# app/db/session.py

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./candidate_screening.db")

Base = declarative_base()


def _sqlite_path_from_url(database_url: str) -> Optional[Path]:
    if not database_url.startswith("sqlite"):
        return None

    url = make_url(database_url)
    db_name = url.database

    if not db_name or db_name == ":memory:":
        return None

    path = Path(db_name)
    if not path.is_absolute():
        path = Path.cwd() / path

    return path


def ensure_sqlite_database() -> None:
    """
    If the file exists but is not a valid SQLite database, move it aside.
    This prevents SQLAlchemy startup from crashing.
    """
    db_path = _sqlite_path_from_url(DATABASE_URL)
    if db_path is None:
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        return

    try:
        # This will fail if the file is not a valid SQLite database.
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("PRAGMA schema_version;")
    except sqlite3.DatabaseError:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        broken_path = db_path.with_name(f"{db_path.stem}.broken.{timestamp}{db_path.suffix}")
        try:
            db_path.replace(broken_path)
        except OSError:
            try:
                db_path.unlink()
            except OSError:
                pass


def build_engine():
    if DATABASE_URL.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}

    return create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        future=True,
    )


engine = None
SessionLocal = None


def init_db() -> None:
    """
    Call this once at application startup.
    It validates the SQLite file, creates the engine, and builds tables.
    """
    global engine, SessionLocal

    ensure_sqlite_database()

    if engine is None:
        engine = build_engine()

    if SessionLocal is None:
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
            future=True,
        )

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        raise RuntimeError("Database is not initialized. Call init_db() at startup.")

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()