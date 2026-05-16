import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json


def _country_matches(text_blob: str, requested_country: str) -> bool:
    country = (requested_country or "").strip().lower()
    if not country:
        return True
    if "remote" in text_blob:
        return True
    aliases = {country}
    if country in {"de", "deutschland", "germany"}:
        aliases.update({"de", "deutschland", "germany"})
    return any(alias in text_blob for alias in aliases)


def _extract_keywords(text: str) -> list[str]:
    tokens = [token.strip(".,:;()[]{}").lower() for token in text.split()]
    cleaned = []
    for token in tokens:
        if len(token) < 3:
            continue
        if not token.replace("-", "").isalnum():
            continue
        cleaned.append(token)
    return list(dict.fromkeys(cleaned))[:20]


def _clean_results(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dedupe: dict[str, dict[str, Any]] = {}
    for item in items:
        url = (item.get("apply_url") or "").strip().lower()
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        key = f"{(item.get('title') or '').strip().lower()}|{(item.get('company') or '').strip().lower()}|{(item.get('location') or '').strip().lower()}"
        if key not in dedupe:
            dedupe[key] = item
    return list(dedupe.values())


def _scrape_remoteok(preferences: dict | None, query_terms: list[str], limit: int) -> list[dict[str, Any]]:
    prefs = preferences or {}
    country = (prefs.get("country") or "").strip().lower()
    city = (prefs.get("city") or "").strip().lower()
    request = Request("https://remoteok.com/remote-dev-jobs.rss", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=12) as response:  # nosec B310
        xml_payload = response.read().decode("utf-8", errors="ignore")
    root = ET.fromstring(xml_payload)
    items: list[dict[str, Any]] = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "Remote Role").strip()
        link = (node.findtext("link") or "").strip()
        description = (node.findtext("description") or "").strip()
        blob = f"{title} {description}".lower()
        if query_terms and not any(term in blob for term in query_terms[:4]):
            continue
        if city and city not in blob:
            continue
        if country and not _country_matches(blob, country):
            continue
        items.append(
            {
                "source": "scrape_remoteok",
                "external_id": link or title,
                "title": title[:160],
                "company": "RemoteOK",
                "location": "Remote",
                "country": prefs.get("country") or None,
                "city": prefs.get("city") or None,
                "work_mode": "remote",
                "job_type": None,
                "apply_url": link,
                "description": description[:4000],
                "skills_csv": ",".join(_extract_keywords(description)),
            }
        )
        if len(items) >= limit:
            break
    return items


def _scrape_weworkremotely(query_terms: list[str], limit: int) -> list[dict[str, Any]]:
    request = Request("https://weworkremotely.com/remote-jobs.rss", headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=12) as response:  # nosec B310
        xml_payload = response.read().decode("utf-8", errors="ignore")
    root = ET.fromstring(xml_payload)
    items: list[dict[str, Any]] = []
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "Remote Role").strip()
        link = (node.findtext("link") or "").strip()
        description = (node.findtext("description") or "").strip()
        blob = f"{title} {description}".lower()
        if query_terms and not any(term in blob for term in query_terms[:4]):
            continue
        company = "WeWorkRemotely"
        if " at " in title.lower():
            parts = title.split(" at ", 1)
            if len(parts) == 2:
                title = parts[0].strip()[:160]
                company = parts[1].strip()[:160] or company
        items.append(
            {
                "source": "scrape_weworkremotely",
                "external_id": link or title,
                "title": title[:160],
                "company": company,
                "location": "Remote",
                "country": None,
                "city": None,
                "work_mode": "remote",
                "job_type": None,
                "apply_url": link,
                "description": description[:4000],
                "skills_csv": ",".join(_extract_keywords(description)),
            }
        )
        if len(items) >= limit:
            break
    return items


def _scrape_remotive_api(preferences: dict | None, query_terms: list[str], limit: int) -> list[dict[str, Any]]:
    prefs = preferences or {}
    country = (prefs.get("country") or "").strip().lower()
    city = (prefs.get("city") or "").strip().lower()
    query = " ".join(query_terms[:4]).strip() or "software"
    url = f"https://remotive.com/api/remote-jobs?{urlencode({'search': query})}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urlopen(request, timeout=15) as response:  # nosec B310
        payload = json.loads(response.read().decode("utf-8"))

    items: list[dict[str, Any]] = []
    for row in payload.get("jobs", [])[: limit * 3]:
        title = (row.get("title") or "Remote Role").strip()
        company = (row.get("company_name") or "Remotive Company").strip()
        location = (row.get("candidate_required_location") or "Remote").strip()
        apply_url = (row.get("url") or "").strip()
        description = (row.get("description") or "").strip()
        blob = f"{title} {location} {description}".lower()
        if query_terms and not any(term in blob for term in query_terms[:3]):
            continue
        if city and city not in blob:
            continue
        if country and not _country_matches(blob, country):
            continue
        items.append(
            {
                "source": "scrape_remotive",
                "external_id": str(row.get("id") or apply_url or title),
                "title": title[:160],
                "company": company[:160],
                "location": location[:120],
                "country": prefs.get("country") or None,
                "city": prefs.get("city") or None,
                "work_mode": "remote",
                "job_type": (row.get("job_type") or "")[:40] or None,
                "apply_url": apply_url,
                "description": description[:4000],
                "skills_csv": ",".join(_extract_keywords(description)),
            }
        )
        if len(items) >= limit:
            break
    return items


def scrape_jobs_from_web(preferences: dict | None, query: str, limit: int = 40) -> list[dict[str, Any]]:
    terms = [part for part in (query or "").lower().split() if part]
    target = min(max(limit, 1), 100)
    rows: list[dict[str, Any]] = []

    try:
        rows.extend(_scrape_remoteok(preferences, terms, limit=min(target, 50)))
    except Exception:
        pass

    if len(rows) < target:
        try:
            rows.extend(_scrape_weworkremotely(terms, limit=min(target - len(rows), 50)))
        except Exception:
            pass

    if len(rows) < target:
        try:
            rows.extend(_scrape_remotive_api(preferences, terms, limit=min(target - len(rows), 50)))
        except Exception:
            pass

    # Graceful fallback: if filtering got too strict, return latest remote jobs.
    if not rows:
        try:
            rows.extend(_scrape_weworkremotely([], limit=min(target, 30)))
        except Exception:
            pass

    return _clean_results(rows)[:target]
