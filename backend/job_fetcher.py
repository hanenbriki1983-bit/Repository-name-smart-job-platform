import difflib
import json
import os
import logging
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET
import requests
from web_scraper import scrape_jobs_from_web

logger = logging.getLogger("smartjob.backend.providers")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
LAST_FETCH_DIAGNOSTICS: dict[str, Any] = {}

COUNTRY_TO_ADZUNA = {
    "germany": "de",
    "de": "de",
    "deutschland": "de",
    "united states": "us",
    "usa": "us",
    "us": "us",
    "united kingdom": "gb",
    "uk": "gb",
    "gb": "gb",
    "france": "fr",
    "fr": "fr",
    "spain": "es",
    "es": "es",
    "italy": "it",
    "it": "it",
    "netherlands": "nl",
    "nl": "nl",
    "poland": "pl",
    "pl": "pl",
}

COUNTRY_ALIASES = {
    "germany": {"germany", "deutschland", "de"},
    "deutschland": {"germany", "deutschland", "de"},
    "de": {"germany", "deutschland", "de"},
}

KNOWN_JOB_TITLES = [
    "Nurse",
    "Registered Nurse",
    "Nursing Assistant",
    "Case Manager Nurse",
    "Advanced Practice Nurse",
    "Caregiver",
    "Housekeeping",
    "Driver",
    "Security Guard",
    "Warehouse Worker",
    "Cashier",
    "Waiter",
    "Chef",
    "Sales Assistant",
    "Customer Support",
    "Electrician",
    "Plumber",
    "Recruiter",
    "HR Specialist",
    "Employer Relations Specialist",
    "Job Posting Specialist",
    "Payroll Specialist",
    "Python Developer",
    "Backend Developer",
    "Frontend Developer",
    "Full Stack Developer",
    "Data Scientist",
    "Data Analyst",
    "Machine Learning Engineer",
    "DevOps Engineer",
    "Cloud Engineer",
    "Software Engineer",
    "QA Engineer",
    "Product Manager",
    "UI UX Designer",
    "Java Developer",
    "JavaScript Developer",
    "React Developer",
]

RELATED_QUERY_TERMS = {
    "nurse": ["nurse", "pflegefachkraft", "pflegehelfer", "krankenschwester", "altenpfleger", "gesundheits und krankenpfleger"],
    "plumber": ["plumber", "installateur", "sanitar", "heizung", "sanitaer", "klempner", "سباك"],
    "electrician": ["electrician", "elektriker", "elektroinstallateur", "كهربائي"],
    "housekeeping": ["housekeeping", "zimmermaedchen", "reinigungskraft", "housekeeper", "تدبير منزلي"],
}

TITLE_ALIASES = {
    "سباك": "Plumber",
    "plomberie": "Plumber",
    "klempner": "Plumber",
    "installateur": "Plumber",
    "elektriker": "Electrician",
    "kellner": "Waiter",
    "krankenpfleger": "Nurse",
    "pflegehelfer": "Nursing Assistant",
}

PLACEHOLDER_TOKENS = {
    "your",
    "here",
    "placeholder",
    "put",
    "insert",
    "example",
    "dummy",
    "test",
    "ضعي",
    "هنا",
}


def _broad_search_mode_enabled() -> bool:
    return (os.getenv("BROAD_SEARCH_MODE") or "1").strip().lower() in {"1", "true", "yes", "on"}


def _looks_configured(value: str) -> bool:
    raw = (value or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    if any(token in lowered for token in PLACEHOLDER_TOKENS):
        return False
    if lowered.startswith("<") and lowered.endswith(">"):
        return False
    return True


def ai_assist_enabled() -> bool:
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def scraping_fallback_enabled() -> bool:
    return (os.getenv("ENABLE_SCRAPING_FALLBACK") or "").strip().lower() in {"1", "true", "yes", "on"}


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    logger.info("provider_http_get url=%s", url.split("?")[0])
    req_headers = headers or {}
    try:
        response = requests.get(url, headers=req_headers, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as req_exc:
        logger.warning("provider_http_get requests_failed error=%s", req_exc)
    request = Request(url, headers=req_headers)
    with urlopen(request, timeout=20) as response:  # nosec B310
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _http_post_json(url: str, body: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    logger.info("provider_http_post url=%s", url)
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    try:
        response = requests.post(url, json=body, headers=merged_headers, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as req_exc:
        logger.warning("provider_http_post requests_failed error=%s", req_exc)
    raw = json.dumps(body).encode("utf-8")
    request = Request(url, data=raw, headers=merged_headers, method="POST")
    with urlopen(request, timeout=20) as response:  # nosec B310
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _openai_chat_json(system_prompt: str, user_prompt: str, max_tokens: int = 180) -> str | None:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        data = _http_post_json(OPENAI_API_URL, payload, headers=headers)
        return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip() or None
    except (URLError, HTTPError, TimeoutError) as exc:
        logger.warning("openai_assist_failed error=%s", exc)
        return None
    except Exception as exc:
        logger.warning("openai_assist_failed error=%s", exc)
        return None


def _extract_keywords_from_cv(cv_text: str) -> list[str]:
    raw_tokens = [token.strip(".,:;()[]{}").lower() for token in cv_text.split()]
    terms = []
    for token in raw_tokens:
        if len(token) < 3 or not token.replace("-", "").isalnum():
            continue
        if token in {"and", "with", "for", "the", "this", "that", "from"}:
            continue
        terms.append(token)
    unique_terms = list(dict.fromkeys(terms))
    return unique_terms[:12]


def suggest_job_titles(query: str, limit: int = 8) -> list[str]:
    text = (query or "").strip()
    if not text:
        return KNOWN_JOB_TITLES[:limit]

    starts = [title for title in KNOWN_JOB_TITLES if text.lower() in title.lower()]
    fuzzy = difflib.get_close_matches(text, KNOWN_JOB_TITLES, n=limit, cutoff=0.45)
    merged = []
    for title in starts + fuzzy:
        if title not in merged:
            merged.append(title)
    local = merged[:limit]
    if local or not ai_assist_enabled():
        return local

    ai_text = _openai_chat_json(
        "You suggest realistic software and professional job titles. Return only a plain list, one title per line.",
        f"User typed: '{text}'. Suggest up to {limit} likely intended job titles.",
        max_tokens=140,
    )
    if not ai_text:
        return local
    ai_titles = []
    for line in ai_text.splitlines():
        clean = line.strip("-*0123456789. ").strip()
        if clean and clean not in ai_titles:
            ai_titles.append(clean[:80])
        if len(ai_titles) >= limit:
            break
    return ai_titles or local


def autocorrect_job_title(raw_title: str) -> str:
    text = (raw_title or "").strip()
    if not text:
        return ""
    alias = TITLE_ALIASES.get(text.lower())
    if alias:
        return alias
    # Keep typo-correction conservative so non-tech titles (e.g. housekeeping, nurse)
    # are not incorrectly forced into software titles.
    candidate_matches = difflib.get_close_matches(text, KNOWN_JOB_TITLES, n=1, cutoff=0.55)
    if candidate_matches:
        candidate = candidate_matches[0]
        ratio = difflib.SequenceMatcher(a=text.lower(), b=candidate.lower()).ratio()
        if ratio >= 0.86:
            return candidate
    if not ai_assist_enabled():
        return text
    ai_text = _openai_chat_json(
        "You correct job title typos. Return only one corrected job title, no explanation.",
        f"Correct this job title typo if needed: '{text}'",
        max_tokens=40,
    )
    if not ai_text:
        return text
    first_line = ai_text.splitlines()[0].strip("-*0123456789. ").strip()
    return first_line or text


def build_short_match_reason(
    title: str,
    company: str,
    location: str,
    preferences: dict | None,
    reasons: list[str] | None,
) -> str:
    base_reasons = reasons or []
    if ai_assist_enabled():
        pref = preferences or {}
        ai_text = _openai_chat_json(
            "Write one short sentence (max 16 words) why this job matches the user. No bullet points.",
            (
                f"Job: {title} at {company} in {location}\n"
                f"Preferences: title={pref.get('job_title')}, country={pref.get('country')}, city={pref.get('city')}, work_mode={pref.get('work_mode')}\n"
                f"Signals: {', '.join(base_reasons[:3])}"
            ),
            max_tokens=45,
        )
        if ai_text:
            line = ai_text.splitlines()[0].strip()
            if line:
                return line[:160]
    if base_reasons:
        return base_reasons[0][:160]
    return "General profile and preference alignment."


def build_search_terms(preferences: dict | None, cv_text: str) -> str:
    prefs = preferences or {}
    original_title = (prefs.get("job_title") or "").strip()
    corrected_title = autocorrect_job_title(original_title)
    mode_hint = (prefs.get("work_mode") or "").strip()
    request_hint = (prefs.get("search_text") or "").strip()
    skill_terms = _extract_keywords_from_cv(cv_text)
    base_terms = [request_hint] if request_hint else []
    if corrected_title:
        title_lower = corrected_title.lower()
        expanded = []
        for key, aliases in RELATED_QUERY_TERMS.items():
            if key in title_lower:
                expanded.extend(aliases)
        if expanded:
            base_terms.append(" OR ".join(dict.fromkeys(expanded)))
        else:
            base_terms.append(corrected_title)
    if mode_hint:
        base_terms.append(mode_hint)
    # Keep provider queries focused on explicit user intent.
    # CV keywords can over-constrain broad/non-tech roles (e.g. electrician, nurse).
    if not (corrected_title or request_hint):
        base_terms.extend(skill_terms[:4])
    compact = [term for term in base_terms if term]
    return " ".join(compact) or "software engineer"


def _has_valid_apply_url(item: dict[str, Any]) -> bool:
    url = (item.get("apply_url") or "").strip().lower()
    return url.startswith("http://") or url.startswith("https://")


def _normalize_dedupe_key(item: dict[str, Any]) -> str:
    title = (item.get("title") or "").strip().lower()
    company = (item.get("company") or "").strip().lower()
    location = (item.get("location") or "").strip().lower()
    return f"{title}|{company}|{location}"


def _clean_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = {}
    for item in items:
        if not _has_valid_apply_url(item):
            continue
        key = _normalize_dedupe_key(item)
        if key not in unique:
            unique[key] = item
    return list(unique.values())


def _clean_results_with_debug(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    unique: dict[str, dict[str, Any]] = {}
    rejected = {
        "invalid_apply_url": 0,
        "duplicate": 0,
        "missing_title": 0,
        "missing_company": 0,
        "missing_location": 0,
    }
    for item in items:
        if not (item.get("title") or "").strip():
            rejected["missing_title"] += 1
            continue
        if not (item.get("company") or "").strip():
            rejected["missing_company"] += 1
            continue
        if not (item.get("location") or "").strip():
            rejected["missing_location"] += 1
            continue
        if not _has_valid_apply_url(item):
            rejected["invalid_apply_url"] += 1
            continue
        key = _normalize_dedupe_key(item)
        if key in unique:
            rejected["duplicate"] += 1
            continue
        unique[key] = item
    return list(unique.values()), rejected


def _country_matches(text_blob: str, requested_country: str) -> bool:
    country = (requested_country or "").strip().lower()
    if not country:
        return True
    aliases = COUNTRY_ALIASES.get(country, {country})
    return any(alias in text_blob for alias in aliases)


def fetch_adzuna_jobs(preferences: dict | None, cv_text: str, limit: int = 25) -> list[dict[str, Any]]:
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    if not _looks_configured(app_id) or not _looks_configured(app_key):
        return []

    prefs = preferences or {}
    country_raw = (prefs.get("country") or "de").strip().lower()
    country = COUNTRY_TO_ADZUNA.get(country_raw, "de")
    city = (prefs.get("city") or "").strip()
    work_mode = (prefs.get("work_mode") or "").strip().lower()
    query = build_search_terms(preferences, cv_text)

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(max(limit, 1), 50),
        "what": query,
        "content-type": "application/json",
    }
    if city:
        params["where"] = city

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?{urlencode(params)}"
    logger.info(
        "provider=adzuna request country=%s country_raw=%s city=%s query=%s limit=%s",
        country,
        country_raw,
        city or "-",
        query,
        limit,
    )
    data = _http_get_json(url)
    items = []
    for row in data.get("results", []):
        description = row.get("description") or ""
        location_name = row.get("location", {}).get("display_name") or row.get("location", {}).get("area", [""])[0]
        text_blob = f"{(row.get('title') or '')} {description} {location_name}".lower()
        detected_mode = "remote" if "remote" in text_blob else ("hybrid" if "hybrid" in text_blob else "on-site")
        if work_mode and work_mode not in detected_mode and not (work_mode == "on-site" and detected_mode == "on-site"):
            continue
        items.append(
            {
                "source": "adzuna",
                "external_id": str(row.get("id") or row.get("redirect_url") or ""),
                "title": (row.get("title") or "Unknown Role")[:160],
                "company": (row.get("company", {}).get("display_name") or "Unknown Company")[:160],
                "location": (location_name or "Unknown")[:120],
                "country": (prefs.get("country") or "")[:120] or None,
                "city": city[:120] or None,
                "work_mode": detected_mode,
                "job_type": None,
                "apply_url": row.get("redirect_url"),
                "description": description[:4000],
                "skills_csv": ",".join(_extract_keywords_from_cv(description)[:20]),
                "posted_at": row.get("created"),
            }
        )
    cleaned = _clean_results(items)
    logger.info("provider=adzuna response_count=%s cleaned_count=%s", len(items), len(cleaned))
    return cleaned


def fetch_jsearch_jobs(preferences: dict | None, cv_text: str, limit: int = 25) -> list[dict[str, Any]]:
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not _looks_configured(api_key):
        return []

    prefs = preferences or {}
    city = (prefs.get("city") or "").strip()
    country = (prefs.get("country") or "").strip()
    work_mode = (prefs.get("work_mode") or "").strip().lower()
    query = build_search_terms(preferences, cv_text)
    query_with_location = " ".join([query, city, country]).strip()

    params = {"query": query_with_location, "page": "1", "num_pages": "1"}
    url = f"https://jsearch.p.rapidapi.com/search?{urlencode(params)}"
    headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    logger.info("provider=jsearch request query=%s limit=%s", query_with_location, limit)
    data = _http_get_json(url, headers=headers)

    items = []
    for row in data.get("data", [])[:limit]:
        title = row.get("job_title") or "Unknown Role"
        company = row.get("employer_name") or "Unknown Company"
        location = ", ".join([part for part in [row.get("job_city"), row.get("job_country")] if part]) or "Unknown"
        detected_mode = "remote" if bool(row.get("job_is_remote")) else "on-site"
        if work_mode and work_mode not in {detected_mode, "hybrid"}:
            continue
        description = row.get("job_description") or ""
        items.append(
            {
                "source": "jsearch",
                "external_id": str(row.get("job_id") or row.get("job_apply_link") or ""),
                "title": title[:160],
                "company": company[:160],
                "location": location[:120],
                "country": (row.get("job_country") or country)[:120] or None,
                "city": (row.get("job_city") or city)[:120] or None,
                "work_mode": detected_mode,
                "job_type": (row.get("job_employment_type") or "")[:40] or None,
                "apply_url": row.get("job_apply_link"),
                "description": description[:4000],
                "skills_csv": ",".join(_extract_keywords_from_cv(description)[:20]),
                "posted_at": row.get("job_posted_at_datetime_utc") or row.get("job_posted_at_datetime_utc"),
            }
        )
    cleaned = _clean_results(items)
    logger.info("provider=jsearch response_count=%s cleaned_count=%s", len(items), len(cleaned))
    return cleaned


def fetch_arbeitnow_jobs(preferences: dict | None, cv_text: str, limit: int = 25) -> list[dict[str, Any]]:
    prefs = preferences or {}
    broad_mode = _broad_search_mode_enabled()
    city = (prefs.get("city") or "").strip().lower()
    country = (prefs.get("country") or "").strip().lower()
    work_mode = (prefs.get("work_mode") or "").strip().lower()
    query_terms = build_search_terms(preferences, cv_text).lower().split()
    data = _http_get_json("https://www.arbeitnow.com/api/job-board-api")
    raw_count = len(data.get("data", []))
    rejected = {"city": 0, "country": 0, "query": 0, "work_mode": 0}
    items = []
    for row in data.get("data", []):
        title = (row.get("title") or "").strip()
        company = (row.get("company_name") or "").strip()
        location = (row.get("location") or "Remote").strip()
        description = (row.get("description") or "")[:4000]
        tags = row.get("tags") or []
        text_blob = f"{title} {location} {' '.join(tags)} {description}".lower()
        if (not broad_mode) and city and city not in text_blob:
            rejected["city"] += 1
            continue
        if (not broad_mode) and country and not _country_matches(text_blob, country):
            rejected["country"] += 1
            continue
        if query_terms and not any(term in text_blob for term in query_terms[:4]):
            rejected["query"] += 1
            continue
        detected_mode = "remote" if "remote" in text_blob else "on-site"
        if work_mode and work_mode not in {detected_mode, "hybrid"}:
            rejected["work_mode"] += 1
            continue
        items.append(
            {
                "source": "arbeitnow",
                "external_id": str(row.get("slug") or row.get("url") or ""),
                "title": title[:160] or "Unknown Role",
                "company": company[:160] or "Unknown Company",
                "location": location[:120],
                "country": prefs.get("country"),
                "city": prefs.get("city"),
                "work_mode": detected_mode,
                "job_type": None,
                "apply_url": row.get("url"),
                "description": description,
                "skills_csv": ",".join(tags[:20]),
                "posted_at": row.get("created_at"),
            }
        )
        if len(items) >= limit:
            break
    cleaned, clean_rejected = _clean_results_with_debug(items)
    logger.info(
        "provider=arbeitnow raw_count=%s normalized_count=%s cleaned_count=%s filtered_out=%s clean_rejected=%s broad_mode=%s",
        raw_count,
        len(items),
        len(cleaned),
        rejected,
        clean_rejected,
        broad_mode,
    )
    return cleaned


def fetch_remotive_jobs(preferences: dict | None, cv_text: str, limit: int = 25) -> list[dict[str, Any]]:
    prefs = preferences or {}
    broad_mode = _broad_search_mode_enabled()
    query = build_search_terms(preferences, cv_text)
    city = (prefs.get("city") or "").strip().lower()
    country = (prefs.get("country") or "").strip().lower()
    params = {"search": query}
    data = _http_get_json(f"https://remotive.com/api/remote-jobs?{urlencode(params)}")
    raw_count = len(data.get("jobs", []))
    rejected = {"city": 0, "country": 0}
    items = []
    for row in data.get("jobs", [])[:limit * 2]:
        title = row.get("title") or "Unknown Role"
        company = row.get("company_name") or "Unknown Company"
        location = row.get("candidate_required_location") or "Remote"
        description = (row.get("description") or "")[:4000]
        text_blob = f"{title} {location} {description}".lower()
        if (not broad_mode) and city and city not in text_blob:
            rejected["city"] += 1
            continue
        if (not broad_mode) and country and not _country_matches(text_blob, country):
            rejected["country"] += 1
            continue
        items.append(
            {
                "source": "remotive",
                "external_id": str(row.get("id") or row.get("url") or ""),
                "title": title[:160],
                "company": company[:160],
                "location": location[:120],
                "country": prefs.get("country"),
                "city": prefs.get("city"),
                "work_mode": "remote",
                "job_type": (row.get("job_type") or "")[:40] or None,
                "apply_url": row.get("url"),
                "description": description,
                "skills_csv": ",".join((row.get("tags") or [])[:20]),
                "posted_at": row.get("publication_date"),
            }
        )
        if len(items) >= limit:
            break
    cleaned, clean_rejected = _clean_results_with_debug(items)
    logger.info(
        "provider=remotive raw_count=%s normalized_count=%s cleaned_count=%s filtered_out=%s clean_rejected=%s broad_mode=%s",
        raw_count,
        len(items),
        len(cleaned),
        rejected,
        clean_rejected,
        broad_mode,
    )
    return cleaned


def fetch_remotive_jobs_raw(limit: int = 20) -> list[dict[str, Any]]:
    target = min(max(int(limit or 20), 1), 100)
    data = _http_get_json("https://remotive.com/api/remote-jobs")
    items: list[dict[str, Any]] = []
    for row in (data.get("jobs") or [])[:target]:
        items.append(
            {
                "source": "remotive_raw",
                "external_id": str(row.get("id") or row.get("url") or ""),
                "title": (row.get("title") or "Unknown Role")[:160],
                "company": (row.get("company_name") or "Unknown Company")[:160],
                "location": (row.get("candidate_required_location") or "Remote")[:120],
                "country": row.get("candidate_required_location"),
                "city": None,
                "work_mode": "remote",
                "job_type": (row.get("job_type") or "")[:40] or None,
                "apply_url": row.get("url"),
                "description": (row.get("description") or "")[:4000],
                "posted_at": row.get("publication_date"),
                "raw_provider_payload": row,
            }
        )
    logger.info("provider=remotive_raw raw_count=%s returned_count=%s", len(data.get("jobs") or []), len(items))
    return items


def fetch_jooble_jobs(preferences: dict | None, cv_text: str, limit: int = 25) -> list[dict[str, Any]]:
    api_key = os.getenv("JOOBLE_API_KEY", "").strip()
    if not _looks_configured(api_key):
        return []
    prefs = preferences or {}
    country = (prefs.get("country") or "Germany").strip()
    city = (prefs.get("city") or "").strip()
    query = build_search_terms(preferences, cv_text)
    body = {
        "keywords": query,
        "location": city or country,
        "radius": "100",
        "page": "1",
    }
    url = f"https://jooble.org/api/{api_key}"
    logger.info("provider=jooble request country=%s city=%s query=%s limit=%s", country, city or "-", query, limit)
    data = _http_post_json(url, body)
    items = []
    for row in data.get("jobs", [])[:limit]:
        title = row.get("title") or "Unknown Role"
        company = row.get("company") or "Unknown Company"
        location = row.get("location") or country
        description = (row.get("snippet") or "")[:4000]
        items.append(
            {
                "source": "jooble",
                "external_id": str(row.get("id") or row.get("link") or ""),
                "title": title[:160],
                "company": company[:160],
                "location": location[:120],
                "country": prefs.get("country"),
                "city": prefs.get("city"),
                "work_mode": "remote" if "remote" in f"{title} {description}".lower() else None,
                "job_type": None,
                "apply_url": row.get("link"),
                "description": description,
                "skills_csv": ",".join(_extract_keywords_from_cv(description)[:20]),
                "posted_at": row.get("updated"),
            }
        )
    cleaned = _clean_results(items)
    logger.info("provider=jooble response_count=%s cleaned_count=%s", len(items), len(cleaned))
    return cleaned


def fetch_the_muse_jobs(preferences: dict | None, cv_text: str, limit: int = 20) -> list[dict[str, Any]]:
    query = build_search_terms(preferences, cv_text)
    data = _http_get_json(f"https://www.themuse.com/api/public/jobs?{urlencode({'page': 1, 'descending': True})}")
    items = []
    q_tokens = query.lower().split()
    for row in data.get("results", []):
        title = row.get("name") or "Unknown Role"
        company = (row.get("company") or {}).get("name") or "Unknown Company"
        locations = row.get("locations") or []
        location = ", ".join(loc.get("name") for loc in locations if loc.get("name")) or "Unknown"
        landing = row.get("refs", {}).get("landing_page")
        contents = (row.get("contents") or "")[:4000]
        blob = f"{title} {company} {location} {contents}".lower()
        if q_tokens and not any(token in blob for token in q_tokens[:4]):
            continue
        items.append(
            {
                "source": "themuse",
                "external_id": str(row.get("id") or landing or ""),
                "title": title[:160],
                "company": company[:160],
                "location": location[:120],
                "country": None,
                "city": None,
                "work_mode": "remote" if "remote" in blob else None,
                "job_type": None,
                "apply_url": landing,
                "description": contents,
                "skills_csv": ",".join(_extract_keywords_from_cv(contents)[:20]),
                "posted_at": row.get("publication_date"),
            }
        )
        if len(items) >= limit:
            break
    cleaned, clean_rejected = _clean_results_with_debug(items)
    logger.info(
        "provider=themuse raw_count=%s normalized_count=%s cleaned_count=%s clean_rejected=%s",
        len(data.get("results", [])),
        len(items),
        len(cleaned),
        clean_rejected,
    )
    return cleaned


def fetch_indeed_compatible_jobs(preferences: dict | None, cv_text: str, limit: int = 20) -> list[dict[str, Any]]:
    # Placeholder for indeed-compatible feeds when an integrator endpoint is configured.
    # Expected endpoint returns list[dict] with keys compatible with normalized format.
    feed_url = os.getenv("INDEED_FEED_URL", "").strip()
    if not _looks_configured(feed_url):
        return []
    data = _http_get_json(feed_url)
    items = []
    for row in (data.get("results") or data.get("items") or [])[:limit]:
        items.append(
            {
                "source": "indeed_feed",
                "external_id": str(row.get("id") or row.get("apply_url") or ""),
                "title": (row.get("title") or "Unknown Role")[:160],
                "company": (row.get("company") or "Unknown Company")[:160],
                "location": (row.get("location") or "Unknown")[:120],
                "country": row.get("country"),
                "city": row.get("city"),
                "work_mode": row.get("work_mode"),
                "job_type": row.get("job_type"),
                "apply_url": row.get("apply_url"),
                "description": (row.get("description") or "")[:4000],
                "skills_csv": ",".join(_extract_keywords_from_cv(row.get("description") or "")[:20]),
                "posted_at": row.get("posted_at"),
            }
        )
    cleaned = _clean_results(items)
    logger.info("provider=indeed_feed response_count=%s cleaned_count=%s", len(items), len(cleaned))
    return cleaned


def scrape_remoteok_rss(preferences: dict | None, cv_text: str, limit: int = 20) -> list[dict[str, Any]]:
    prefs = preferences or {}
    query_terms = build_search_terms(preferences, cv_text).lower().split()
    country = (prefs.get("country") or "").strip().lower()
    city = (prefs.get("city") or "").strip().lower()
    work_mode = (prefs.get("work_mode") or "").strip().lower()
    if work_mode and work_mode != "remote":
        return []
    try:
        request = Request("https://remoteok.com/remote-dev-jobs.rss", headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=12) as response:  # nosec B310
            xml_payload = response.read().decode("utf-8", errors="ignore")
        root = ET.fromstring(xml_payload)
    except Exception as exc:
        logger.warning("provider=scrape_remoteok_rss failed error=%s", exc)
        return []

    items = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "Remote Role").strip()
        link = (node.findtext("link") or "").strip()
        description = (node.findtext("description") or "").strip()
        blob = f"{title} {description}".lower()
        if query_terms and not any(term in blob for term in query_terms[:3]):
            continue
        if city and city not in blob:
            continue
        if country and not _country_matches(blob, country):
            continue
        company = "RemoteOK"
        items.append(
            {
                "source": "scrape_remoteok",
                "external_id": link or title,
                "title": title[:160],
                "company": company,
                "location": "Remote",
                "country": prefs.get("country") or None,
                "city": prefs.get("city") or None,
                "work_mode": "remote",
                "job_type": None,
                "apply_url": link,
                "description": description[:4000],
                "skills_csv": ",".join(_extract_keywords_from_cv(description)[:20]),
            }
        )
        if len(items) >= limit:
            break
    cleaned = _clean_results(items)
    logger.info("provider=scrape_remoteok_rss response_count=%s cleaned_count=%s", len(items), len(cleaned))
    return cleaned


def _scraping_provider_sequence() -> list[tuple[str, Any]]:
    return [
        ("python_web_scraper", lambda preferences, cv_text, limit=20: scrape_jobs_from_web(preferences, build_search_terms(preferences, cv_text), limit=limit)),
    ]


def _free_provider_sequence() -> list[tuple[str, Any]]:
    return [
        ("arbeitnow", fetch_arbeitnow_jobs),
        ("remotive", fetch_remotive_jobs),
        ("themuse", fetch_the_muse_jobs),
        ("scrape_remoteok_rss", scrape_remoteok_rss),
    ]


def _keyed_provider_sequence() -> list[tuple[str, Any]]:
    return [
        ("adzuna", fetch_adzuna_jobs),
        ("jsearch", fetch_jsearch_jobs),
        ("jooble", fetch_jooble_jobs),
        ("indeed_feed", fetch_indeed_compatible_jobs),
    ]


def _provider_sequence() -> list[tuple[str, Any]]:
    mode = (os.getenv("JOB_API_PROVIDER") or "multi").strip().lower()
    if mode in {"scrape", "scraping", "webscrape", "web-scrape"}:
        return _scraping_provider_sequence()
    if mode in {"multi", "all", "*"}:
        return _free_provider_sequence() + _keyed_provider_sequence()

    by_name = {name: fn for name, fn in (_free_provider_sequence() + _keyed_provider_sequence())}
    if mode in by_name:
        # Keep selected provider first, still fall through to others for resiliency.
        selected = [(mode, by_name[mode])]
        others = [(name, fn) for name, fn in by_name.items() if name != mode]
        return selected + others
    return _free_provider_sequence() + _keyed_provider_sequence()


def get_last_fetch_diagnostics() -> dict[str, Any]:
    return dict(LAST_FETCH_DIAGNOSTICS)


def fetch_real_jobs(preferences: dict | None, cv_text: str, limit: int = 50) -> list[dict[str, Any]]:
    target = min(max(limit, 1), 200)
    aggregated: list[dict[str, Any]] = []
    provider_counts: dict[str, int] = {}
    provider_failures: dict[str, str] = {}
    connection_failures = 0
    for provider_name, provider_fn in _provider_sequence():
        provider_items = []
        try:
            provider_items = provider_fn(preferences, cv_text, limit=min(50, target))
            logger.info("provider=%s fetched_count=%s", provider_name, len(provider_items))
        except Exception as exc:
            logger.exception("provider=%s failed error=%s", provider_name, exc)
            provider_items = []
            msg = str(exc)
            provider_failures[provider_name] = msg[:240]
            lowered = msg.lower()
            if "winerror 10013" in lowered or "urlopen error" in lowered or "permissionerror" in lowered:
                connection_failures += 1
        provider_counts[provider_name] = len(provider_items)
        if provider_items:
            aggregated.extend(provider_items)
        # keep trying next provider even if one returns 0, to maximize coverage.
        if len(aggregated) >= target:
            break
    cleaned = _clean_results(aggregated)[:target]
    logger.info(
        "providers_aggregated total_before_clean=%s total_after_clean=%s provider_counts=%s",
        len(aggregated),
        len(cleaned),
        provider_counts,
    )
    warning = None
    if connection_failures >= 2:
        warning = (
            "Some job providers are currently blocked by network/firewall/security policy "
            "(connection failures detected, including possible WinError 10013). "
            "Search logic is working, but external provider access is restricted."
        )
    elif connection_failures == 1:
        warning = "One job provider connection failed. Network/security policy may be blocking external provider access."
    global LAST_FETCH_DIAGNOSTICS
    LAST_FETCH_DIAGNOSTICS = {
        "provider_counts": provider_counts,
        "provider_failures": provider_failures,
        "connection_failures": connection_failures,
        "provider_warning": warning,
    }
    scrape_min_results = max(1, int((os.getenv("SCRAPING_MIN_RESULTS") or "12").strip() or "12"))
    if cleaned and (not scraping_fallback_enabled() or len(cleaned) >= scrape_min_results):
        return cleaned

    if scraping_fallback_enabled():
        logger.info(
            "providers_scrape_fallback start existing_count=%s threshold=%s",
            len(cleaned),
            scrape_min_results,
        )
        scraped_aggregated: list[dict[str, Any]] = list(cleaned)
        for provider_name, provider_fn in _scraping_provider_sequence():
            provider_items = []
            try:
                remaining = max(1, min(30, target - len(scraped_aggregated)))
                provider_items = provider_fn(preferences, cv_text, limit=remaining)
                logger.info("provider=%s fetched_count=%s", provider_name, len(provider_items))
            except Exception as exc:
                logger.warning("provider=%s failed error=%s", provider_name, exc)
                provider_items = []
                msg = str(exc)
                provider_failures[provider_name] = msg[:240]
                lowered = msg.lower()
                if "winerror 10013" in lowered or "urlopen error" in lowered or "permissionerror" in lowered:
                    connection_failures += 1
            if provider_items:
                scraped_aggregated.extend(provider_items)
            if len(scraped_aggregated) >= target:
                break
        cleaned_after_scrape = _clean_results(scraped_aggregated)[:target]
        logger.info(
            "providers_scrape_fallback done total_before_clean=%s total_after_clean=%s",
            len(scraped_aggregated),
            len(cleaned_after_scrape),
        )
        if cleaned_after_scrape:
            LAST_FETCH_DIAGNOSTICS = {
                "provider_counts": provider_counts,
                "provider_failures": provider_failures,
                "connection_failures": connection_failures,
                "provider_warning": warning,
            }
            return cleaned_after_scrape

    # Relaxed retry: keep user-entered title/search text if present.
    # Only relax title/text when the user did not explicitly provide them.
    relaxed_preferences = dict(preferences or {})
    explicit_job_title = (relaxed_preferences.get("job_title") or "").strip()
    explicit_search_text = (relaxed_preferences.get("search_text") or "").strip()
    if not explicit_job_title and not explicit_search_text:
        relaxed_preferences["job_title"] = ""
        relaxed_preferences["search_text"] = ""
    logger.info("providers_retry mode=relaxed_location_only")
    relaxed_aggregated: list[dict[str, Any]] = []
    relaxed_counts: dict[str, int] = {}
    for provider_name, provider_fn in _provider_sequence():
        provider_items = []
        try:
            provider_items = provider_fn(relaxed_preferences, cv_text, limit=min(50, target))
            logger.info("provider=%s relaxed_fetched_count=%s", provider_name, len(provider_items))
        except Exception as exc:
            logger.exception("provider=%s relaxed_failed error=%s", provider_name, exc)
            provider_items = []
            msg = str(exc)
            provider_failures[f"{provider_name}:relaxed"] = msg[:240]
            lowered = msg.lower()
            if "winerror 10013" in lowered or "urlopen error" in lowered or "permissionerror" in lowered:
                connection_failures += 1
        relaxed_counts[provider_name] = len(provider_items)
        if provider_items:
            relaxed_aggregated.extend(provider_items)
        if len(relaxed_aggregated) >= target:
            break
    relaxed_cleaned = _clean_results(relaxed_aggregated)[:target]
    logger.info(
        "providers_aggregated_relaxed total_before_clean=%s total_after_clean=%s",
        len(relaxed_aggregated),
        len(relaxed_cleaned),
    )
    logger.info("providers_aggregated_relaxed_counts counts=%s", relaxed_counts)
    if connection_failures >= 2:
        warning = (
            "Some job providers are currently blocked by network/firewall/security policy "
            "(connection failures detected, including possible WinError 10013). "
            "Search logic is working, but external provider access is restricted."
        )
    elif connection_failures == 1:
        warning = "One job provider connection failed. Network/security policy may be blocking external provider access."
    LAST_FETCH_DIAGNOSTICS = {
        "provider_counts": provider_counts | {f"{k}:relaxed": v for k, v in relaxed_counts.items()},
        "provider_failures": provider_failures,
        "connection_failures": connection_failures,
        "provider_warning": warning,
    }
    return relaxed_cleaned


def api_keys_configured() -> bool:
    # Public providers (Arbeitnow/Remotive/TheMuse) can work without keys,
    # but key-backed providers are needed for broader coverage (for example
    # local/non-remote roles like nursing jobs in specific German cities).
    adzuna_ready = _looks_configured(os.getenv("ADZUNA_APP_ID", "")) and _looks_configured(os.getenv("ADZUNA_APP_KEY", ""))
    jsearch_ready = _looks_configured(os.getenv("RAPIDAPI_KEY", ""))
    jooble_ready = _looks_configured(os.getenv("JOOBLE_API_KEY", ""))
    indeed_feed_ready = _looks_configured(os.getenv("INDEED_FEED_URL", ""))
    return adzuna_ready or jsearch_ready or jooble_ready or indeed_feed_ready
