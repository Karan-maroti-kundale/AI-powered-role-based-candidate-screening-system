# app/main.py

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import InterviewSession, MCQQuestion
from app.db.session import Base, engine, get_db, init_db
from app.services.mcq_generator import MCQGenerator
from app.services.resume_parser import ResumeParser
from app.services.skill_extractor import SkillExtractor

import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


app = FastAPI(
    title="AI-Powered MCQ Assessment API",
    version="2.0.0",
    description="Real-time dynamic MCQ assessment system",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

resume_parser = ResumeParser()
skill_extractor = SkillExtractor()


class PublicMCQQuestion(BaseModel):
    question_id: str
    question_number: int
    question_text: str
    options: list[dict]
    difficulty_level: str


class MCQStartResponse(BaseModel):
    success: bool = True
    message: str
    session_id: str
    role_name: str
    filename: str | None = None
    text_length: int
    extracted_profile: dict
    questions: list[PublicMCQQuestion]


class SelectedAnswer(BaseModel):
    question_id: str
    selected_answer: str = Field(..., description="A, B, C, or D")


class SubmitTestRequest(BaseModel):
    session_id: str
    answers: list[SelectedAnswer]


class QuestionGrade(BaseModel):
    question_id: str
    question_number: int
    selected_answer: str | None
    correct_answer: str
    is_correct: bool
    explanation: str | None = None


class SubmitTestResponse(BaseModel):
    success: bool = True
    message: str
    session_id: str
    total_questions: int
    correct_count: int
    score_text: str
    percentage: float
    results: list[QuestionGrade]


class ResultsResponse(BaseModel):
    success: bool = True
    session_id: str
    role_name: str
    score_text: str
    percentage: float
    total_questions: int
    correct_count: int
    report_text: str
    strengths: list[str]
    improvement_focus: list[str]
    recommendation: str


class MCQAnalysisReport(BaseModel):
    report_text: str
    strengths: list[str] = Field(default_factory=list)
    improvement_focus: list[str] = Field(default_factory=list)
    recommendation: str = ""


def _build_results_chain():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0.2)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are a senior assessment evaluator.\n"
                    "Analyze a candidate's MCQ test performance.\n"
                    "Highlight strengths, weaknesses, and exactly what to improve next.\n"
                    "Be specific, actionable, and grounded in the question-by-question results."
                ),
            ),
            (
                "user",
                (
                    "Role: {role_name}\n"
                    "Candidate profile: {profile}\n"
                    "Score: {score_text}\n"
                    "Percentage: {percentage}%\n\n"
                    "Question review:\n{question_review}\n\n"
                    "Produce a concise but useful evaluation report."
                ),
            ),
        ]
    )

    structured = llm.with_structured_output(
        MCQAnalysisReport,
        method="json_schema",
    )

    return prompt | structured


RESULTS_CHAIN = _build_results_chain()


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/interview/start", response_model=MCQStartResponse)
async def start_interview(
    resume_file: UploadFile = File(...),
    role_name: str = Form(...),
    db: Session = Depends(get_db),
):
    if not role_name or not role_name.strip():
        raise HTTPException(status_code=400, detail="role_name is required.")

    if not resume_file.filename:
        raise HTTPException(status_code=400, detail="resume_file must have a filename.")

    if not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")

    session_row = InterviewSession(
        session_id=str(uuid4()),
        role_name=role_name.strip(),
        resume_filename=resume_file.filename,
        status="upload_received",
        mcq_status="upload_received",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)

    try:
        resume_text = await resume_parser.extract_text_from_pdf(resume_file)
        extracted_profile = skill_extractor.extract_profile(resume_text)

        session_row.resume_text = resume_text
        session_row.extracted_skills = extracted_profile.get("skills", [])
        session_row.extracted_technologies = extracted_profile.get("technologies", [])
        session_row.years_of_experience = float(
            extracted_profile.get("years_of_experience", 0.0) or 0.0
        )
        session_row.status = "profile_extracted"
        db.commit()
        db.refresh(session_row)

        mcq_generator = MCQGenerator()
        test_bundle = mcq_generator.generate_test(
            role_name=session_row.role_name,
            extracted_profile=extracted_profile,
        )

        questions = test_bundle.get("questions", [])
        if len(questions) != 30:
            raise RuntimeError(f"MCQ generator returned {len(questions)} questions instead of 30.")

        for idx, q in enumerate(questions, start=1):
            question_row = MCQQuestion(
                question_id=str(uuid4()),
                session_id=session_row.session_id,
                question_number=idx,
                question_text=q["question_text"],
                options=[{"key": opt["key"], "text": opt["text"]} for opt in q["options"]],
                correct_answer=q["correct_answer"],
                explanation=q.get("explanation", ""),
                difficulty_level=q.get("difficulty_level", "medium"),
            )
            db.add(question_row)

        session_row.mcq_total_questions = 30
        session_row.mcq_status = "generated"
        session_row.status = "mcq_generated"
        db.commit()
        db.refresh(session_row)

        stored_questions = (
            db.query(MCQQuestion)
            .filter(MCQQuestion.session_id == session_row.session_id)
            .order_by(MCQQuestion.question_number.asc())
            .all()
        )

        public_questions = [
            PublicMCQQuestion(
                question_id=q.question_id,
                question_number=q.question_number,
                question_text=q.question_text,
                options=q.options,
                difficulty_level=q.difficulty_level,
            )
            for q in stored_questions
        ]

        return MCQStartResponse(
            message="Resume processed and MCQ test generated successfully.",
            session_id=session_row.session_id,
            role_name=session_row.role_name,
            filename=session_row.resume_filename,
            text_length=len(resume_text),
            extracted_profile=extracted_profile,
            questions=public_questions,
        )

    except ValueError as exc:
        session_row.status = "failed"
        session_row.mcq_status = "failed"
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        session_row.status = "failed"
        session_row.mcq_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Interview start failed: {exc}")


@app.post("/interview/submit-test", response_model=SubmitTestResponse)
async def submit_test(payload: SubmitTestRequest, db: Session = Depends(get_db)):
    session_row = db.get(InterviewSession, payload.session_id)
    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found.")

    questions = (
        db.query(MCQQuestion)
        .filter(MCQQuestion.session_id == payload.session_id)
        .order_by(MCQQuestion.question_number.asc())
        .all()
    )

    if not questions:
        raise HTTPException(status_code=404, detail="No MCQ questions found for this session.")

    selected_map = {
        item.question_id: item.selected_answer.strip().upper()
        for item in payload.answers
    }

    question_ids = {q.question_id for q in questions}
    invalid_ids = [qid for qid in selected_map.keys() if qid not in question_ids]
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid question_id(s) in submission: {invalid_ids}",
        )

    correct_count = 0
    results: list[QuestionGrade] = []

    for q in questions:
        selected = selected_map.get(q.question_id)
        is_correct = bool(selected) and selected == q.correct_answer

        q.selected_answer = selected
        q.is_correct = is_correct
        q.answered_at = datetime.utcnow()

        if is_correct:
            correct_count += 1

        results.append(
            QuestionGrade(
                question_id=q.question_id,
                question_number=q.question_number,
                selected_answer=selected,
                correct_answer=q.correct_answer,
                is_correct=is_correct,
                explanation=q.explanation,
            )
        )

    total_questions = len(questions)
    percentage = round((correct_count / total_questions) * 100, 2) if total_questions else 0.0

    session_row.mcq_score = correct_count
    session_row.mcq_percentage = percentage
    session_row.mcq_total_questions = total_questions
    session_row.mcq_status = "submitted"
    session_row.status = "submitted"
    db.commit()

    return SubmitTestResponse(
        message="Test submitted and graded successfully.",
        session_id=session_row.session_id,
        total_questions=total_questions,
        correct_count=correct_count,
        score_text=f"{correct_count}/{total_questions}",
        percentage=percentage,
        results=results,
    )


@app.get("/interview/{session_id}/results", response_model=ResultsResponse)
async def get_results(session_id: str, db: Session = Depends(get_db)):
    session_row = db.get(InterviewSession, session_id)
    if not session_row:
        raise HTTPException(status_code=404, detail="Session not found.")

    questions = (
        db.query(MCQQuestion)
        .filter(MCQQuestion.session_id == session_id)
        .order_by(MCQQuestion.question_number.asc())
        .all()
    )

    if not questions:
        raise HTTPException(status_code=404, detail="No MCQ questions found for this session.")

    correct_count = sum(1 for q in questions if q.is_correct is True)
    total_questions = len(questions)
    percentage = round((correct_count / total_questions) * 100, 2) if total_questions else 0.0
    score_text = f"{correct_count}/{total_questions}"

    profile = {
        "skills": session_row.extracted_skills or [],
        "technologies": session_row.extracted_technologies or [],
        "years_of_experience": session_row.years_of_experience or 0.0,
    }

    question_review = [
        {
            "question_number": q.question_number,
            "question_text": q.question_text,
            "difficulty_level": q.difficulty_level,
            "selected_answer": q.selected_answer,
            "correct_answer": q.correct_answer,
            "is_correct": q.is_correct,
            "explanation": q.explanation,
        }
        for q in questions
    ]

    # Return stored report if already generated
    if session_row.mcq_report_text:
        return ResultsResponse(
            success=True,
            session_id=session_row.session_id,
            role_name=session_row.role_name,
            score_text=score_text,
            percentage=percentage,
            total_questions=total_questions,
            correct_count=correct_count,
            report_text=session_row.mcq_report_text,
            strengths=session_row.mcq_strengths or [],
            improvement_focus=session_row.mcq_focus_areas or [],
            recommendation=session_row.mcq_recommendation or "",
        )

    if RESULTS_CHAIN is not None:
        try:
            report: MCQAnalysisReport = RESULTS_CHAIN.invoke(
                {
                    "role_name": session_row.role_name,
                    "profile": profile,
                    "score_text": score_text,
                    "percentage": percentage,
                    "question_review": question_review,
                }
            )

            session_row.mcq_report_text = report.report_text
            session_row.mcq_strengths = report.strengths
            session_row.mcq_focus_areas = report.improvement_focus
            session_row.mcq_recommendation = report.recommendation
            session_row.mcq_status = "reported"
            db.commit()

            return ResultsResponse(
                success=True,
                session_id=session_row.session_id,
                role_name=session_row.role_name,
                score_text=score_text,
                percentage=percentage,
                total_questions=total_questions,
                correct_count=correct_count,
                report_text=report.report_text,
                strengths=report.strengths,
                improvement_focus=report.improvement_focus,
                recommendation=report.recommendation,
            )
        except Exception:
            pass

    # Deterministic fallback if LLM is unavailable
    strengths = [
        "Good recall of the topics you answered correctly.",
        "You completed a full MCQ assessment workflow.",
    ]

    improvement_focus = []
    weak_topics = [q.question_text for q in questions if q.is_correct is False][:5]
    if weak_topics:
        improvement_focus.extend(
            [
                "Revisit the concepts behind the questions you missed.",
                "Practice deeper conceptual understanding instead of pattern-based guessing.",
            ]
        )
    else:
        improvement_focus.append("Increase difficulty range and test speed under time pressure.")

    recommendation = (
        "Review the missed questions, revise the related fundamentals, and retake a fresh test."
    )

    report_text = (
        f"Candidate scored {score_text} ({percentage}%). "
        f"The assessment suggests strong performance in some areas, but there is room to improve "
        f"on the topics associated with incorrect responses."
    )

    session_row.mcq_report_text = report_text
    session_row.mcq_strengths = strengths
    session_row.mcq_focus_areas = improvement_focus
    session_row.mcq_recommendation = recommendation
    session_row.mcq_status = "reported"
    db.commit()

    return ResultsResponse(
        success=True,
        session_id=session_row.session_id,
        role_name=session_row.role_name,
        score_text=score_text,
        percentage=percentage,
        total_questions=total_questions,
        correct_count=correct_count,
        report_text=report_text,
        strengths=strengths,
        improvement_focus=improvement_focus,
        recommendation=recommendation,
    )