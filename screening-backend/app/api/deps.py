from typing import Generator
from sqlalchemy.orm import Session
from app.db.session import SessionLocal

async def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
