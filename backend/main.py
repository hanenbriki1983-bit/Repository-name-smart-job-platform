import hashlib
import secrets
from io import BytesIO

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Application, AuthToken, Job, User

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
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
}


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
            Job(title="Frontend Developer", company="Google", location="Germany"),
            Job(title="Python Developer", company="Spotify", location="Remote"),
        ]
    )
    db.commit()


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


def compute_match(job: Job, cv_text: str) -> dict:
    cv_tokens = tokenize(cv_text)
    sections = extract_sections(cv_text)
    skills_tokens = tokenize(sections["skills"])
    exp_tokens = tokenize(sections["experience"])
    project_tokens = tokenize(sections["projects"])
    weighted_cv = cv_tokens | skills_tokens | exp_tokens | project_tokens
    job_tokens = tokenize(f"{job.title} {job.company} {job.location} {job.description or ''}")

    cv_skill_hits = sorted(token for token in weighted_cv if token in SKILL_KEYWORDS)
    overlap = sorted(weighted_cv & job_tokens)
    overlap_score = min(len(overlap) * 10, 60)
    skill_score = min(len(cv_skill_hits) * 7, 28)
    title_bonus = 12 if tokenize(job.title) & (skills_tokens | exp_tokens) else 0
    project_bonus = 8 if tokenize(job.title) & project_tokens else 0
    score = min(overlap_score + skill_score + title_bonus + project_bonus + 4, 100)

    reasons = []
    if cv_skill_hits:
        reasons.append(f"CV skills matched: {', '.join(cv_skill_hits[:5])}")
    if overlap:
        reasons.append(f"Keyword overlap with role: {', '.join(overlap[:5])}")
    if not reasons:
        reasons.append("General profile alignment based on available text.")

    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "score": score,
        "reasons": reasons,
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


@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        seed_jobs(db)
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
            "title": job.title,
            "company": job.company,
            "location": job.location,
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


@app.get("/auth/me")
def me(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db)

    return {"id": user.id, "name": user.name, "email": user.email, "cv_status": get_cv_status(user)}


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


@app.get("/matching")
def get_matching(authorization: str = Header(default=""), db: Session = Depends(get_db)):
    user = get_current_user(authorization, db)
    cv_text = (user.cv_text or "").strip()
    if not cv_text:
        raise HTTPException(status_code=400, detail="Upload your CV first to get AI matches")

    jobs = db.query(Job).order_by(Job.id.asc()).all()
    ranked = sorted((compute_match(job, cv_text) for job in jobs), key=lambda row: row["score"], reverse=True)
    return {"items": ranked[:10], "cv_status": get_cv_status(user)}
