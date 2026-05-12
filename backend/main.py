import hashlib
import secrets

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

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

jobs = [
    {
        "id": 1,
        "title": "Frontend Developer",
        "company": "Google",
        "location": "Germany"
    },
    {
        "id": 2,
        "title": "Python Developer",
        "company": "Spotify",
        "location": "Remote"
    }
]

users = []
tokens = {}


class RegisterPayload(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@app.get("/")
def home():
    return {"message": "Smart Job Platform API"}


@app.get("/jobs")
def get_jobs():
    return jobs


@app.post("/auth/register")
def register(payload: RegisterPayload):
    existing = next((user for user in users if user["email"].lower() == payload.email.lower()), None)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = {
        "id": len(users) + 1,
        "name": payload.name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
    }
    users.append(user)
    return {"message": "User registered successfully"}


@app.post("/auth/login")
def login(payload: LoginPayload):
    user = next((row for row in users if row["email"] == payload.email.lower()), None)
    if not user or user["password_hash"] != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = secrets.token_hex(16)
    tokens[token] = user["id"]
    return {"token": token, "user": {"id": user["id"], "name": user["name"], "email": user["email"]}}


@app.get("/auth/me")
def me(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.removeprefix("Bearer ").strip()
    user_id = tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = next((row for row in users if row["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"id": user["id"], "name": user["name"], "email": user["email"]}
