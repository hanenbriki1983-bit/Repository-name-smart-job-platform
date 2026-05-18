import hashlib
import logging
import os
import secrets
import math
import time
import json
import re
import zipfile
import threading
import smtplib
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from email.message import EmailMessage

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pypdf import PdfReader
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy import or_, text as sa_text

from database import SessionLocal
from job_fetcher import (
    ai_assist_enabled,
    api_keys_configured,
    autocorrect_job_title,
    build_short_match_reason,
    fetch_real_jobs,
    get_last_fetch_diagnostics,
    suggest_job_titles,
)
from models import (
    Application,
    AuthToken,
    EmailVerificationToken,
    Job,
    PasswordResetToken,
    SavedSearch,
    User,
)

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("smartjob.backend")
REAL_JOB_SOURCES = [
    "adzuna",
    "jsearch",
    "arbeitnow",
    "remotive",
    "jooble",
    "themuse",
    "indeed_feed",
    "scrape_remoteok",
    "scrape_weworkremotely",
    "scrape_remotive",
]
SCRAPED_ONLY_SOURCES = ["scrape_remoteok", "scrape_weworkremotely", "scrape_remotive"]
GERMANY_NEARBY_CITIES = {
    "dusseldorf": ["heiligenhaus", "velbert", "wuppertal", "ratingen", "neuss", "duisburg"],
    "düsseldorf": ["heiligenhaus", "velbert", "wuppertal", "ratingen", "neuss", "duisburg"],
    "velbert": ["dusseldorf", "düsseldorf", "heiligenhaus", "wuppertal", "ratingen", "essen"],
    "heiligenhaus": ["velbert", "dusseldorf", "ratingen", "wülfrath", "essen"],
    "wuppertal": ["velbert", "dusseldorf", "solingen", "remscheid", "essen"],
    "ratingen": ["dusseldorf", "duisburg", "essen", "velbert", "mettmann"],
    "neuss": ["dusseldorf", "krefeld", "moenchengladbach", "köln"],
    "duisburg": ["dusseldorf", "essen", "oberhausen", "muelheim", "krefeld"],
    "essen": ["duisburg", "bochum", "gelsenkirchen", "dortmund", "velbert"],
    "berlin": ["potsdam", "oranienburg", "bernau", "teltow"],
    "potsdam": ["berlin", "brandenburg an der havel", "werder"],
    "munich": ["augsburg", "freising", "erding", "dachau"],
    "münchen": ["augsburg", "freising", "erding", "dachau"],
    "augsburg": ["münchen", "munich", "ulm", "ingolstadt"],
    "hamburg": ["norderstedt", "pinneberg", "aharensburg", "lueneburg"],
    "norderstedt": ["hamburg", "pinneberg", "elmshorn"],
    "frankfurt": ["offenbach", "darmstadt", "wiesbaden", "mainz", "hanau"],
    "frankfurt am main": ["offenbach", "darmstadt", "wiesbaden", "mainz", "hanau"],
    "stuttgart": ["esslingen", "ludwigsburg", "boeblingen", "heilbronn"],
    "cologne": ["köln", "bonn", "leverkusen", "bergisch gladbach", "troisdorf"],
    "köln": ["bonn", "leverkusen", "bergisch gladbach", "troisdorf"],
    "bonn": ["köln", "cologne", "siegburg", "troisdorf"],
    "dortmund": ["bochum", "essen", "hagen", "unna", "duisburg"],
    "leipzig": ["halle", "markkleeberg", "taucha", "schkeuditz"],
}

app = FastAPI()
default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", default_origins).split(",") if origin.strip()]
default_origin_regex = r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?$"
cors_origin_regex = os.getenv("CORS_ORIGIN_REGEX", default_origin_regex).strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RegisterPayload(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class ApplicationPayload(BaseModel):
    job_id: int


class PreferencesPayload(BaseModel):
    country: str | None = None
    city: str | None = None
    job_title: str | None = None
    work_mode: str | None = None
    job_type: str | None = None
    experience_level: str | None = None


class JobSearchPayload(BaseModel):
    search_text: str | None = None
    country: str | None = None
    city: str | None = None
    job_title: str | None = None
    radius_km: int | None = 20
    work_mode: str | None = None
    job_type: str | None = None
    experience_level: str | None = None
    limit: int = 20
    offset: int = 0


class ChatbotPayload(BaseModel):
    message: str


class ProfileSettingsPayload(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None


class PasswordResetRequestPayload(BaseModel):
    email: EmailStr


class PasswordResetConfirmPayload(BaseModel):
    token: str
    new_password: str


class CvTextSavePayload(BaseModel):
    cv_text: str
    filename: str | None = None


class ChatbotCvActionPayload(BaseModel):
    cv_text: str
    language: str | None = None
    request: str | None = None


class SavedSearchPayload(BaseModel):
    name: str
    search_text: str | None = None
    country: str | None = None
    city: str | None = None
    job_title: str | None = None
    work_mode: str | None = None
    job_type: str | None = None
    experience_level: str | None = None
    radius_km: int | None = 20
    email_notifications_enabled: bool = False


class CareerPlanPayload(BaseModel):
    target_role: str | None = None
    target_city: str | None = None
    language: str | None = None

ALL_VALUES = {"all", "any", "*", "all countries", "all cities"}
PLACEHOLDER_VALUES = {"string", "null", "none", "undefined", "n/a", "-"}
FRESH_DAYS = 7
RADIUS_OPTIONS = {5, 10, 20, 30, 50, 100}
COUNTRY_CITY_SEEDS = {
    "germany": [
        "Berlin",
        "Hamburg",
        "München",
        "Munich",
        "Köln",
        "Cologne",
        "Frankfurt",
        "Frankfurt am Main",
        "Stuttgart",
        "Düsseldorf",
        "Dusseldorf",
        "Dresden",
        "Leipzig",
        "Dortmund",
        "Essen",
        "Bremen",
        "Hannover",
        "Nürnberg",
        "Nuremberg",
        "Wuppertal",
        "Velbert",
        "Heiligenhaus",
        "Ratingen",
        "Bochum",
        "Bonn",
    ]
}

GERMANY_ALIASES = {"germany", "de", "deutschland"}

GERMAN_CITY_COORDS = {
    "dusseldorf": (51.2277, 6.7735),
    "düsseldorf": (51.2277, 6.7735),
    "velbert": (51.3361, 7.0439),
    "heiligenhaus": (51.3280, 6.9696),
    "wuppertal": (51.2562, 7.1508),
    "ratingen": (51.2969, 6.8493),
    "neuss": (51.2042, 6.6879),
    "duisburg": (51.4344, 6.7623),
    "essen": (51.4556, 7.0116),
    "berlin": (52.5200, 13.4050),
    "potsdam": (52.3906, 13.0645),
    "oranienburg": (52.7555, 13.2417),
    "bernau": (52.6798, 13.5871),
    "teltow": (52.4039, 13.2615),
    "hamburg": (53.5511, 9.9937),
    "munich": (48.1351, 11.5820),
    "münchen": (48.1351, 11.5820),
    "frankfurt": (50.1109, 8.6821),
    "frankfurt am main": (50.1109, 8.6821),
    "stuttgart": (48.7758, 9.1829),
    "cologne": (50.9375, 6.9603),
    "köln": (50.9375, 6.9603),
    "bonn": (50.7374, 7.0982),
    "dortmund": (51.5136, 7.4653),
    "leipzig": (51.3397, 12.3731),
    "halle": (51.4969, 11.9688),
    "markkleeberg": (51.2776, 12.3807),
    "taucha": (51.3833, 12.4936),
    "schkeuditz": (51.3966, 12.2219),
}
_GEOCODE_CACHE: dict[str, tuple[float, float] | None] = {}
_LAST_GEOCODE_TS = 0.0
_AUTO_REFRESH_THREAD_STARTED = False
_CHAT_LANG_PREFS: dict[str, str] = {}

RELATED_JOB_TITLES = {
    "nurse": ["nurse", "pflegefachkraft", "pflegehelfer", "krankenschwester", "altenpfleger", "gesundheits und krankenpfleger"],
}

JOB_ROLE_SYNONYMS = {
    "cashier": {
        "cashier", "retail assistant", "sales assistant", "verkaufer", "verkäufer", "kassierer", "einzelhandel", "shop assistant",
    },
    "nurse": {
        "nurse", "pflegefachkraft", "krankenschwester", "pflegehelfer", "krankenpfleger", "altenpfleger",
    },
    "driver": {
        "driver", "fahrer", "delivery driver", "lieferfahrer", "chauffeur", "kurierfahrer",
    },
}


def _norm_city(value: str | None) -> str:
    text = (value or "").strip().lower()
    return text.replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("ß", "ss")


def _build_city_distance_map(search_city: str) -> dict[str, int]:
    base = _norm_city(search_city)
    if not base:
        return {}
    nearby = GERMANY_NEARBY_CITIES.get(base, [])
    mapped = {base: 0}
    for idx, city in enumerate(nearby):
        mapped[_norm_city(city)] = min(100, 8 + (idx * 7))
    return mapped


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (math.sin(d_phi / 2) ** 2) + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(round(r * c))


def _extract_job_city(job: Job) -> str:
    if job.city:
        return _norm_city(job.city)
    if job.location:
        return _norm_city(job.location.split(",")[0])
    return ""


def _distance_km(search_city: str, job: Job) -> int | None:
    if not search_city:
        return None
    search_city_raw = (search_city or "").strip()
    search_key = _norm_city(search_city_raw)
    job_city = _extract_job_city(job)
    if not job_city:
        return None
    job_country = (job.country or "Germany").strip() or "Germany"
    search_coords = _resolve_city_coords(search_key, search_city_raw, "Germany")
    job_coords = _resolve_city_coords(job_city, job.city or job.location or "", job_country)
    if search_coords and job_coords:
        return _haversine_km(search_coords[0], search_coords[1], job_coords[0], job_coords[1])
    city_map = _build_city_distance_map(search_city_raw)
    return city_map.get(job_city)


def _resolve_city_coords(norm_city: str, raw_city: str, country: str) -> tuple[float, float] | None:
    known = GERMAN_CITY_COORDS.get(norm_city)
    if known:
        return known
    return _geocode_city(raw_city, country)


def _job_coordinates(job: Job) -> tuple[float, float] | None:
    city_key = _extract_job_city(job)
    raw_city = job.city or (job.location.split(",")[0].strip() if job.location else "")
    country = (job.country or "Germany").strip() or "Germany"
    return _resolve_city_coords(city_key, raw_city, country)


def _geocode_city(raw_city: str, country: str) -> tuple[float, float] | None:
    global _LAST_GEOCODE_TS
    city = (raw_city or "").strip()
    country_value = (country or "Germany").strip()
    if not city:
        return None
    cache_key = f"{_norm_city(city)}|{_norm_city(country_value)}"
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    try:
        wait_sec = 1.05 - (time.time() - _LAST_GEOCODE_TS)
        if wait_sec > 0:
            time.sleep(wait_sec)
        query = quote_plus(f"{city}, {country_value}")
        url = f"https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q={query}"
        request = Request(
            url,
            headers={
                "User-Agent": "SmartJobPlatform/1.0 (local-dev)",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        _LAST_GEOCODE_TS = time.time()
        if payload and isinstance(payload, list):
            first = payload[0]
            lat = float(first.get("lat"))
            lon = float(first.get("lon"))
            coords = (lat, lon)
            _GEOCODE_CACHE[cache_key] = coords
            return coords
    except Exception:
        _GEOCODE_CACHE[cache_key] = None
        return None

    _GEOCODE_CACHE[cache_key] = None
    return None


def _expand_title_terms(raw_title: str) -> list[str]:
    text = (raw_title or "").strip().lower()
    if not text:
        return []
    expanded = set([text])
    for key, aliases in RELATED_JOB_TITLES.items():
        if key in text:
            expanded.update(aliases)
    return list(expanded)


def _title_filter_terms(raw_title: str) -> list[str]:
    text = (raw_title or "").strip().lower()
    if not text:
        return []
    tokens = [part.strip() for part in text.replace("/", " ").replace("-", " ").split() if part.strip()]
    significant = [token for token in tokens if len(token) >= 3]
    if significant:
        return list(dict.fromkeys(significant))
    return [text]


def _norm_text(value: str) -> str:
    text = (value or "").strip().lower()
    return text.replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("ß", "ss")


def _expanded_relevance_terms(query_text: str) -> set[str]:
    q = _norm_text(query_text)
    if not q:
        return set()
    tokens = {part.strip() for part in re.split(r"[\s,/|-]+", q) if part.strip()}
    expanded = set(tokens)
    expanded.add(q)
    for role_key, synonyms in JOB_ROLE_SYNONYMS.items():
        role_norm = _norm_text(role_key)
        synonym_norms = {_norm_text(item) for item in synonyms}
        if role_norm in q or any(item in q for item in synonym_norms):
            expanded.update(synonym_norms)
            expanded.add(role_norm)
    return {term for term in expanded if len(term) >= 3}


def _job_is_relevant(job: Job, query_text: str) -> bool:
    terms = _expanded_relevance_terms(query_text)
    if not terms:
        return True
    haystack = _norm_text(
        " ".join(
            [
                job.title or "",
                job.description or "",
                job.job_type or "",
                job.work_mode or "",
                job.company or "",
            ]
        )
    )
    title_only = _norm_text(job.title or "")
    # Require at least one strong synonym hit in title OR two hits overall.
    title_hits = sum(1 for term in terms if term in title_only)
    body_hits = sum(1 for term in terms if term in haystack)
    return title_hits >= 1 or body_hits >= 2


SKILL_KEYWORDS = {
    "python",
    "fastapi",
    "flask",
    "django",
    "react",
    "javascript",
    "typescript",
    "sql",
    "docker",
    "aws",
    "node",
    "html",
    "css",
    "machine",
    "learning",
    "nlp",
    "api",
    "backend",
    "frontend",
    "java",
    "spring",
    "kubernetes",
    "git",
    "postgresql",
    "mongodb",
    "redis",
    "graphql",
    "pandas",
    "numpy",
    "tensorflow",
    "pytorch",
    "scikit",
    "linux",
}

SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "ml": "machine learning",
    "ai": "machine learning",
}

ROLE_SKILL_HINTS = {
    "python developer": {"python", "django", "flask", "fastapi", "sql", "docker", "git"},
    "frontend developer": {"javascript", "typescript", "react", "html", "css", "git"},
    "backend developer": {"python", "java", "sql", "docker", "api", "git"},
}

DEMO_EMAIL = "demo@smartjob.local"
DEMO_PASSWORD = "demo1234"
DEMO_NAME = "Demo Presenter"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_user_id_from_auth(authorization: str) -> int:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.removeprefix("Bearer ").strip()
    with SessionLocal() as db:
        auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()
    if not auth_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    return auth_token.user_id


def seed_jobs(db: Session) -> None:
    # Seed jobs removed intentionally: only real provider jobs are shown.
    return


def remove_seed_jobs(db: Session) -> None:
    db.query(Job).filter(Job.source == "seed").delete()
    db.commit()


def is_demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def active_job_sources() -> list[str]:
    mode = (os.getenv("JOB_API_PROVIDER") or "multi").strip().lower()
    if mode in {"scrape", "scraping", "webscrape", "web-scrape"}:
        return SCRAPED_ONLY_SOURCES
    return REAL_JOB_SOURCES


def log_provider_configuration() -> None:
    provider = os.getenv("JOB_API_PROVIDER", "multi").strip().lower()
    adzuna_id_set = bool(os.getenv("ADZUNA_APP_ID", "").strip())
    adzuna_key_set = bool(os.getenv("ADZUNA_APP_KEY", "").strip())
    rapidapi_set = bool(os.getenv("RAPIDAPI_KEY", "").strip())
    jooble_set = bool(os.getenv("JOOBLE_API_KEY", "").strip())
    indeed_feed_set = bool(os.getenv("INDEED_FEED_URL", "").strip())
    logger.warning(
        "Provider config: provider=%s adzuna_id_set=%s adzuna_key_set=%s rapidapi_set=%s jooble_set=%s indeed_feed_set=%s api_keys_configured=%s env_path=%s",
        provider,
        adzuna_id_set,
        adzuna_key_set,
        rapidapi_set,
        jooble_set,
        indeed_feed_set,
        api_keys_configured(),
        str(ENV_PATH),
    )


def ensure_demo_user_and_data(db: Session) -> None:
    if not is_demo_mode_enabled():
        return

    demo_user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if not demo_user:
        demo_user = User(
            name=DEMO_NAME,
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            cv_filename="demo_cv.txt",
            cv_text=(
                "Senior Python developer with FastAPI, SQL, Docker, AWS and React experience. "
                "Built backend APIs and dashboards with measurable impact."
            ),
            preferred_country="Germany",
            preferred_city="Berlin",
            preferred_job_title="Python Developer",
            preferred_work_mode="remote",
            preferred_job_type="full-time",
            preferred_experience_level="mid",
        )
        db.add(demo_user)
        db.commit()
        db.refresh(demo_user)
    else:
        changed = False
        if not (demo_user.cv_text or "").strip():
            demo_user.cv_filename = "demo_cv.txt"
            demo_user.cv_text = (
                "Senior Python developer with FastAPI, SQL, Docker, AWS and React experience. "
                "Built backend APIs and dashboards with measurable impact."
            )
            changed = True
        if not demo_user.preferred_country:
            demo_user.preferred_country = "Germany"
            changed = True
        if not demo_user.preferred_city:
            demo_user.preferred_city = "Berlin"
            changed = True
        if not demo_user.preferred_job_title:
            demo_user.preferred_job_title = "Python Developer"
            changed = True
        if not demo_user.preferred_work_mode:
            demo_user.preferred_work_mode = "remote"
            changed = True
        if changed:
            db.add(demo_user)
            db.commit()


def parse_job_skills(job: Job) -> set[str]:
    base = tokenize(f"{job.title} {job.description or ''}")
    csv_tokens = tokenize((job.skills_csv or "").replace(",", " "))
    return normalize_skill_tokens(base | csv_tokens)


def upsert_fetched_jobs(db: Session, jobs: list[dict]) -> int:
    def _parse_posted_at(value: str | None) -> datetime | None:
        raw = (value or "").strip()
        if not raw:
            return None
        try:
            # Support common ISO/RFC3339 variants.
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None

    saved = 0
    for row in jobs:
        apply_url = (row.get("apply_url") or "").strip()
        if not (apply_url.startswith("http://") or apply_url.startswith("https://")):
            # Hard requirement: only persist real jobs with a real apply link.
            continue
        external_id = (row.get("external_id") or "").strip()
        source = (row.get("source") or "external").strip().lower()
        existing = None
        if external_id:
            existing = (
                db.query(Job)
                .filter(Job.source == source, Job.external_id == external_id)
                .first()
            )

        if not existing:
            existing = Job(source=source, external_id=external_id or None)
            db.add(existing)
            existing.created_at = datetime.utcnow()
        posted_date = _parse_posted_at(row.get("posted_at"))
        if not existing.posted_date:
            existing.posted_date = posted_date or existing.created_at or datetime.utcnow()
        elif posted_date:
            existing.posted_date = min(existing.posted_date, posted_date)
        existing.title = (row.get("title") or "Unknown Role")[:160]
        existing.company = (row.get("company") or "Unknown Company")[:160]
        existing.location = (row.get("location") or "Unknown")[:120]
        existing.country = (row.get("country") or "")[:120] or None
        normalized_city = (row.get("city") or "").strip()
        if not normalized_city and existing.location:
            normalized_city = existing.location.split(",")[0].strip()
        existing.city = normalized_city[:120] or None
        existing.work_mode = (row.get("work_mode") or "")[:40] or None
        existing.job_type = (row.get("job_type") or "")[:40] or None
        existing.apply_url = apply_url[:600] or None
        website_url = (row.get("company_website_url") or "").strip()
        if website_url and not (website_url.startswith("http://") or website_url.startswith("https://")):
            website_url = ""
        if not website_url and apply_url:
            try:
                host = (urlparse(apply_url).hostname or "").strip().lower()
                if host.startswith("www."):
                    host = host[4:]
                if host:
                    website_url = f"https://{host}"
            except Exception:
                website_url = ""
        existing.company_website_url = website_url[:600] or None
        existing.description = (row.get("description") or "")[:4000] or None
        existing.skills_csv = (row.get("skills_csv") or "")[:1200] or None
        existing.last_updated = datetime.utcnow()
        logo_url = (row.get("company_logo_url") or "").strip()
        if logo_url and not (logo_url.startswith("http://") or logo_url.startswith("https://")):
            logo_url = ""
        if not logo_url:
            try:
                base = existing.company_website_url or apply_url
                host = (urlparse(base).hostname or "").strip().lower()
                if host.startswith("www."):
                    host = host[4:]
                if host:
                    logo_url = f"https://logo.clearbit.com/{host}"
            except Exception:
                logo_url = ""
        existing.company_logo_url = logo_url[:600] or None
        saved += 1

    db.commit()
    return saved


def _extract_cv_profile(cv_text: str) -> dict:
    text = (cv_text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lowered = text.lower()

    candidate_name = None
    for idx, line in enumerate(lines[:8]):
        if re.match(r"^[A-Za-z][A-Za-z\s\-']{2,60}$", line) and "@" not in line and not any(ch.isdigit() for ch in line):
            candidate_name = line
            break
        if line.lower().startswith("name:"):
            candidate_name = line.split(":", 1)[1].strip()
            break
        if idx == 0 and len(line.split()) in {2, 3} and "@" not in line:
            candidate_name = line
            break

    keyword_pool = normalize_skill_tokens(tokenize(text))
    skills = sorted([token for token in keyword_pool if token in SKILL_KEYWORDS])[:20]
    exp_summary = ""
    exp_lines = [line for line in lines if any(k in line.lower() for k in ["experience", "years", "worked", "employment"])]
    if exp_lines:
        exp_summary = " ".join(exp_lines[:2])[:300]
    else:
        years = extract_years_experience(text)
        if years > 0:
            exp_summary = f"About {years}+ years of experience."

    preferred_keywords = []
    for phrase in ["nurse", "pflege", "developer", "engineer", "warehouse", "driver", "assistant", "support", "remote", "healthcare"]:
        if phrase in lowered:
            preferred_keywords.append(phrase)
    preferred_keywords.extend(skills[:8])
    preferred_keywords = list(dict.fromkeys(preferred_keywords))[:20]
    return {
        "name": candidate_name,
        "skills": skills,
        "experience_summary": exp_summary,
        "preferred_keywords": preferred_keywords,
    }


def extract_cv_text(file: UploadFile) -> str:
    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    filename = (file.filename or "").lower()
    if filename.endswith(".txt"):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1", errors="ignore")

    if filename.endswith(".pdf"):
        reader = PdfReader(BytesIO(raw))
        content = []
        for page in reader.pages:
            content.append(page.extract_text() or "")
        return "\n".join(content).strip()
    if filename.endswith(".docx"):
        try:
            with zipfile.ZipFile(BytesIO(raw)) as zf:
                xml_bytes = zf.read("word/document.xml")
            root = ET.fromstring(xml_bytes)
            texts = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
            return " ".join(texts).strip()
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read .docx file content")

    if filename.endswith(".xlsx"):
        try:
            with zipfile.ZipFile(BytesIO(raw)) as zf:
                shared_strings: list[str] = []
                if "xl/sharedStrings.xml" in zf.namelist():
                    sst_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                    shared_strings = [
                        node.text or "" for node in sst_root.iter() if node.tag.endswith("}t")
                    ]
                rows_text: list[str] = []
                sheet_names = [name for name in zf.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
                for sheet_name in sheet_names:
                    sheet_root = ET.fromstring(zf.read(sheet_name))
                    for cell in sheet_root.iter():
                        if not cell.tag.endswith("}c"):
                            continue
                        cell_type = cell.attrib.get("t")
                        value_node = next((n for n in cell if n.tag.endswith("}v") and (n.text or "").strip()), None)
                        if value_node is None:
                            continue
                        value_text = (value_node.text or "").strip()
                        if cell_type == "s":
                            idx = int(value_text)
                            if 0 <= idx < len(shared_strings):
                                rows_text.append(shared_strings[idx])
                        else:
                            rows_text.append(value_text)
            return " ".join(rows_text).strip()
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read .xlsx file content")

    if filename.endswith(".doc") or filename.endswith(".xls"):
        # Legacy binary Office files: best-effort text extraction without extra native dependencies.
        text = raw.decode("latin-1", errors="ignore")
        text = re.sub(r"[\x00-\x08\x0b-\x1f]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) >= 20:
            return text
        raise HTTPException(
            status_code=400,
            detail="Legacy .doc/.xls detected but readable text is too limited. Prefer .docx/.xlsx or PDF.",
        )

    raise HTTPException(
        status_code=400,
        detail="Supported CV formats: .txt, .pdf, .doc, .docx, .xls, .xlsx",
    )


def _chatbot_reply(message: str, user: User | None = None, db: Session | None = None) -> str:
    text = (message or "").strip()
    if not text:
        return "Please type a message."

    def _detect_lang(input_text: str) -> str:
        sample = (input_text or "").strip()
        if re.search(r"[\u0600-\u06FF]", sample):
            return "ar"
        lowered = sample.lower()
        romanized_ar_markers = [
            "arabic",
            "3arabi",
            "arabi",
            "ana",
            "mish",
            "mesh",
            "shukran",
            "afwan",
            "mumkin",
            "mumken",
            "wazifa",
            "wazifah",
            "sira",
            "seera",
        ]
        german_markers = [
            "ich",
            "und",
            "der",
            "die",
            "das",
            "für",
            "arbeits",
            "bewerbung",
            "lebenslauf",
            "stellen",
            "hilfe",
            "bitte",
            "danke",
            "interview",
            "fragen",
        ]
        german_romanized_markers = [
            "lebenslauf",
            "bewerbung",
            "stellenanzeige",
            "arbeit",
            "jobsuche",
            "koennen",
            "kannst du",
            "bitte erklaeren",
            "erklaeren",
            "danke",
        ]
        if any(marker in lowered for marker in romanized_ar_markers):
            return "ar"
        if any(marker in lowered for marker in german_markers) or any(ch in sample for ch in "äöüß"):
            return "de"
        if any(marker in lowered for marker in german_romanized_markers):
            return "de"
        return "en"

    def _pick(options: list[str], seed: str) -> str:
        if not options:
            return ""
        idx = abs(hash(seed)) % len(options)
        return options[idx]

    def _detect_requested_reply_lang(lowered_text: str, default_lang: str) -> str:
        wants_ar = bool(
            re.search(
                r"\b(in|speak in|reply in|translate to|explain in)\s+arabic\b|"
                r"\barabic\b|auf arabisch|arabisch|بالعربي|بالعربية",
                lowered_text,
            )
        )
        wants_de = bool(
            re.search(
                r"\b(in|speak in|reply in|translate to|explain in)\s+german\b|"
                r"\bgerman\b|auf deutsch|deutsch",
                lowered_text,
            )
        )
        wants_en = bool(
            re.search(
                r"\b(in|speak in|reply in|translate to|explain in)\s+english\b|"
                r"\benglish\b|auf englisch|بالانجليزي|بالإنجليزي",
                lowered_text,
            )
        )
        if wants_ar:
            return "ar"
        if wants_de:
            return "de"
        if wants_en:
            return "en"
        return default_lang

    def _is_career_plan_request(lowered_text: str) -> bool:
        if "plan" in lowered_text and any(k in lowered_text for k in ["job", "jobs", "career", "role", "skills"]):
            return True
        if any(k in lowered_text for k in ["make me a plan", "make a plan for me", "build me a plan"]):
            return True
        if any(k in lowered_text for k in [
            "career plan", "skills do i need", "how can i become", "roadmap",
            "karriereplan", "welche skills", "wie werde ich",
            "خطة مهنية", "ما المهارات", "كيف أصبح",
        ]):
            return True
        return bool(
            re.search(
                r"\b(30\s*/\s*60\s*/\s*90|30-60-90|30 60 90|"
                r"(30|60|90)[-\s‑]?(day|days|tage|tagen|يوم)|"
                r"(30|60|90)[-\s‑]?day[-\s‑]?plan)\b",
                lowered_text,
            )
        )

    def _intent(lowered_text: str) -> str:
        if any(k in lowered_text for k in [
            "career plan", "90-day", "30/60/90", "skills do i need", "how can i become",
            "karriereplan", "90 tage", "welche skills", "wie werde ich",
            "خطة مهنية", "90 يوم", "ما المهارات", "كيف أصبح",
        ]):
            return "career_plan"
        if any(k in lowered_text for k in ["who are you", "what are you", "who r u", "من انت", "مين انت", "wer bist du"]):
            return "intro"
        if any(k in lowered_text for k in ["cv", "resume", "lebenslauf", "السيرة", "cv "]):
            return "cv"
        if any(k in lowered_text for k in ["interview", "fragen", "questions", "مقابلة", "مقابله", "اسئلة", "أسئلة"]):
            return "interview"
        if any(k in lowered_text for k in ["job", "jobs", "search", "find", "stellen", "arbeit", "وظيفة", "وظائف", "شغل"]):
            return "jobs"
        if any(k in lowered_text for k in [
            "translate",
            "translation",
            "explain in",
            "say this in",
            "how to say",
            "auf deutsch",
            "auf englisch",
            "auf arabisch",
            "بالعربي",
            "بالإنجليزي",
            "بالالماني",
            "بالألماني",
            "ترجم",
            "اشرح",
        ]):
            return "translate"
        return "generic"

    input_lang = _detect_lang(text)
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    lower = text.lower()
    requested_lang = _detect_requested_reply_lang(lower, "")
    user_key = f"user:{user.id}" if user else None
    if user_key and requested_lang in {"en", "de", "ar"}:
        _CHAT_LANG_PREFS[user_key] = requested_lang
    sticky_lang = _CHAT_LANG_PREFS.get(user_key) if user_key else None
    lang = sticky_lang or (requested_lang if requested_lang in {"en", "de", "ar"} else input_lang)
    # Natural override: when user writes clearly in English or Arabic, follow that language directly.
    # Explicit "speak/reply in X" still remains sticky via requested_lang above.
    if requested_lang not in {"en", "de", "ar"}:
        if input_lang in {"en", "ar"} and sticky_lang and sticky_lang != input_lang:
            lang = input_lang
    prefs = get_preferences(user) if user else {}
    pref_title = (prefs.get("job_title") or "").strip()
    pref_city = (prefs.get("city") or "").strip()
    pref_country = (prefs.get("country") or "").strip()
    cv_name = (user.cv_candidate_name or user.name or "").strip() if user else ""
    cv_skills = [item.strip() for item in (user.cv_skills_csv or "").split(",") if item.strip()] if user else []
    cv_keywords = [item.strip() for item in (user.cv_preferred_keywords_csv or "").split(",") if item.strip()] if user else []
    career_intent = _is_career_plan_request(lower)
    if career_intent and requested_lang not in {"en", "de", "ar"} and input_lang in {"en", "ar"}:
        lang = input_lang
    intent = "career_plan" if career_intent else _intent(lower)
    logger.info(
        "chatbot_route intent=%s career_intent=%s input_lang=%s requested_lang=%s selected_lang=%s user_id=%s text=%s",
        intent,
        career_intent,
        input_lang,
        requested_lang,
        lang,
        user.id if user else None,
        text[:180],
    )
    role_match = re.search(r"(as|als|als eine|als ein|wie)\s+([a-zA-Z\u0600-\u06FF\s\-]{3,40})", text, flags=re.IGNORECASE)
    role_from_text = (role_match.group(2).strip() if role_match else "")
    role_need_match = re.search(r"(for|für|fur|in)\s+([a-zA-Z\u0600-\u06FFäöüÄÖÜß\s\-]{2,50})\s+jobs?", text, flags=re.IGNORECASE)
    role_need_from_text = (role_need_match.group(2).strip() if role_need_match else "")
    become_match = re.search(r"(become|werde ich|wie werde ich|اصبح|أصبح)\s+([a-zA-Z\u0600-\u06FFäöüÄÖÜß\s\-]{3,50})", text, flags=re.IGNORECASE)
    become_role = (become_match.group(2).strip() if become_match else "")
    city_match = re.search(r"\b(in|near|bei|um|nähe|في|قرب)\s+([a-zA-Z\u0600-\u06FFäöüÄÖÜß\s\-]{2,40})", text, flags=re.IGNORECASE)
    city_from_text = (city_match.group(2).strip() if city_match else "")
    inferred_role = role_from_text or role_need_from_text or become_role or pref_title or "target role"
    inferred_city = city_from_text or pref_city or pref_country or "preferred location"

    if intent == "career_plan":
        # Natural English career prompts should not be stuck in previous German preference.
        if requested_lang not in {"en", "de", "ar"}:
            if re.search(r"\b(make|plan|career|skills|jobs|role|how can i)\b", lower):
                lang = "en"
        cv_base = (user.cv_text or "").strip() if user else ""
        if len(cv_base) < 20:
            cv_base = (
                f"Target role: {inferred_role}. Preferred location: {inferred_city}. "
                f"Known skills: {', '.join(cv_skills[:10]) if cv_skills else 'not specified'}."
            )
        logger.info(
            "chatbot_route path=career_plan role=%s city=%s lang=%s has_cv=%s",
            inferred_role,
            inferred_city,
            lang,
            bool((user.cv_text or "").strip()) if user else False,
        )
        plan = _build_career_plan(cv_base, inferred_role, inferred_city, language=lang)
        if lang == "de":
            return (
                f"Klar. Hier ist dein realistischer 90-Tage-Plan für {inferred_role} in {inferred_city}.\n\n"
                f"Fokus: {plan.get('summary')}\n"
                f"Top-Skill-Gaps: {' | '.join((plan.get('gaps') or [])[:3])}\n"
                f"30 Tage: {'; '.join((plan.get('plan_30') or [])[:3])}\n"
                f"60 Tage: {'; '.join((plan.get('plan_60') or [])[:3])}\n"
                f"90 Tage: {'; '.join((plan.get('plan_90') or [])[:3])}"
            )
        if lang == "ar":
            return (
                f"أكيد. هذه خطة مهنية واقعية لمدة 90 يومًا لوظيفة {inferred_role} في {inferred_city}.\n\n"
                f"التركيز: {plan.get('summary')}\n"
                f"أهم الفجوات: {' | '.join((plan.get('gaps') or [])[:3])}\n"
                f"30 يوم: {'؛ '.join((plan.get('plan_30') or [])[:3])}\n"
                f"60 يوم: {'؛ '.join((plan.get('plan_60') or [])[:3])}\n"
                f"90 يوم: {'؛ '.join((plan.get('plan_90') or [])[:3])}"
            )
        return (
            f"Absolutely. Here’s a practical 90-day career plan for {inferred_role} in {inferred_city}.\n\n"
            f"Focus: {plan.get('summary')}\n"
            f"Top skill gaps: {' | '.join((plan.get('gaps') or [])[:3])}\n"
            f"30 days: {'; '.join((plan.get('plan_30') or [])[:3])}\n"
            f"60 days: {'; '.join((plan.get('plan_60') or [])[:3])}\n"
            f"90 days: {'; '.join((plan.get('plan_90') or [])[:3])}"
        )

    def _rule_based_reply() -> str:
        focus_en = pref_title or "your target role"
        place_en = pref_city or pref_country or "your preferred location"
        focus_de = pref_title or "deine Zielrolle"
        place_de = pref_city or pref_country or "deinem Wunschort"
        focus_ar = pref_title or "المسمى المستهدف"
        place_ar = pref_city or pref_country or "الموقع المفضل"
        messages = {
            "en": {
                "intro": [
                    "I am your Smart Job assistant. I can help with job search, CV tips, and interview prep.",
                    "I am your job assistant. I can help you find roles, improve your CV, and prepare for interviews.",
                ],
                "cv": [
                    "For stronger CV matches, add a clear Skills section and 3 measurable achievements in Experience.",
                    "Keep your CV short and specific: skills first, then experience with measurable results.",
                ],
                "interview": [
                    "Use STAR answers: Situation, Task, Action, Result. Prepare 3 short stories with outcomes.",
                    "For interviews, practice concise STAR examples and include numbers when possible.",
                ],
                "jobs": [
                    (
                        f"Hi {cv_name}, I found your CV. Let's search for {(role_from_text or focus_en)} in "
                        f"{(city_from_text or place_en)}. "
                        f"Based on your CV, highlight skills like {', '.join(cv_skills[:3]) or 'your strongest skills'}."
                    ),
                    f"We can target {(role_from_text or focus_en)} in {(city_from_text or place_en)}. If results are low, widen city/radius and simplify filters.",
                    f"Next step: open Jobs search with title={(role_from_text or focus_en)} and city={(city_from_text or place_en)}; old valid jobs can still match.",
                ],
                "translate": [
                    "Sure. Share the exact sentence, and I will explain it in Arabic, German, or English.",
                    "Yes. Send the text and your target language, and I will give a short practical explanation.",
                ],
                "generic": [
                    "I can help with jobs, CV improvement, and interview prep. Tell me your goal.",
                    "Share your target role and city, and I will suggest a focused next step.",
                ],
            },
            "de": {
                "intro": [
                    "Ich bin dein Smart-Job-Assistent. Ich helfe bei Jobsuche, Lebenslauf und Interviewvorbereitung.",
                    "Ich bin dein Job-Assistent. Ich unterstütze dich bei Stellen, CV-Optimierung und Interviewtipps.",
                ],
                "cv": [
                    "Für bessere Treffer: klare Skills-Sektion und 3 messbare Erfolge im Abschnitt Erfahrung.",
                    "Halte den Lebenslauf kurz und konkret: zuerst Skills, dann Erfahrung mit messbaren Ergebnissen.",
                ],
                "interview": [
                    "Nutze STAR-Antworten: Situation, Aufgabe, Aktion, Ergebnis. Übe 3 kurze Beispiele.",
                    "Für Interviews: kurze STAR-Beispiele vorbereiten und wenn möglich Zahlen nennen.",
                ],
                "jobs": [
                    (
                        f"Hi {cv_name}, ich habe deinen Lebenslauf gefunden. Wir suchen nach {(role_from_text or focus_de)} "
                        f"in {(city_from_text or place_de)}. Betone Skills wie {', '.join(cv_skills[:3]) or 'deine stärksten Skills'}."
                    ),
                    f"Wir suchen {(role_from_text or focus_de)} in {(city_from_text or place_de)}. Wenn wenig kommt, Stadt/Radius erweitern und Filter vereinfachen.",
                    f"Nächster Schritt: Jobsuche mit Titel={(role_from_text or focus_de)} und Stadt={(city_from_text or place_de)} starten.",
                ],
                "translate": [
                    "Gerne. Schick den genauen Satz, dann erkläre ich ihn auf Arabisch, Deutsch oder Englisch.",
                    "Ja. Sende den Text und die Zielsprache, ich antworte kurz und praktisch.",
                ],
                "generic": [
                    "Ich helfe bei Jobsuche, Lebenslauf und Interviewvorbereitung. Was ist dein Ziel?",
                    "Nenne mir Rolle und Stadt, dann schlage ich den nächsten sinnvollen Schritt vor.",
                ],
            },
            "ar": {
                "intro": [
                    "أنا مساعدك في منصة الوظائف الذكية. أساعدك في البحث عن وظيفة وتحسين السيرة والاستعداد للمقابلة.",
                    "أنا مساعدك المهني. أقدر أساعدك في الوظائف، السيرة الذاتية، ونصائح المقابلات.",
                ],
                "cv": [
                    "لتحسين المطابقة: أضف قسم مهارات واضح و3 إنجازات قابلة للقياس في الخبرة.",
                    "خلّي السيرة مختصرة وواضحة: المهارات أولاً ثم خبرات مع نتائج رقمية.",
                ],
                "interview": [
                    "استخدم طريقة STAR: الموقف، المهمة، الإجراء، النتيجة. حضّر 3 أمثلة قصيرة.",
                    "للمقابلة: تدرب على أمثلة STAR مختصرة واذكر أرقامًا عند الإمكان.",
                ],
                "jobs": [
                    (
                        f"مرحبًا {cv_name}، وجدت سيرتك الذاتية. خلّينا نبحث عن {(role_from_text or focus_ar)} في "
                        f"{(city_from_text or place_ar)}. ركّز على مهارات مثل {', '.join(cv_skills[:3]) or 'أقوى مهاراتك'}."
                    ),
                    f"نقدر نستهدف {(role_from_text or focus_ar)} في {(city_from_text or place_ar)}. عند قلة النتائج، خفّف الفلاتر ووسّع المدينة/المسافة.",
                    f"الخطوة التالية: شغّل بحث الوظائف بعنوان={(role_from_text or focus_ar)} ومدينة={(city_from_text or place_ar)}.",
                ],
                "translate": [
                    "أكيد. أرسل الجملة المطلوبة وحدد اللغة الهدف، وأشرحها لك بشكل مختصر.",
                    "تمام. اكتب النص واللغة المطلوبة (عربي/ألماني/إنجليزي) وسأعطيك شرحًا عمليًا سريعًا.",
                ],
                "generic": [
                    "أقدر أساعدك في الوظائف، تحسين السيرة، والاستعداد للمقابلات. ما هدفك الآن؟",
                    "اكتب المسمى والمدينة، وسأعطيك خطوة عملية سريعة للبحث.",
                ],
            },
        }
        logger.info("chatbot_route path=rule_based intent=%s lang=%s", intent, lang)
        lang_messages = messages.get(lang, messages["en"])
        choices = lang_messages.get(intent) or lang_messages["generic"]
        return _pick(choices, f"{lang}:{intent}:{text}") or choices[0]

    if not api_key:
        return _rule_based_reply()

    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    user_pref = get_preferences(user) if user else {}
    cv_hint = "yes" if user and (user.cv_text or "").strip() else "no"
    system_prompt = (
        "You are Smart Job Platform assistant. Be concise and practical. "
        "Reply strictly in one language only: same language as the user's message (English, German, or Arabic). "
        "If the user explicitly asks for another reply language, use the requested language. "
        "Do not switch languages in the same response. "
        "Keep answers lightweight and job-focused. "
        "Help users with job search, CV improvement, interview prep, and platform actions."
    )
    user_prompt = (
        f"User message: {text}\n"
        f"User has CV uploaded: {cv_hint}\n"
        f"User preferences: {json.dumps(user_pref)}\n"
        f"CV name: {cv_name or 'unknown'}\n"
        f"CV skills: {', '.join(cv_skills[:12])}\n"
        f"CV keywords: {', '.join(cv_keywords[:12])}"
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 220,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=25) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        return content or _rule_based_reply()
    except Exception as exc:
        logger.warning("chatbot_failed error=%s", exc)
        return _rule_based_reply()


def tokenize(text_value: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text_value)
    return {token for token in cleaned.split() if len(token) > 1}


def extract_sections(cv_text: str) -> dict:
    sections = {"skills": "", "experience": "", "education": "", "projects": ""}
    current = None
    headers = {
        "skills": "skills",
        "technical skills": "skills",
        "experience": "experience",
        "work experience": "experience",
        "education": "education",
        "projects": "projects",
    }
    for line in cv_text.splitlines():
        name = line.strip().lower().rstrip(":")
        if name in headers:
            current = headers[name]
            continue
        if current and line.strip():
            sections[current] += f" {line.strip()}"
    return sections


def extract_years_experience(cv_text: str) -> int:
    tokens = tokenize(cv_text)
    years = 0
    for token in tokens:
        if token.isdigit():
            value = int(token)
            if 0 < value <= 40:
                years = max(years, value)
    return years


def normalize_skill_tokens(tokens: set[str]) -> set[str]:
    normalized = set(tokens)
    for token in list(tokens):
        if token in SKILL_ALIASES:
            normalized.add(SKILL_ALIASES[token])
    normalized.discard("machine")
    normalized.discard("learning")
    text_blob = " ".join(tokens)
    if "machine" in tokens and "learning" in tokens:
        normalized.add("machine learning")
    if "node" in tokens and "js" in tokens:
        normalized.add("node")
    return normalized


def get_role_skill_hints(job: Job) -> set[str]:
    title = job.title.lower()
    hints = set()
    for role, skills in ROLE_SKILL_HINTS.items():
        if role in title:
            hints.update(skills)
    if not hints:
        hints.update({"git", "sql"})
    return hints


def build_cv_improvement_tips(job: Job, score: int, missing_skills: list[str]) -> list[str]:
    tips = []
    top_missing = missing_skills[:2]
    if top_missing:
        tips.append(
            f"Add a dedicated 'Technical Skills' section and include: {', '.join(top_missing)}."
        )
    else:
        tips.append(
            "Strengthen your 'Technical Skills' section with job-relevant tools and frameworks."
        )

    if score < 35:
        tips.append(
            f"Add 2 bullet points under Experience for {job.title} keywords, each with measurable impact (for example: reduced API latency by 30%)."
        )
    elif score < 60:
        tips.append(
            f"Improve role alignment by adding one project entry tailored to {job.title}, with stack + outcomes."
        )
    else:
        tips.append(
            "Increase ATS relevance by repeating the most important role keywords naturally across Skills and Experience."
        )

    third_skill = missing_skills[2] if len(missing_skills) > 2 else "the role stack"
    tips.append(
        f"Add one short project case study showing practical use of {third_skill} with clear results and timeline."
    )

    return tips[:3]


def compute_match(job: Job, cv_text: str, preferences: dict | None = None) -> dict:
    cv_tokens = tokenize(cv_text)
    sections = extract_sections(cv_text)
    skills_tokens = tokenize(sections["skills"])
    exp_tokens = tokenize(sections["experience"])
    project_tokens = tokenize(sections["projects"])
    weighted_cv = normalize_skill_tokens(cv_tokens | skills_tokens | exp_tokens | project_tokens)
    job_tokens = tokenize(f"{job.title} {job.company} {job.location} {job.description or ''}")
    years_experience = extract_years_experience(cv_text)

    cv_skill_hits = sorted(token for token in weighted_cv if token in SKILL_KEYWORDS)
    overlap = sorted(weighted_cv & job_tokens)
    overlap_score = min(len(overlap) * 8, 48)
    skill_score = min(len(cv_skill_hits) * 8, 32)
    title_bonus = 12 if tokenize(job.title) & (skills_tokens | exp_tokens) else 0
    project_bonus = 8 if tokenize(job.title) & project_tokens else 0
    experience_bonus = min(years_experience * 2, 12)
    skill_score_total = min(overlap_score + skill_score + title_bonus + project_bonus + experience_bonus + 4, 100)
    preference_alignment = compute_preference_alignment(job, preferences)
    preference_score = preference_alignment["score"]
    score = min(int((skill_score_total * 0.75) + (preference_score * 0.25)), 100)

    role_hints = get_role_skill_hints(job)
    job_skill_tokens = parse_job_skills(job)
    expected_skills = sorted(role_hints | {token for token in job_skill_tokens if token in SKILL_KEYWORDS})
    matched_skills = sorted(skill for skill in expected_skills if skill in weighted_cv)
    missing_skills = sorted(skill for skill in expected_skills if skill not in weighted_cv)
    cv_improvement_tips = build_cv_improvement_tips(job, score, missing_skills)

    reasons = []
    if cv_skill_hits:
        reasons.append(f"CV skills matched: {', '.join(cv_skill_hits[:5])}")
    if overlap:
        reasons.append(f"Keyword overlap with role: {', '.join(overlap[:5])}")
    if years_experience > 0:
        reasons.append(f"Experience signal detected: about {years_experience}+ years.")
    if missing_skills:
        reasons.append(f"Top missing skills: {', '.join(missing_skills[:4])}")
    reasons.extend(preference_alignment["reasons"])
    if not reasons:
        reasons.append("General profile alignment based on available text.")

    posted_days = None
    posted_label = "Recently posted"
    posted_at = job.posted_date or job.created_at
    if posted_at:
        try:
            delta = datetime.utcnow() - posted_at
            posted_days = max(delta.days, 0)
            posted_hours = max(int(delta.total_seconds() // 3600), 0)
            if posted_hours < 1:
                posted_label = "Posted today"
            elif posted_days == 0:
                posted_label = "Posted today"
            elif posted_days == 1:
                posted_label = "Posted 1 day ago"
            elif posted_days < 7:
                posted_label = f"Posted {posted_days} days ago"
            elif posted_days < 14:
                posted_label = "Posted 1 week ago"
            else:
                posted_label = f"Posted {round(posted_days / 7)} weeks ago"
        except Exception:
            posted_days = None
            posted_label = "Recently posted"
    distance_km = _distance_km((preferences or {}).get("city") or "", job)
    distance_label = f"{distance_km} km away" if distance_km is not None else None
    coords = _job_coordinates(job)
    company_logo_url = (job.company_logo_url or "").strip() or None
    if not company_logo_url and (job.company_website_url or job.apply_url):
        try:
            base = job.company_website_url or job.apply_url
            host = (urlparse(base).hostname or "").strip().lower()
            if host:
                if host.startswith("www."):
                    host = host[4:]
                company_logo_url = f"https://logo.clearbit.com/{host}"
        except Exception:
            company_logo_url = None
    logo_click_url = (job.company_website_url or job.apply_url or "").strip() or None

    return {
        "job_id": job.id,
        "source": job.source,
        "external_id": job.external_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "country": job.country,
        "city": job.city,
        "work_mode": job.work_mode,
        "job_type": job.job_type,
        "apply_url": job.apply_url,
        "company_website_url": job.company_website_url,
        "logo_click_url": logo_click_url,
        "company_logo_url": company_logo_url,
        "company_initials": "".join([part[0] for part in (job.company or "").split()[:2]]).upper() or "CO",
        "posted_days": posted_days,
        "posted_label": posted_label,
        "posted_date": (posted_at.isoformat() if posted_at else None),
        "last_updated": (job.last_updated.isoformat() if job.last_updated else None),
        "distance_km": distance_km,
        "distance_label": distance_label,
        "latitude": coords[0] if coords else None,
        "longitude": coords[1] if coords else None,
        "score": score,
        "skill_score": skill_score_total,
        "preference_score": preference_score,
        "reasons": reasons,
        "matched_skills": matched_skills[:8],
        "missing_skills": missing_skills[:5],
        "cv_improvement_tips": cv_improvement_tips,
        "preference_reasons": preference_alignment["reasons"],
        "preference_matched": preference_alignment["matched"],
        "preference_not_matched": preference_alignment["not_matched"],
    }


def _rank_key(item: dict) -> tuple[int, str, str]:
    return (
        int(item.get("score") or 0),
        item.get("last_updated") or "",
        item.get("posted_date") or "",
    )


def get_current_user(authorization: str, db: Session) -> User:
    user_id = get_user_id_from_auth(authorization)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_optional_current_user(authorization: str, db: Session) -> User | None:
    if not authorization.startswith("Bearer "):
        return None
    return get_current_user(authorization, db)


def get_cv_status(user: User) -> dict:
    return {
        "has_cv": bool((user.cv_text or "").strip()),
        "cv_filename": user.cv_filename,
        "cv_chars": len((user.cv_text or "").strip()),
        "candidate_name": user.cv_candidate_name,
        "skills": [token.strip() for token in (user.cv_skills_csv or "").split(",") if token.strip()],
        "experience_summary": user.cv_experience_summary,
        "preferred_keywords": [token.strip() for token in (user.cv_preferred_keywords_csv or "").split(",") if token.strip()],
    }


def get_preferences(user: User) -> dict:
    return {
        "country": user.preferred_country,
        "city": user.preferred_city,
        "job_title": user.preferred_job_title,
        "work_mode": user.preferred_work_mode,
        "job_type": user.preferred_job_type,
        "experience_level": user.preferred_experience_level,
    }


def _is_email_configured() -> bool:
    return bool((os.getenv("SMTP_HOST") or "").strip() and (os.getenv("SMTP_FROM") or "").strip())


def _send_reset_email(target_email: str, reset_link: str) -> tuple[bool, str]:
    if not _is_email_configured():
        return False, "Email provider is not configured. Password reset link generated for development only."

    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    smtp_port = int((os.getenv("SMTP_PORT") or "587").strip() or "587")
    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or "").strip()
    smtp_from = (os.getenv("SMTP_FROM") or "").strip()
    use_tls = (os.getenv("SMTP_USE_TLS") or "1").strip().lower() in {"1", "true", "yes", "on"}

    msg = EmailMessage()
    msg["Subject"] = "Smart Job Platform Password Reset"
    msg["From"] = smtp_from
    msg["To"] = target_email
    msg.set_content(
        "We received a password reset request.\n\n"
        f"Reset your password using this link:\n{reset_link}\n\n"
        "If you did not request this, you can ignore this email."
    )
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            if use_tls:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True, "Password reset email sent."
    except Exception as exc:
        logger.warning("password_reset_email_failed error=%s", exc)
        return False, "Email delivery failed safely. Please contact support or try again later."


def _send_basic_email(target_email: str, subject: str, body: str) -> tuple[bool, str]:
    if not _is_email_configured():
        return False, "Email provider not configured."
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    smtp_port = int((os.getenv("SMTP_PORT") or "587").strip() or "587")
    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_password = (os.getenv("SMTP_PASSWORD") or "").strip()
    smtp_from = (os.getenv("SMTP_FROM") or "").strip()
    use_tls = (os.getenv("SMTP_USE_TLS") or "1").strip().lower() in {"1", "true", "yes", "on"}
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = target_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            if use_tls:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True, "sent"
    except Exception as exc:
        logger.warning("email_send_failed error=%s", exc)
        return False, "failed"


def _generate_cv_outputs(cv_text: str, language: str = "en", request_text: str = "") -> dict:
    text = (cv_text or "").strip()
    lang = (language or "en").strip().lower()
    request_lower = (request_text or "").strip().lower()
    if any(token in request_lower for token in ["german", "deutsch", "auf deutsch", "ins deutsche"]):
        lang = "de"
    elif any(token in request_lower for token in ["english", "englisch", "in english", "auf englisch"]):
        lang = "en"
    elif any(token in request_lower for token in ["arabic", "arabisch", "بالعربي", "بالعربية", "عربي"]):
        lang = "ar"
    if lang not in {"en", "de", "ar"}:
        lang = "en"
    profile = _extract_cv_profile(text)
    skills = profile.get("skills") or []
    exp_summary = profile.get("experience_summary") or ""
    name = profile.get("name") or "Candidate"
    key = (os.getenv("OPENAI_API_KEY") or "").strip()

    fallback = {
        "en": {
            "summary": f"{name} profile summary: {exp_summary or 'General professional background'} Skills: {', '.join(skills[:8]) or 'Not clearly listed'}.",
            "tips": [
                "Fix grammar and verb tense consistency across all bullet points.",
                "Use measurable achievements with realistic metrics where available.",
                "Add ATS-friendly keywords that match target job descriptions naturally.",
                "Use clear sections: Summary, Skills, Experience, Education, Certifications.",
            ],
        },
        "de": {
            "summary": f"Profil-Zusammenfassung von {name}: {exp_summary or 'Allgemeiner beruflicher Hintergrund'} Skills: {', '.join(skills[:8]) or 'Nicht klar aufgeführt'}.",
            "tips": [
                "Korrigiere Grammatik und Zeitformen in allen Stichpunkten.",
                "Formuliere realistische, messbare Ergebnisse pro Erfahrung.",
                "Ergänze ATS-relevante Schlüsselwörter passend zur Zielstelle.",
                "Nutze klare Struktur: Profil, Skills, Erfahrung, Ausbildung, Zertifikate.",
            ],
        },
        "ar": {
            "summary": f"ملخص ملف {name}: {exp_summary or 'خلفية مهنية عامة'} المهارات: {', '.join(skills[:8]) or 'غير واضحة بشكل كافٍ'}.",
            "tips": [
                "صحّح القواعد والإملاء وتوحيد زمن الأفعال في كامل السيرة.",
                "استخدم صياغة مهنية أقوى مع إنجازات واقعية قابلة للقياس.",
                "أضف كلمات مفتاحية مناسبة لأنظمة ATS بشكل طبيعي.",
                "نظّم السيرة إلى: ملخص، مهارات، خبرات، تعليم، شهادات.",
            ],
        },
    }

    if not key:
        action_hint = "professional_cv"
        if any(token in request_lower for token in ["fix grammar", "grammar", "spelling", "correct grammar", "korrig", "إملاء", "قواعد"]):
            action_hint = "grammar"
        elif any(token in request_lower for token in ["rewrite", "experience", "better", "stronger", "neu formul", "إعادة صياغة"]):
            action_hint = "rewrite_experience"
        elif any(token in request_lower for token in ["translate", "übersetz", "ترجم"]):
            action_hint = "translate"

        summary_prefix = {
            "grammar": "Grammar/spelling-focused review:",
            "rewrite_experience": "Experience rewrite-focused review:",
            "translate": "Translation-focused review:",
            "professional_cv": "Professional CV improvement review:",
        }.get(action_hint, "Professional CV improvement review:")
        improved = (
            f"{name}\n\n"
            f"Professional Summary\n{summary_prefix} {fallback[lang]['summary']}\n\n"
            "Core Skills\n- " + ("\n- ".join(skills[:12]) if skills else "Add your most relevant skills here.") + "\n\n"
            "Experience\n- Add role, company, dates, and 3 quantified achievements per role.\n\n"
            "Education\n- Add degree, institution, graduation year.\n"
        )
        return {"summary": fallback[lang]["summary"], "suggestions": fallback[lang]["tips"], "improved_cv_text": improved}

    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    prompt = (
        "You are an expert CV assistant for real-world hiring. "
        "Return strict JSON with keys: summary, suggestions, improved_cv_text. "
        "summary: 2-4 sentences; suggestions: 4-8 concise points; improved_cv_text: full rewritten CV.\n"
        "Quality requirements:\n"
        "- Correct grammar and spelling.\n"
        "- Improve wording professionally.\n"
        "- Make CV ATS-friendly with natural keywords and clean sectioning.\n"
        "- Rewrite weak experience bullets into stronger professional language.\n"
        "- Keep content realistic: do NOT invent jobs, degrees, certifications, dates, or exaggerated achievements.\n"
        "- If information is missing, keep placeholders neutral like '[add metric]' rather than fabricating.\n"
        "- If user asks translation, preserve original meaning and improve language quality.\n"
        f"Target language: {lang}. Follow request exactly.\n"
        f"User request: {request_text or 'Make my CV more professional, fix grammar, and improve ATS quality.'}\n"
        f"Original CV:\n{text[:12000]}"
    )
    try:
        req = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(
                {
                    "model": model,
                    "temperature": 0.2,
                    "max_tokens": 1200,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        with urlopen(req, timeout=35) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}").strip()
        parsed = json.loads(content)
        return {
            "summary": (parsed.get("summary") or fallback[lang]["summary"])[:2000],
            "suggestions": parsed.get("suggestions") or fallback[lang]["tips"],
            "improved_cv_text": (parsed.get("improved_cv_text") or "").strip() or text,
        }
    except Exception as exc:
        logger.warning("cv_generate_failed error=%s", exc)
        improved = (
            f"{name}\n\nProfessional Summary\n{fallback[lang]['summary']}\n\n"
            "Core Skills\n- " + ("\n- ".join(skills[:12]) if skills else "Add your most relevant skills here.")
        )
        return {"summary": fallback[lang]["summary"], "suggestions": fallback[lang]["tips"], "improved_cv_text": improved}


def _build_career_plan(cv_text: str, target_role: str, target_city: str, language: str = "en") -> dict:
    lang = (language or "en").strip().lower()
    if lang not in {"en", "de", "ar"}:
        lang = "en"
    role = (target_role or "").strip() or "your target role"
    city = (target_city or "").strip() or "your preferred location"
    profile = _extract_cv_profile(cv_text or "")
    skills = profile.get("skills") or []
    key = (os.getenv("OPENAI_API_KEY") or "").strip()

    fallback = {
        "en": {
            "summary": f"Career focus: {role} in {city}.",
            "gaps": [
                "Clarify role-specific achievements with measurable outcomes.",
                "Strengthen ATS keywords for target role descriptions.",
                "Add one portfolio/project example aligned to the role.",
            ],
            "plan_30": [
                "Refine CV headline and summary for target role.",
                "Update 3 experience bullets with concrete impact.",
                "Apply to 15 targeted jobs and track responses.",
            ],
            "plan_60": [
                "Close top 2 skill gaps via short practical projects.",
                "Practice 10 interview questions using STAR format.",
                "Network with 10 relevant professionals/recruiters.",
            ],
            "plan_90": [
                "Publish/complete one role-relevant project proof.",
                "Iterate CV using interview/application feedback.",
                "Target second-wave applications to best-fit companies.",
            ],
        },
        "de": {
            "summary": f"Karrierefokus: {role} in {city}.",
            "gaps": [
                "Rollenrelevante Erfolge klarer und messbar formulieren.",
                "ATS-Schlüsselwörter für Zielrolle gezielt ergänzen.",
                "Ein passendes Projekt/Portfolio-Beispiel hinzufügen.",
            ],
            "plan_30": [
                "CV-Überschrift und Profil auf Zielrolle zuschneiden.",
                "3 Erfahrungs-Stichpunkte mit konkreter Wirkung verbessern.",
                "15 passende Stellen bewerben und Rückmeldungen tracken.",
            ],
            "plan_60": [
                "Top-2 Skill-Gaps mit Mini-Projekten schließen.",
                "10 Interviewfragen im STAR-Format üben.",
                "Mit 10 relevanten Kontakten/Recruitern vernetzen.",
            ],
            "plan_90": [
                "Ein rollenrelevantes Projekt als Nachweis veröffentlichen.",
                "CV anhand Bewerbungs-/Interviewfeedback optimieren.",
                "Zweite Bewerbungsrunde bei Top-Unternehmen starten.",
            ],
        },
        "ar": {
            "summary": f"التركيز المهني: {role} في {city}.",
            "gaps": [
                "توضيح الإنجازات المرتبطة بالدور بصياغة قابلة للقياس.",
                "تعزيز كلمات ATS المناسبة للوظيفة المستهدفة.",
                "إضافة مشروع/نماذج أعمال مرتبطة بالدور.",
            ],
            "plan_30": [
                "تحسين عنوان السيرة والملخص ليتوافقا مع الدور المستهدف.",
                "تطوير 3 نقاط خبرة بأثر مهني واضح وقابل للقياس.",
                "التقديم على 15 وظيفة مناسبة وتتبع النتائج.",
            ],
            "plan_60": [
                "سد أهم فجوتين مهاريتين عبر مشاريع عملية قصيرة.",
                "التدرّب على 10 أسئلة مقابلة بطريقة STAR.",
                "بناء شبكة مع 10 أشخاص/مجندين في نفس المجال.",
            ],
            "plan_90": [
                "إنجاز مشروع قوي يثبت الجاهزية للدور.",
                "تحديث السيرة بناءً على ملاحظات المقابلات والتقديم.",
                "إطلاق موجة تقديم ثانية للشركات الأنسب.",
            ],
        },
    }
    if not key:
        return fallback[lang]

    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    prompt = (
        "You are a realistic career coach. Return strict JSON with keys: summary, gaps, plan_30, plan_60, plan_90.\n"
        "Rules: no fake claims, no exaggeration, practical and specific actions.\n"
        f"Language: {lang}\nTarget role: {role}\nTarget city: {city}\n"
        f"Current CV skills: {', '.join(skills[:20])}\nCV text:\n{(cv_text or '')[:10000]}"
    )
    try:
        req = Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(
                {
                    "model": model,
                    "temperature": 0.2,
                    "max_tokens": 900,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        with urlopen(req, timeout=35) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
        content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}").strip()
        parsed = json.loads(content)
        return {
            "summary": parsed.get("summary") or fallback[lang]["summary"],
            "gaps": parsed.get("gaps") or fallback[lang]["gaps"],
            "plan_30": parsed.get("plan_30") or fallback[lang]["plan_30"],
            "plan_60": parsed.get("plan_60") or fallback[lang]["plan_60"],
            "plan_90": parsed.get("plan_90") or fallback[lang]["plan_90"],
        }
    except Exception as exc:
        logger.warning("career_plan_failed error=%s", exc)
        return fallback[lang]


def merge_search_preferences(base: dict, payload: JobSearchPayload | None) -> dict:
    merged = dict(base)
    if not payload:
        payload = None
    if payload and payload.search_text is not None:
        merged["search_text"] = payload.search_text
    if payload and payload.country is not None:
        merged["country"] = payload.country
    if payload and payload.city is not None:
        merged["city"] = payload.city
    if payload and payload.job_title is not None:
        merged["job_title"] = payload.job_title
    if payload and payload.radius_km is not None:
        merged["radius_km"] = payload.radius_km
    if payload and payload.work_mode is not None:
        merged["work_mode"] = payload.work_mode
    if payload and payload.job_type is not None:
        merged["job_type"] = payload.job_type
    if payload and payload.experience_level is not None:
        merged["experience_level"] = payload.experience_level
    for key in ["search_text", "country", "city", "job_title", "work_mode", "job_type", "experience_level"]:
        value = str(merged.get(key) or "").strip()
        if value.lower() in PLACEHOLDER_VALUES:
            merged[key] = ""
        else:
            merged[key] = value
    return merged


def infer_job_work_mode(job: Job) -> str | None:
    blob = f"{job.title} {job.location} {job.description or ''}".lower()
    if "hybrid" in blob:
        return "hybrid"
    if "remote" in blob:
        return "remote"
    if any(token in blob for token in ["on-site", "onsite", "office"]):
        return "on-site"
    return None


def infer_job_type(job: Job) -> str | None:
    blob = f"{job.title} {job.description or ''}".lower()
    if "part-time" in blob or "part time" in blob:
        return "part-time"
    if "contract" in blob:
        return "contract"
    if "intern" in blob:
        return "internship"
    if "full-time" in blob or "full time" in blob:
        return "full-time"
    return None


def infer_experience_level(job: Job) -> str | None:
    blob = f"{job.title} {job.description or ''}".lower()
    if any(token in blob for token in ["junior", "entry level", "graduate"]):
        return "junior"
    if any(token in blob for token in ["senior", "lead", "principal"]):
        return "senior"
    if any(token in blob for token in ["mid", "intermediate"]):
        return "mid"
    return None


def compute_preference_alignment(job: Job, preferences: dict | None) -> dict:
    if not preferences:
        return {"score": 0, "reasons": ["No job preferences set yet."], "matched": [], "not_matched": []}

    reasons = []
    matched = []
    not_matched = []
    score = 0
    location_blob = f"{job.location} {job.description or ''}".lower()

    country = (preferences.get("country") or "").strip().lower()
    city = (preferences.get("city") or "").strip().lower()
    work_mode = (preferences.get("work_mode") or "").strip().lower()
    job_type = (preferences.get("job_type") or "").strip().lower()
    exp_level = (preferences.get("experience_level") or "").strip().lower()
    preferred_title = (preferences.get("job_title") or "").strip().lower()

    if country:
        if country in location_blob:
            score += 8
            matched.append(f"Country matches ({preferences['country']})")
        else:
            not_matched.append(f"Country mismatch (wanted {preferences['country']})")
    if city:
        if city in location_blob:
            score += 8
            matched.append(f"City matches ({preferences['city']})")
        else:
            not_matched.append(f"City mismatch (wanted {preferences['city']})")
    if preferred_title:
        if preferred_title in job.title.lower():
            score += 8
            matched.append(f"Job title matches ({preferences['job_title']})")
        else:
            not_matched.append(f"Job title mismatch (wanted {preferences['job_title']})")
    if work_mode:
        detected_mode = infer_job_work_mode(job)
        if detected_mode == work_mode:
            score += 10
            matched.append(f"Work mode matches ({work_mode})")
        elif detected_mode:
            not_matched.append(f"Work mode mismatch (job is {detected_mode}, wanted {work_mode})")
        else:
            not_matched.append("Work mode not specified in this job post")
    if job_type:
        detected_type = infer_job_type(job)
        if detected_type == job_type:
            score += 7
            matched.append(f"Job type matches ({job_type})")
        elif detected_type:
            not_matched.append(f"Job type mismatch (job is {detected_type}, wanted {job_type})")
        else:
            not_matched.append("Job type not specified in this job post")
    if exp_level:
        detected_level = infer_experience_level(job)
        if detected_level == exp_level:
            score += 7
            matched.append(f"Experience level matches ({exp_level})")
        elif detected_level:
            not_matched.append(f"Experience level mismatch (job is {detected_level}, wanted {exp_level})")
        else:
            not_matched.append("Experience level not specified in this job post")

    reasons.extend(matched[:2])
    reasons.extend(not_matched[:2])
    if not reasons:
        reasons.append("No preference filters were provided.")
    return {"score": min(score, 40), "reasons": reasons, "matched": matched, "not_matched": not_matched}


@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        log_provider_configuration()
        seed_jobs(db)
        remove_seed_jobs(db)
        ensure_demo_user_and_data(db)
        _ensure_refresh_log_table(db)
        _start_auto_refresh_thread()
    except OperationalError as exc:
        raise RuntimeError(
            "Database schema is not ready. Run `alembic upgrade head` in backend/ first."
        ) from exc
    finally:
        db.close()


def _refresh_jobs_for_all_users_once() -> dict[str, int]:
    scanned = 0
    refreshed = 0
    failed = 0
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            scanned += 1
            preferences = get_preferences(user)
            if not any((preferences.get(k) or "").strip() for k in ("job_title", "city", "country")):
                continue
            try:
                # Privacy-safe scheduled refresh: do not send CV text to external providers.
                fetched_jobs = fetch_real_jobs(preferences, "", limit=50)
                if fetched_jobs:
                    upsert_fetched_jobs(db, fetched_jobs)
                    refreshed += 1
            except Exception as exc:
                failed += 1
                logger.warning("auto_refresh user_id=%s failed error=%s", user.id, exc)
    finally:
        db.close()
    return {"scanned": scanned, "refreshed": refreshed, "failed": failed}


def _run_saved_search_notifications_once() -> dict[str, int]:
    scanned = 0
    sent = 0
    db = SessionLocal()
    try:
        rows = db.query(SavedSearch).filter(SavedSearch.email_notifications_enabled == 1).all()
        for search in rows:
            scanned += 1
            user = db.query(User).filter(User.id == search.user_id).first()
            if not user or not user.email or int(user.email_verified or 0) != 1:
                continue
            if int(user.email_notifications_enabled or 0) != 1:
                continue
            q = db.query(Job).filter(Job.source.in_(active_job_sources()))
            if (search.country or "").strip():
                q = q.filter((Job.country.ilike(f"%{search.country}%")) | (Job.location.ilike(f"%{search.country}%")))
            if (search.city or "").strip():
                q = q.filter((Job.city.ilike(f"%{search.city}%")) | (Job.location.ilike(f"%{search.city}%")))
            if (search.job_title or "").strip():
                q = q.filter(Job.title.ilike(f"%{search.job_title}%"))
            since = search.last_notified_at or (datetime.utcnow() - timedelta(days=1))
            matches = (
                q.filter(Job.last_updated >= since)
                .order_by(Job.last_updated.desc())
                .limit(8)
                .all()
            )
            if not matches:
                continue
            lines = [f"- {job.title} at {job.company} ({job.city or job.location})" for job in matches]
            body = (
                f"Hi {user.name},\n\n"
                f"We found {len(matches)} new job matches for your saved search '{search.name}'.\n\n"
                + "\n".join(lines)
                + "\n\nYou can open Smart Job Platform to review and apply."
            )
            ok, _ = _send_basic_email(user.email, f"New job matches: {search.name}", body)
            if ok:
                search.last_notified_at = datetime.utcnow()
                db.add(search)
                sent += 1
        db.commit()
    finally:
        db.close()
    return {"scanned": scanned, "sent": sent}


def _auto_refresh_loop() -> None:
    interval_seconds = max(86400, int((os.getenv("AUTO_REFRESH_INTERVAL_SECONDS") or "86400").strip() or "86400"))
    run_on_start = (os.getenv("AUTO_REFRESH_RUN_ON_START") or "1").strip().lower() in {"1", "true", "yes", "on"}
    logger.info("auto_refresh_loop started interval_seconds=%s run_on_start=%s", interval_seconds, run_on_start)
    if run_on_start:
        stats = _refresh_jobs_for_all_users_once()
        _run_saved_search_notifications_once()
        _record_refresh_log(stats)
        logger.info(
            "auto_refresh_once scanned=%s refreshed=%s failed=%s",
            stats["scanned"],
            stats["refreshed"],
            stats["failed"],
        )
    while True:
        time.sleep(interval_seconds)
        stats = _refresh_jobs_for_all_users_once()
        _run_saved_search_notifications_once()
        _record_refresh_log(stats)
        logger.info(
            "auto_refresh_once scanned=%s refreshed=%s failed=%s",
            stats["scanned"],
            stats["refreshed"],
            stats["failed"],
        )


def _start_auto_refresh_thread() -> None:
    global _AUTO_REFRESH_THREAD_STARTED
    if _AUTO_REFRESH_THREAD_STARTED:
        return
    enabled = (os.getenv("AUTO_REFRESH_ENABLED") or "1").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        logger.info("auto_refresh_loop disabled by AUTO_REFRESH_ENABLED")
        return
    thread = threading.Thread(target=_auto_refresh_loop, name="smartjob-auto-refresh", daemon=True)
    thread.start()
    _AUTO_REFRESH_THREAD_STARTED = True


def _ensure_refresh_log_table(db: Session) -> None:
    db.execute(
        sa_text(
            """
            CREATE TABLE IF NOT EXISTS auto_refresh_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                scanned_users INTEGER NOT NULL,
                refreshed_users INTEGER NOT NULL,
                failed_users INTEGER NOT NULL,
                mode TEXT NOT NULL
            )
            """
        )
    )
    db.commit()


def _record_refresh_log(stats: dict[str, int]) -> None:
    db = SessionLocal()
    try:
        _ensure_refresh_log_table(db)
        mode = (os.getenv("JOB_API_PROVIDER") or "multi").strip().lower()
        db.execute(
            sa_text(
                """
                INSERT INTO auto_refresh_runs (scanned_users, refreshed_users, failed_users, mode)
                VALUES (:scanned_users, :refreshed_users, :failed_users, :mode)
                """
            ),
            {
                "scanned_users": int(stats.get("scanned", 0)),
                "refreshed_users": int(stats.get("refreshed", 0)),
                "failed_users": int(stats.get("failed", 0)),
                "mode": mode,
            },
        )
        db.commit()
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "Smart Job Platform API"}


@app.get("/health/providers")
def health_providers(
    request: Request,
    x_dev_token: str = Header(default="", alias="X-Dev-Token"),
    run_check: bool = False,
):
    expected_token = (os.getenv("DEV_HEALTH_TOKEN") or "").strip()
    if not expected_token:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_dev_token or x_dev_token != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    diagnostics = get_last_fetch_diagnostics()
    response: dict = {
        "status": "ok",
        "mode": (os.getenv("JOB_API_PROVIDER") or "multi").strip().lower(),
        "api_keys_configured": api_keys_configured(),
        "ai_assist_enabled": ai_assist_enabled(),
        "scraping_fallback_enabled": (os.getenv("ENABLE_SCRAPING_FALLBACK") or "").strip().lower() in {"1", "true", "yes", "on"},
        "connection": {
            "client_host": request.client.host if request.client else None,
        },
        "last_fetch": diagnostics,
    }

    if run_check:
        started = time.time()
        probe_preferences = {"job_title": "software engineer", "country": "Germany", "city": "Berlin"}
        fetched = fetch_real_jobs(probe_preferences, "", limit=20)
        probe_diagnostics = get_last_fetch_diagnostics()
        response["probe"] = {
            "requested_at_utc": datetime.utcnow().isoformat() + "Z",
            "duration_ms": int((time.time() - started) * 1000),
            "fetched_count": len(fetched),
            "provider_counts": probe_diagnostics.get("provider_counts") or {},
            "provider_failures": probe_diagnostics.get("provider_failures") or {},
            "connection_failures": int(probe_diagnostics.get("connection_failures") or 0),
            "provider_warning": probe_diagnostics.get("provider_warning"),
        }

    return response


@app.get("/jobs")
def get_jobs(db: Session = Depends(get_db)):
    sources = active_job_sources()
    rows = (
        db.query(Job)
        .filter(Job.source.in_(sources))
        .filter(Job.apply_url.isnot(None))
        .filter(Job.apply_url != "")
        .order_by(Job.last_updated.desc(), Job.posted_date.desc(), Job.id.desc())
        .all()
    )
    return [
        {
            "id": job.id,
            "source": job.source,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "apply_url": job.apply_url,
            "company_website_url": job.company_website_url,
            "logo_click_url": (job.company_website_url or job.apply_url),
            "company_logo_url": job.company_logo_url,
            "posted_date": (job.posted_date.isoformat() if job.posted_date else None),
            "last_updated": (job.last_updated.isoformat() if job.last_updated else None),
        }
        for job in rows
    ]


@app.post("/jobs/search")
def search_jobs(
    payload: JobSearchPayload,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    broad_mode = (os.getenv("BROAD_SEARCH_MODE") or "1").strip().lower() in {"1", "true", "yes", "on"}
    user = get_optional_current_user(authorization, db)
    base_preferences = get_preferences(user) if user else {}
    preferences = merge_search_preferences(base_preferences, payload)
    requested_title = (preferences.get("job_title") or "").strip()
    requested_search_text = (preferences.get("search_text") or "").strip()
    corrected_title = autocorrect_job_title(requested_title) if requested_title else ""
    if corrected_title and corrected_title != requested_title:
        preferences["job_title"] = corrected_title
    city_value = (preferences.get("city") or "").strip()
    radius_km = int(preferences.get("radius_km") or 20)
    if radius_km not in RADIUS_OPTIONS:
        radius_km = 20
    preferences["radius_km"] = radius_km
    cv_text = ((user.cv_text or "").strip() if user else "")
    limit = min(max(int(payload.limit or 20), 1), 50)
    offset = max(int(payload.offset or 0), 0)

    fetched_count = 0
    has_api_keys = api_keys_configured()
    logger.info(
        "jobs_search request title=%s city=%s radius=%s work_mode=%s limit=%s offset=%s",
        preferences.get("job_title") or "",
        preferences.get("city") or "",
        radius_km,
        preferences.get("work_mode") or "",
        limit,
        offset,
    )

    try:
        fetch_size = 50
        fetched_jobs = fetch_real_jobs(preferences, cv_text, limit=fetch_size)
        if fetched_jobs:
            fetched_count = upsert_fetched_jobs(db, fetched_jobs)
    except Exception:
        fetched_count = 0

    def run_filtered_query(active_preferences: dict, active_radius_km: int, strict_title: bool = True) -> list[Job]:
        query = db.query(Job).filter(Job.source.in_(active_job_sources()))
        country_pref_local = (active_preferences.get("country") or "Germany").strip()
        city_pref_local = (active_preferences.get("city") or "").strip()

        if (not broad_mode) and country_pref_local and country_pref_local.lower() not in ALL_VALUES:
            country_value = country_pref_local
            query = query.filter(
                (Job.country.ilike(f"%{country_value}%")) | (Job.location.ilike(f"%{country_value}%"))
            )
        if (not broad_mode) and city_pref_local and city_pref_local.lower() not in ALL_VALUES:
            city_map = _build_city_distance_map(city_pref_local)
            city_terms = [city for city, km in city_map.items() if km <= max(active_radius_km, 20)]
            city_terms.append(_norm_city(city_pref_local))
            city_terms = list({term for term in city_terms if term})
            city_clauses = []
            for term in city_terms:
                city_clauses.append(Job.city.ilike(f"%{term}%"))
                city_clauses.append(Job.location.ilike(f"%{term}%"))
            if city_clauses:
                query = query.filter(or_(*city_clauses))
        if active_preferences.get("job_title"):
            title_terms = _title_filter_terms(active_preferences["job_title"])
            if strict_title:
                # Strict mode: all significant terms must exist in title.
                for term in title_terms:
                    query = query.filter(Job.title.ilike(f"%{term}%"))
            elif title_terms:
                # Relaxed mode: allow any term in title/company/description.
                relaxed_title_clauses = []
                for term in title_terms:
                    relaxed_title_clauses.append(Job.title.ilike(f"%{term}%"))
                    relaxed_title_clauses.append(Job.company.ilike(f"%{term}%"))
                    relaxed_title_clauses.append(Job.description.ilike(f"%{term}%"))
                query = query.filter(or_(*relaxed_title_clauses))
        if active_preferences.get("work_mode"):
            query = query.filter(Job.work_mode == active_preferences["work_mode"])

        rows = query.order_by(Job.last_updated.desc(), Job.posted_date.desc(), Job.id.desc()).limit(500).all()
        if (not broad_mode) and city_pref_local and city_pref_local.lower() not in ALL_VALUES:
            filtered_jobs = []
            for job in rows:
                dist = _distance_km(city_pref_local, job)
                if dist is None or dist <= active_radius_km:
                    filtered_jobs.append(job)
            return filtered_jobs
        return rows

    jobs = run_filtered_query(preferences, radius_km, strict_title=True)
    used_filter_relaxation = False
    title_requested = bool((preferences.get("job_title") or "").strip())
    relevance_query = (preferences.get("job_title") or preferences.get("search_text") or "").strip()
    if not jobs:
        relaxed_preferences = dict(preferences)
        relaxed_preferences["work_mode"] = ""
        relaxed_preferences["job_type"] = ""
        relaxed_preferences["experience_level"] = ""
        if not title_requested:
            relaxed_preferences["job_title"] = ""
            relaxed_preferences["search_text"] = ""
        relaxed_radius = max(50, radius_km)
        relaxed_jobs = run_filtered_query(relaxed_preferences, relaxed_radius, strict_title=not title_requested)
        if not relaxed_jobs and title_requested:
            # Second-chance relaxed title search for manual role queries.
            relaxed_jobs = run_filtered_query(relaxed_preferences, relaxed_radius, strict_title=False)
        if relaxed_jobs:
            jobs = relaxed_jobs
            used_filter_relaxation = True
            logger.info(
                "jobs_search relaxed_filters_applied original_title=%s original_city=%s original_work_mode=%s original_radius=%s relaxed_radius=%s result_count=%s",
                preferences.get("job_title") or "",
                preferences.get("city") or "",
                preferences.get("work_mode") or "",
                radius_km,
                relaxed_radius,
                len(jobs),
            )
    if not jobs and (preferences.get("city") or "").strip():
        country_only_preferences = dict(preferences)
        country_only_preferences["work_mode"] = ""
        country_only_preferences["job_type"] = ""
        country_only_preferences["experience_level"] = ""
        if not title_requested:
            country_only_preferences["job_title"] = ""
            country_only_preferences["search_text"] = ""
        country_only_preferences["city"] = ""
        country_only_jobs = run_filtered_query(country_only_preferences, max(100, radius_km))
        if country_only_jobs:
            jobs = country_only_jobs
            used_filter_relaxation = True
            logger.info(
                "jobs_search country_only_fallback_applied original_city=%s original_title=%s result_count=%s",
                preferences.get("city") or "",
                preferences.get("job_title") or "",
                len(jobs),
            )
    if not jobs:
        global_broader_preferences = dict(preferences)
        global_broader_preferences["work_mode"] = ""
        global_broader_preferences["job_type"] = ""
        global_broader_preferences["experience_level"] = ""
        global_broader_preferences["city"] = ""
        global_broader_preferences["radius_km"] = max(100, radius_km)
        # Keep title/search constraints when the user explicitly requested a role.
        if not title_requested and not requested_search_text:
            global_broader_preferences["job_title"] = ""
            global_broader_preferences["search_text"] = ""
        global_broader_jobs = run_filtered_query(global_broader_preferences, max(100, radius_km), strict_title=False)
        if global_broader_jobs:
            jobs = global_broader_jobs
            used_filter_relaxation = True
            logger.info(
                "jobs_search global_broader_fallback_applied original_title=%s original_city=%s result_count=%s",
                preferences.get("job_title") or "",
                preferences.get("city") or "",
                len(jobs),
            )
    logger.info(
        "jobs_search db_results raw=%s fetched_count=%s sources=%s broad_mode=%s",
        len(jobs),
        fetched_count,
        ",".join(sorted({job.source for job in jobs})) if jobs else "-",
        broad_mode,
    )
    if relevance_query:
        before = len(jobs)
        jobs = [job for job in jobs if _job_is_relevant(job, relevance_query)]
        logger.info("jobs_search strict_relevance_applied query=%s before=%s after=%s", relevance_query, before, len(jobs))
    ranked = sorted((compute_match(job, cv_text, preferences) for job in jobs), key=_rank_key, reverse=True)
    paged_items = ranked[offset : offset + limit]
    for item in paged_items:
        item["why_match"] = build_short_match_reason(
            title=item.get("title") or "",
            company=item.get("company") or "",
            location=item.get("location") or "",
            preferences=preferences,
            reasons=item.get("preference_reasons") or item.get("reasons") or [],
        )
    logger.info("jobs_search response_count=%s has_more=%s", len(paged_items), (offset + limit) < len(ranked))
    if len(paged_items) > 0 and used_filter_relaxation:
        message = "Showing broader matches after relaxing filters."
    elif len(paged_items) > 0:
        message = "Real jobs fetched from provider."
    elif relevance_query:
        message = "No matching jobs found."
    elif not has_api_keys:
        message = (
            "No fresh matches for this search yet from active free providers. "
            "Try a broader title or nearby city, or add optional API keys to widen coverage."
        )
    else:
        message = "No fresh matching jobs found."
    return {
        "items": paged_items,
        "preferences": preferences,
        "fetched_jobs_count": fetched_count,
        "used_fallback": used_filter_relaxation,
        "api_keys_configured": has_api_keys,
        "total_available": len(ranked),
        "offset": offset,
        "limit": limit,
        "has_more": (offset + limit) < len(ranked),
        "message": message,
        "search_scope": "radius_city",
        "corrected_job_title": corrected_title if corrected_title and corrected_title != requested_title else None,
        "ai_assist_enabled": ai_assist_enabled(),
        "suggested_broaden_search": len(paged_items) == 0 and not used_filter_relaxation,
    }


@app.get("/locations/countries")
def get_countries(db: Session = Depends(get_db)):
    rows = (
        db.query(Job.country)
        .filter(Job.country.isnot(None))
        .filter(Job.country != "")
        .distinct()
        .all()
    )
    dynamic = sorted({(row[0] or "").strip() for row in rows if (row[0] or "").strip()})
    seed = ["Germany", "United States", "United Kingdom", "France", "Spain", "Italy", "Netherlands", "Poland"]
    merged = []
    for name in seed + dynamic:
        if name and name not in merged:
            merged.append(name)
    return {"items": merged}


@app.get("/locations/cities")
def get_cities(country: str = "", q: str = "", db: Session = Depends(get_db)):
    query = db.query(Job.city, Job.location, Job.country).filter(Job.source.in_(active_job_sources()))
    country_value = (country or "").strip()
    if not country_value or country_value.lower() in ALL_VALUES:
        # Keep UX focused: do not return random worldwide city lists by default.
        return {"items": []}

    country_lower = country_value.strip().lower()
    if country_lower and country_lower not in ALL_VALUES:
        query = query.filter(
            (Job.country.ilike(f"%{country_value}%")) | (Job.location.ilike(f"%{country_value}%"))
        )
    rows = query.limit(2000).all()

    items = set()
    for city_val, location_val, _ in rows:
        if city_val and city_val.strip():
            items.add(city_val.strip())
        if location_val and location_val.strip():
            first = location_val.split(",")[0].strip()
            if first:
                items.add(first)

    needle = (q or "").strip().lower()
    # Prioritize Germany major-city UX.
    if country_lower in GERMANY_ALIASES:
        for seeded in COUNTRY_CITY_SEEDS.get("germany", []):
            items.add(seeded)
    for seeded in COUNTRY_CITY_SEEDS.get(country_lower, []):
        items.add(seeded)

    filtered = sorted([name for name in items if not needle or needle in name.lower()])[:100]
    if country_lower in GERMANY_ALIASES and not needle:
        majors = COUNTRY_CITY_SEEDS.get("germany", [])
        ordered = [city for city in majors if city in filtered]
        rest = [city for city in filtered if city not in ordered]
        filtered = (ordered + rest)[:100]
    return {"items": filtered}


@app.get("/jobs/suggestions")
def job_title_suggestions(q: str = ""):
    suggestions = suggest_job_titles(q, limit=8)
    corrected = autocorrect_job_title(q) if q else ""
    return {
        "items": suggestions,
        "corrected_job_title": corrected if corrected and corrected.lower() != (q or "").strip().lower() else None,
        "ai_assist_enabled": ai_assist_enabled(),
    }


@app.post("/auth/register")
def register(payload: RegisterPayload, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(name=payload.name, email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    return {"message": "User registered successfully"}


@app.post("/auth/login")
def login(payload: LoginPayload, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or user.password_hash != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = secrets.token_hex(16)
    auth_token = AuthToken(token=token, user_id=user.id)
    db.add(auth_token)
    db.commit()
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.post("/auth/demo-login")
def demo_login(db: Session = Depends(get_db)):
    if not is_demo_mode_enabled():
        raise HTTPException(status_code=403, detail="Demo mode is disabled")

    user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if not user:
        ensure_demo_user_and_data(db)
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if not user:
        raise HTTPException(status_code=500, detail="Demo user could not be created")

    token = secrets.token_hex(16)
    auth_token = AuthToken(token=token, user_id=user.id)
    db.add(auth_token)
    db.commit()
    return {"token": token, "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.post("/auth/logout")
def logout(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.removeprefix("Bearer ").strip()
    auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()
    if auth_token:
        db.delete(auth_token)
        db.commit()
    return {"message": "Logged out successfully"}


@app.post("/dev/reset-test-users")
def reset_test_users(db: Session = Depends(get_db)):
    # Dev helper: remove throwaway users created during local testing.
    test_users = db.query(User).filter(User.email.like("test_%@example.com")).all()
    removed = 0
    for user in test_users:
        db.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
        db.query(Application).filter(Application.user_id == user.id).delete()
        db.delete(user)
        removed += 1
    db.commit()
    return {"message": "Test users removed", "count": removed}


@app.get("/auth/me")
def me(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db)

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "email_verified": bool(int(user.email_verified or 0)),
        "email_notifications_enabled": bool(int(user.email_notifications_enabled or 0)),
        "cv_status": get_cv_status(user),
        "preferences": get_preferences(user),
    }


@app.put("/profile/settings")
def update_profile_settings(
    payload: ProfileSettingsPayload,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = get_current_user(authorization, db)
    next_email = (payload.email or "").strip().lower()
    next_phone = (payload.phone or "").strip()

    if next_email and next_email != user.email:
        existing = db.query(User).filter(User.email == next_email, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = next_email

    user.phone = next_phone[:40] or None
    if payload.email is not None and next_email and next_email != user.email:
        user.email_verified = 0
    db.add(user)
    db.commit()
    return {
        "message": "Settings saved.",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "email_verified": bool(int(user.email_verified or 0)),
            "email_notifications_enabled": bool(int(user.email_notifications_enabled or 0)),
        },
        "sms_reset_configured": bool((os.getenv("SMS_PROVIDER_API_KEY") or "").strip()),
    }


@app.post("/auth/email-verification/request")
def request_email_verification(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    row = EmailVerificationToken(
        token_hash=token_hash,
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(row)
    db.commit()

    frontend_base = (os.getenv("FRONTEND_BASE_URL") or "http://127.0.0.1:5173").strip()
    verify_link = f"{frontend_base.rstrip('/')}/settings?verify_email_token={raw_token}"
    ok, _ = _send_basic_email(
        user.email,
        "Verify your Smart Job Platform email",
        f"Hi {user.name},\n\nVerify your email by opening:\n{verify_link}\n",
    )
    if ok:
        return {"message": "Verification email sent."}
    return {"message": "Email provider is not configured. Development verification link generated.", "dev_verify_link": verify_link}


@app.post("/auth/email-verification/confirm")
def confirm_email_verification(token: str, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db)
    raw = (token or "").strip()
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    row = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.user_id == user.id,
        )
        .first()
    )
    if not row or row.used_at or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification token is invalid or expired")
    row.used_at = datetime.utcnow()
    user.email_verified = 1
    db.add(row)
    db.add(user)
    db.commit()
    return {"message": "Email verified successfully."}


@app.post("/profile/email-notifications")
def set_email_notifications(
    enabled: bool,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = get_current_user(authorization, db)
    if enabled and int(user.email_verified or 0) != 1:
        raise HTTPException(status_code=400, detail="Verify your email first.")
    user.email_notifications_enabled = 1 if enabled else 0
    db.add(user)
    db.commit()
    return {"message": "Email notifications updated.", "enabled": bool(int(user.email_notifications_enabled or 0))}


@app.post("/saved-searches")
def create_saved_search(
    payload: SavedSearchPayload,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = get_current_user(authorization, db)
    search = SavedSearch(
        user_id=user.id,
        name=(payload.name or "My search")[:160],
        search_text=(payload.search_text or "")[:255] or None,
        country=(payload.country or "")[:120] or None,
        city=(payload.city or "")[:120] or None,
        job_title=(payload.job_title or "")[:160] or None,
        work_mode=(payload.work_mode or "")[:40] or None,
        job_type=(payload.job_type or "")[:40] or None,
        experience_level=(payload.experience_level or "")[:40] or None,
        radius_km=int(payload.radius_km or 20),
        email_notifications_enabled=1 if bool(payload.email_notifications_enabled) else 0,
    )
    if search.email_notifications_enabled and (int(user.email_verified or 0) != 1 or int(user.email_notifications_enabled or 0) != 1):
        search.email_notifications_enabled = 0
    db.add(search)
    db.commit()
    db.refresh(search)
    return {"message": "Search saved.", "item": {"id": search.id, "name": search.name, "email_notifications_enabled": bool(search.email_notifications_enabled)}}


@app.get("/saved-searches")
def list_saved_searches(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db)
    rows = db.query(SavedSearch).filter(SavedSearch.user_id == user.id).order_by(SavedSearch.id.desc()).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "search_text": row.search_text,
            "country": row.country,
            "city": row.city,
            "job_title": row.job_title,
            "work_mode": row.work_mode,
            "job_type": row.job_type,
            "experience_level": row.experience_level,
            "radius_km": row.radius_km,
            "email_notifications_enabled": bool(row.email_notifications_enabled),
            "last_notified_at": row.last_notified_at.isoformat() if row.last_notified_at else None,
        }
        for row in rows
    ]


@app.post("/auth/password-reset/request")
def password_reset_request(payload: PasswordResetRequestPayload, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user:
        return {"message": "If this email exists, a reset link has been prepared."}

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.utcnow() + timedelta(minutes=30)
    row = PasswordResetToken(token_hash=token_hash, user_id=user.id, expires_at=expires_at)
    db.add(row)
    db.commit()

    frontend_base = (os.getenv("FRONTEND_BASE_URL") or "http://127.0.0.1:5173").strip()
    reset_link = f"{frontend_base.rstrip('/')}/reset-password?token={raw_token}"
    sent, status_message = _send_reset_email(user.email, reset_link)
    response = {"message": status_message if sent else "Development mode: email provider not configured."}
    if not sent:
        response["dev_reset_link"] = reset_link
    return response


@app.post("/auth/password-reset/confirm")
def password_reset_confirm(payload: PasswordResetConfirmPayload, db: Session = Depends(get_db)):
    token = (payload.token or "").strip()
    if len(token) < 10:
        raise HTTPException(status_code=400, detail="Invalid token")
    if len((payload.new_password or "").strip()) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
    if not row or row.used_at is not None or row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token is invalid or expired")

    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.new_password.strip())
    row.used_at = datetime.utcnow()
    db.add(user)
    db.add(row)
    db.commit()
    return {"message": "Password reset successful."}


@app.post("/applications")
def create_application(
    payload: ApplicationPayload,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user_id = get_user_id_from_auth(authorization)

    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = db.query(Application).filter(Application.user_id == user_id, Application.job_id == payload.job_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already applied to this job")

    application = Application(user_id=user_id, job_id=payload.job_id, status="submitted")
    db.add(application)
    db.commit()
    db.refresh(application)

    return {"id": application.id, "job_id": application.job_id, "status": application.status}


@app.get("/applications")
def list_my_applications(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user_id = get_user_id_from_auth(authorization)

    rows = (
        db.query(Application)
        .filter(Application.user_id == user_id)
        .order_by(Application.id.desc())
        .all()
    )

    return [
        {
            "id": row.id,
            "job_id": row.job_id,
            "job_title": row.job.title,
            "company": row.job.company,
            "status": row.status,
        }
        for row in rows
    ]


@app.post("/profile/cv")
def upload_cv(
    file: UploadFile = File(...),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = get_current_user(authorization, db)
    cv_text = extract_cv_text(file)
    if len(cv_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="CV content is too short")

    user.cv_filename = file.filename or "uploaded_cv"
    user.cv_text = cv_text.strip()
    profile = _extract_cv_profile(user.cv_text)
    user.cv_candidate_name = (profile.get("name") or "")[:160] or None
    user.cv_skills_csv = ",".join(profile.get("skills") or [])[:1200] or None
    user.cv_experience_summary = (profile.get("experience_summary") or "")[:1200] or None
    user.cv_preferred_keywords_csv = ",".join(profile.get("preferred_keywords") or [])[:1200] or None
    db.add(user)
    db.commit()

    return {"message": "CV uploaded successfully", "cv_status": get_cv_status(user)}


@app.post("/profile/cv/text")
def save_cv_text(
    payload: CvTextSavePayload,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = get_current_user(authorization, db)
    text = (payload.cv_text or "").strip()
    if len(text) < 20:
        raise HTTPException(status_code=400, detail="CV text is too short")
    user.cv_text = text
    user.cv_filename = (payload.filename or "improved_cv.txt")[:255]
    profile = _extract_cv_profile(user.cv_text)
    user.cv_candidate_name = (profile.get("name") or "")[:160] or None
    user.cv_skills_csv = ",".join(profile.get("skills") or [])[:1200] or None
    user.cv_experience_summary = (profile.get("experience_summary") or "")[:1200] or None
    user.cv_preferred_keywords_csv = ",".join(profile.get("preferred_keywords") or [])[:1200] or None
    db.add(user)
    db.commit()
    return {"message": "CV text saved to profile.", "cv_status": get_cv_status(user)}


@app.post("/chatbot/cv/analyze")
def chatbot_cv_analyze(
    file: UploadFile = File(...),
    language: str = "en",
    request_text: str = "",
):
    cv_text = extract_cv_text(file)
    if len(cv_text.strip()) < 20:
        raise HTTPException(status_code=400, detail="CV content is too short")
    result = _generate_cv_outputs(cv_text, language=language, request_text=request_text)
    return {
        "filename": file.filename or "uploaded_cv",
        "cv_text": cv_text,
        "summary": result.get("summary"),
        "suggestions": result.get("suggestions") or [],
        "improved_cv_text": result.get("improved_cv_text") or cv_text,
    }


@app.post("/chatbot/cv/generate")
def chatbot_cv_generate(payload: ChatbotCvActionPayload):
    text = (payload.cv_text or "").strip()
    if len(text) < 20:
        raise HTTPException(status_code=400, detail="CV text is too short")
    result = _generate_cv_outputs(text, language=(payload.language or "en"), request_text=(payload.request or ""))
    return result


@app.post("/career/plan")
def career_plan(
    payload: CareerPlanPayload,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = get_current_user(authorization, db)
    cv_text = (user.cv_text or "").strip()
    if len(cv_text) < 20:
        raise HTTPException(status_code=400, detail="Upload your CV first to generate a career plan.")
    prefs = get_preferences(user)
    role = (payload.target_role or prefs.get("job_title") or "").strip() or "target role"
    city = (payload.target_city or prefs.get("city") or prefs.get("country") or "").strip() or "preferred location"
    lang = (payload.language or "en").strip().lower()
    plan = _build_career_plan(cv_text, role, city, language=lang)
    return {
        "target_role": role,
        "target_city": city,
        "language": lang,
        "plan": plan,
    }


@app.post("/profile/preferences")
def save_preferences(
    payload: PreferencesPayload,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = get_current_user(authorization, db)
    user.preferred_country = (payload.country or "").strip() or None
    user.preferred_city = (payload.city or "").strip() or None
    user.preferred_job_title = (payload.job_title or "").strip() or None
    user.preferred_work_mode = (payload.work_mode or "").strip().lower() or None
    user.preferred_job_type = (payload.job_type or "").strip().lower() or None
    user.preferred_experience_level = (payload.experience_level or "").strip().lower() or None
    db.add(user)
    db.commit()
    return {"message": "Preferences saved", "preferences": get_preferences(user)}


@app.post("/chatbot/message")
def chatbot_message(
    payload: ChatbotPayload,
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    user = get_optional_current_user(authorization, db)
    reply = _chatbot_reply(payload.message, user, db)
    return {"reply": reply}


@app.get("/matching")
def get_matching(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db)
    cv_text = (user.cv_text or "").strip()
    if not cv_text:
        raise HTTPException(status_code=400, detail="Upload your CV first to get AI matches")

    preferences = get_preferences(user)
    fetched_count = 0
    try:
        fetched_jobs = fetch_real_jobs(preferences, cv_text, limit=50)
        if fetched_jobs:
            fetched_count = upsert_fetched_jobs(db, fetched_jobs)
    except Exception:
        fetched_count = 0

    jobs = (
        db.query(Job)
        .filter(Job.source.in_(active_job_sources()))
        .order_by(Job.id.desc())
        .limit(300)
        .all()
    )
    ranked = sorted((compute_match(job, cv_text, preferences) for job in jobs), key=_rank_key, reverse=True)
    return {
        "items": ranked[:10],
        "cv_status": get_cv_status(user),
        "preferences": preferences,
        "fetched_jobs_count": fetched_count,
    }
