import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.db import models
import logging

logger = logging.getLogger(__name__)

class SessionService:
    """Service for managing interview sessions"""
    
    async def create_session(
        self,
        resume_path: str,
        role: str,
        candidate_name: Optional[str] = None,
        db: Session = None
    ) -> str:
        """Create a new interview session"""
        try:
            session_id = str(uuid.uuid4())
            
            session = models.InterviewSession(
                id=session_id,
                candidate_name=candidate_name,
                resume_path=resume_path,
                role=role,
                status="active"
            )
            
            if db:
                db.add(session)
                db.commit()
            
            logger.info(f"Created interview session: {session_id}")
            return session_id
        
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            if db:
                db.rollback()
            raise
    
    async def get_session(
        self,
        session_id: str,
        db: Session
    ) -> Optional[models.InterviewSession]:
        """Get session by ID"""
        try:
            session = db.query(models.InterviewSession).filter(
                models.InterviewSession.id == session_id
            ).first()
            return session
        except Exception as e:
            logger.error(f"Error getting session: {str(e)}")
            raise
    
    async def save_answer(
        self,
        session_id: str,
        question_id: str,
        answer_text: str,
        db: Session
    ) -> str:
        """Save an answer"""
        try:
            answer_id = str(uuid.uuid4())
            
            answer = models.Answer(
                id=answer_id,
                session_id=session_id,
                question_id=question_id,
                answer_text=answer_text
            )
            
            db.add(answer)
            db.commit()
            
            logger.info(f"Saved answer {answer_id} for session {session_id}")
            return answer_id
        
        except Exception as e:
            logger.error(f"Error saving answer: {str(e)}")
            db.rollback()
            raise
    
    async def complete_session(
        self,
        session_id: str,
        score: float,
        db: Session
    ):
        """Mark session as completed"""
        try:
            session = await self.get_session(session_id, db)
            if session:
                session.status = "completed"
                session.score = score
                session.end_time = datetime.utcnow()
                db.commit()
                logger.info(f"Completed session {session_id} with score {score}")
        
        except Exception as e:
            logger.error(f"Error completing session: {str(e)}")
            db.rollback()
            raise
