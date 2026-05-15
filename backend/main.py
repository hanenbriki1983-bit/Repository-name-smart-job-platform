import hashlib
import os
import secrets
from io import BytesIO

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import SessionLocal
from job_fetcher import fetch_real_jobs
from models import Application, AuthToken, Job, User

app = FastAPI()
default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", default_origins).split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
    if db.query(Job).count() > 0:
        return

    db.add_all(
        [
            Job(
                source="seed",
                external_id="seed-frontend",
                title="Frontend Developer",
                company="Google",
                location="Germany",
                country="Germany",
                city="Berlin",
                work_mode="on-site",
                apply_url="https://careers.google.com/",
                skills_csv="javascript,react,css,html",
            ),
            Job(
                source="seed",
                external_id="seed-python",
                title="Python Developer",
                company="Spotify",
                location="Remote",
                country="Germany",
                city="Berlin",
                work_mode="remote",
                apply_url="https://www.lifeatspotify.com/jobs",
                skills_csv="python,fastapi,sql,docker",
            ),
        ]
    )
    db.commit()


def is_demo_mode_enabled() -> bool:
    return os.getenv("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


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
    saved = 0
    for row in jobs:
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

        existing.title = (row.get("title") or "Unknown Role")[:160]
        existing.company = (row.get("company") or "Unknown Company")[:160]
        existing.location = (row.get("location") or "Unknown")[:120]
        existing.country = (row.get("country") or "")[:120] or None
        existing.city = (row.get("city") or "")[:120] or None
        existing.work_mode = (row.get("work_mode") or "")[:40] or None
        existing.job_type = (row.get("job_type") or "")[:40] or None
        existing.apply_url = (row.get("apply_url") or "")[:600] or None
        existing.description = (row.get("description") or "")[:4000] or None
        existing.skills_csv = (row.get("skills_csv") or "")[:1200] or None
        saved += 1

    db.commit()
    return saved


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

    raise HTTPException(status_code=400, detail="Only .txt and .pdf files are supported")


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


def get_current_user(authorization: str, db: Session) -> User:
    user_id = get_user_id_from_auth(authorization)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_cv_status(user: User) -> dict:
    return {
        "has_cv": bool((user.cv_text or "").strip()),
        "cv_filename": user.cv_filename,
        "cv_chars": len((user.cv_text or "").strip()),
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
        seed_jobs(db)
        ensure_demo_user_and_data(db)
    except OperationalError as exc:
        raise RuntimeError(
            "Database schema is not ready. Run `alembic upgrade head` in backend/ first."
        ) from exc
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "Smart Job Platform API"}


@app.get("/jobs")
def get_jobs(db: Session = Depends(get_db)):
    rows = db.query(Job).order_by(Job.id.asc()).all()
    return [
        {
            "id": job.id,
            "source": job.source,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "apply_url": job.apply_url,
        }
        for job in rows
    ]


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
        "cv_status": get_cv_status(user),
        "preferences": get_preferences(user),
    }


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
    db.add(user)
    db.commit()

    return {"message": "CV uploaded successfully", "cv_status": get_cv_status(user)}


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


@app.get("/matching")
def get_matching(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db)
    cv_text = (user.cv_text or "").strip()
    if not cv_text:
        raise HTTPException(status_code=400, detail="Upload your CV first to get AI matches")

    preferences = get_preferences(user)
    fetched_count = 0
    try:
        fetched_jobs = fetch_real_jobs(preferences, cv_text, limit=30)
        if fetched_jobs:
            fetched_count = upsert_fetched_jobs(db, fetched_jobs)
    except Exception:
        # Keep matching available even if provider credentials/network are missing.
        fetched_count = 0

    jobs = db.query(Job).order_by(Job.id.desc()).limit(200).all()
    ranked = sorted((compute_match(job, cv_text, preferences) for job in jobs), key=lambda row: row["score"], reverse=True)
    return {
        "items": ranked[:10],
        "cv_status": get_cv_status(user),
        "preferences": preferences,
        "fetched_jobs_count": fetched_count,
    }
