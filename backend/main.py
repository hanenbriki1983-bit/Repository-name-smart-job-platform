from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

app = FastAPI(title="Smart Job Platform API")

DATABASE_URL = "sqlite:///./jobs.db"
SECRET_KEY = "change-this-secret-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="candidate", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    applications = relationship("Application", back_populates="user")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    location = Column(String(120), nullable=True)
    jobs = relationship("Job", back_populates="company")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(120), nullable=True)
    skills = Column(String(255), nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    cv_file = Column(String(255), nullable=False)
    status = Column(String(50), default="submitted", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "candidate"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CompanyCreate(BaseModel):
    name: str
    location: Optional[str] = None


class JobCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    skills: Optional[str] = None
    company_id: int


class AISuggestRequest(BaseModel):
    skills_text: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def seed_jobs_if_empty(db: Session) -> None:
    if db.query(Company).count() > 0:
        return

    google = Company(name="Google", location="Berlin")
    spotify = Company(name="Spotify", location="Stockholm")
    db.add_all([google, spotify])
    db.commit()
    db.refresh(google)
    db.refresh(spotify)

    db.add_all(
        [
            Job(
                title="Frontend Developer",
                company_id=google.id,
                location="Berlin",
                skills="react,javascript,css",
                description="Build user-facing features for web products.",
            ),
            Job(
                title="Python Developer",
                company_id=spotify.id,
                location="Remote",
                skills="python,fastapi,sql",
                description="Build backend APIs and data services.",
            ),
        ]
    )
    db.commit()


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_jobs_if_empty(db)
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "Backend is running"}


@app.post("/auth/register", response_model=TokenResponse)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/dashboard")
def dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_apps = (
        db.query(Application).filter(Application.user_id == current_user.id).order_by(Application.created_at.desc()).all()
    )
    return {
        "user": {"id": current_user.id, "name": current_user.name, "email": current_user.email, "role": current_user.role},
        "applications_count": len(user_apps),
    }


@app.post("/companies")
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    company = Company(name=payload.name, location=payload.location)
    db.add(company)
    db.commit()
    db.refresh(company)
    return {"id": company.id, "name": company.name, "location": company.location}


@app.get("/companies")
def list_companies(db: Session = Depends(get_db)):
    rows = db.query(Company).all()
    return [{"id": c.id, "name": c.name, "location": c.location} for c in rows]


@app.post("/jobs")
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == payload.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    job = Job(
        title=payload.title,
        description=payload.description,
        location=payload.location,
        skills=payload.skills,
        company_id=payload.company_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "title": job.title, "company_id": job.company_id}


@app.get("/jobs")
def list_jobs(q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Job).join(Company, Job.company_id == Company.id)
    if q:
        query = query.filter((Job.title.ilike(f"%{q}%")) | (Job.skills.ilike(f"%{q}%")))

    rows = query.order_by(Job.created_at.desc()).all()
    return [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company.name,
            "location": job.location,
            "skills": job.skills,
            "description": job.description,
        }
        for job in rows
    ]


@app.post("/applications")
async def apply_to_job(
    job_id: int = Form(...),
    cv: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    safe_name = f"user{current_user.id}_job{job_id}_{cv.filename}"
    cv_path = UPLOAD_DIR / safe_name
    content = await cv.read()
    cv_path.write_bytes(content)

    application = Application(user_id=current_user.id, job_id=job_id, cv_file=str(cv_path))
    db.add(application)
    db.commit()
    db.refresh(application)

    return {"application_id": application.id, "status": application.status}


@app.get("/applications")
def list_my_applications(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return [
        {
            "id": a.id,
            "job_id": a.job_id,
            "job_title": a.job.title,
            "status": a.status,
            "cv_file": a.cv_file,
        }
        for a in rows
    ]


@app.post("/ai/suggest-jobs")
def ai_suggest_jobs(payload: AISuggestRequest, db: Session = Depends(get_db)):
    skill_tokens = {s.strip().lower() for s in payload.skills_text.split(",") if s.strip()}
    jobs = db.query(Job).all()

    scored = []
    for job in jobs:
        job_tokens = {s.strip().lower() for s in (job.skills or "").split(",") if s.strip()}
        match_count = len(skill_tokens.intersection(job_tokens))
        if match_count > 0:
            scored.append((match_count, job))

    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:5]

    return {
        "suggestions": [
            {
                "job_id": job.id,
                "title": job.title,
                "company": job.company.name,
                "match_score": score,
            }
            for score, job in top
        ]
    }
