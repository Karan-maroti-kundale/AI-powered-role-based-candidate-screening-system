# app/db/models.py

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def generate_uuid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    session_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    role_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resume_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    extracted_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    extracted_technologies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    years_of_experience: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="created")

    mcq_total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mcq_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mcq_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)

    mcq_status: Mapped[str] = mapped_column(String(30), nullable=False, default="created")
    mcq_report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    mcq_strengths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    mcq_focus_areas: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    mcq_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user: Mapped[User | None] = relationship(back_populates="sessions")
    mcq_questions: Mapped[list["MCQQuestion"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class MCQQuestion(Base):
    __tablename__ = "mcq_questions"

    question_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("interview_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Stored as:
    # [
    #   {"key": "A", "text": "..."},
    #   {"key": "B", "text": "..."},
    #   {"key": "C", "text": "..."},
    #   {"key": "D", "text": "..."}
    # ]
    options: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    correct_answer: Mapped[str] = mapped_column(String(10), nullable=False)
    selected_answer: Mapped[str | None] = mapped_column(String(10), nullable=True)

    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty_level: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    session: Mapped[InterviewSession] = relationship(back_populates="mcq_questions")