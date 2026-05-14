from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    cv_filename = Column(String(255), nullable=True)
    cv_text = Column(Text, nullable=True)
    preferred_country = Column(String(120), nullable=True)
    preferred_city = Column(String(120), nullable=True)
    preferred_work_mode = Column(String(40), nullable=True)
    preferred_job_type = Column(String(40), nullable=True)
    preferred_experience_level = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    applications = relationship("Application", back_populates="user")
    auth_tokens = relationship("AuthToken", back_populates="user")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(160), nullable=False)
    company = Column(String(160), nullable=False)
    location = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    applications = relationship("Application", back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    status = Column(String(40), default="submitted", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(128), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="auth_tokens")
