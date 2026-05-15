import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


COUNTRY_TO_ADZUNA = {
    "germany": "de",
    "de": "de",
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


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=20) as response:  # nosec B310
        payload = response.read().decode("utf-8")
    return json.loads(payload)


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


def build_search_terms(preferences: dict | None, cv_text: str) -> str:
    prefs = preferences or {}
    title_hint = (prefs.get("job_title") or "").strip()
    mode_hint = (prefs.get("work_mode") or "").strip()
    skill_terms = _extract_keywords_from_cv(cv_text)
    base_terms = [title_hint] if title_hint else []
    if mode_hint:
        base_terms.append(mode_hint)
    base_terms.extend(skill_terms[:6])
    compact = [term for term in base_terms if term]
    return " ".join(compact) or "software engineer"


def fetch_adzuna_jobs(preferences: dict | None, cv_text: str, limit: int = 20) -> list[dict[str, Any]]:
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
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
            }
        )
    return items


def fetch_jsearch_jobs(preferences: dict | None, cv_text: str, limit: int = 20) -> list[dict[str, Any]]:
    api_key = os.getenv("RAPIDAPI_KEY", "").strip()
    if not api_key:
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
    data = _http_get_json(url, headers=headers)

    items = []
    for row in data.get("data", [])[:limit]:
        title = row.get("job_title") or "Unknown Role"
        company = row.get("employer_name") or "Unknown Company"
        location = ", ".join(
            [part for part in [row.get("job_city"), row.get("job_country")] if part]
        ) or "Unknown"
        is_remote = bool(row.get("job_is_remote"))
        detected_mode = "remote" if is_remote else "on-site"
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
            }
        )
    return items


def fetch_real_jobs(preferences: dict | None, cv_text: str, limit: int = 20) -> list[dict[str, Any]]:
    provider = os.getenv("JOB_API_PROVIDER", "adzuna").strip().lower()
    if provider == "jsearch":
        return fetch_jsearch_jobs(preferences, cv_text, limit=limit)
    return fetch_adzuna_jobs(preferences, cv_text, limit=limit)

