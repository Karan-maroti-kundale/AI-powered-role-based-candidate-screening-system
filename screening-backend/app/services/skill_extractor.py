# app/services/skill_extractor.py

from __future__ import annotations

import os
import re
from typing import List, Set

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, conlist, confloat


class CandidateProfile(BaseModel):
    skills: conlist(str, min_length=0) = Field(
        default_factory=list,
        description="Core candidate skills inferred from the resume.",
    )
    technologies: conlist(str, min_length=0) = Field(
        default_factory=list,
        description="Tools, frameworks, libraries, databases, cloud platforms, and languages.",
    )
    years_of_experience: confloat(ge=0) = Field(
        default=0.0,
        description="Estimated total years of professional or project experience.",
    )


class SkillExtractor:
    """
    Uses LangChain + OpenAI structured output to convert resume text into a
    predictable JSON object.

    If OpenAI is unavailable or quota is exhausted, falls back to a local
    heuristic extractor so the system does not break during the interview flow.
    """

    def __init__(
        self,
        model_name: str | None = None,
        temperature: float = 0.0,
        max_resume_chars: int = 12000,
    ) -> None:
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature
        self.max_resume_chars = max_resume_chars
        self.api_key = os.getenv("OPENAI_API_KEY")

        self.llm = None
        self.structured_llm = None
        self.chain = None

        if self.api_key:
            # LangChain/OpenAI will read credentials from the environment.
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
            )

            self.prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        (
                            "You are an expert resume parser for technical hiring. "
                            "Extract only factual information grounded in the resume text. "
                            "Do not hallucinate. If something is unclear, omit it or use an empty list. "
                            "Estimate total years of experience only from explicit evidence in the resume."
                        ),
                    ),
                    (
                        "user",
                        (
                            "Parse this resume and return a structured profile.\n\n"
                            "Resume text:\n{resume_text}"
                        ),
                    ),
                ]
            )

            self.structured_llm = self.llm.with_structured_output(
                CandidateProfile,
                method="json_schema",
            )

            self.chain = self.prompt | self.structured_llm

    def extract_profile(self, resume_text: str) -> dict:
        """
        Returns:
            dict with keys:
            - skills: list[str]
            - technologies: list[str]
            - years_of_experience: float
        """
        if not resume_text or not resume_text.strip():
            raise ValueError("resume_text is empty.")

        truncated_text = resume_text[: self.max_resume_chars]

        # Primary path: LLM extraction
        if self.chain is not None:
            try:
                result: CandidateProfile = self.chain.invoke(
                    {"resume_text": truncated_text}
                )
                return result.model_dump()
            except Exception:
                # Fall back to local extraction on quota/rate-limit/API issues.
                pass

        # Fallback path: deterministic heuristic extraction
        return self._fallback_extract(truncated_text)

    def _fallback_extract(self, text: str) -> dict:
        lowered = text.lower()

        tech_patterns = [
            "python", "java", "javascript", "typescript", "react", "next.js",
            "fastapi", "flask", "django", "pytorch", "tensorflow", "keras",
            "scikit-learn", "sklearn", "pandas", "numpy", "matplotlib",
            "sql", "postgresql", "mysql", "mongodb", "redis", "sqlite",
            "docker", "kubernetes", "aws", "gcp", "azure", "linux",
            "langchain", "llamaindex", "chromadb", "faiss", "openai",
            "hugging face", "nlp", "computer vision", "cnn", "rnn",
            "transformer", "llm", "rag", "api", "rest", "microservices",
            "git", "github", "ci/cd",
        ]

        skill_patterns = [
            "machine learning", "deep learning", "data analysis", "data science",
            "backend development", "api development", "model training",
            "model deployment", "feature engineering", "prompt engineering",
            "problem solving", "system design", "testing", "debugging",
            "retrieval augmented generation", "rag", "nlp", "computer vision",
        ]

        technologies = self._match_keywords(lowered, tech_patterns)
        skills = self._match_keywords(lowered, skill_patterns)

        years = self._extract_years_of_experience(text)

        return CandidateProfile(
            skills=skills,
            technologies=technologies,
            years_of_experience=years,
        ).model_dump()

    def _match_keywords(self, text: str, keywords: List[str]) -> List[str]:
        found: List[str] = []
        seen: Set[str] = set()

        for kw in keywords:
            if kw in text and kw not in seen:
                seen.add(kw)
                found.append(kw)

        return found

    def _extract_years_of_experience(self, text: str) -> float:
        """
        Looks for patterns like:
        - 3 years
        - 3+ years
        - 2 yrs
        - 2.5 years
        """
        patterns = [
            r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience)?",
            r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b",
        ]

        matches: List[float] = []
        for pattern in patterns:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                try:
                    matches.append(float(m.group(1)))
                except ValueError:
                    continue

        if matches:
            return max(matches)

        # Weak heuristic fallback when explicit years are not stated.
        lowered = text.lower()
        if "intern" in lowered or "internship" in lowered:
            return 0.5

        return 0.0