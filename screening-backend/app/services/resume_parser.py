# app/services/resume_parser.py

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import UploadFile


class ResumeParser:
    """
    Extract raw text from a PDF resume.

    Strategy:
    1) Save uploaded file temporarily
    2) Try PyMuPDF (fitz)
    3) Fallback to pdfplumber
    4) Clean and normalize text
    """

    def __init__(self, max_pages: Optional[int] = None) -> None:
        self.max_pages = max_pages

    async def extract_text_from_pdf(self, upload_file: UploadFile) -> str:
        """
        Accepts a FastAPI UploadFile and returns extracted raw text.

        Raises:
            ValueError: if file is invalid or text cannot be extracted.
        """
        if not upload_file.filename:
            raise ValueError("Uploaded file must have a filename.")

        file_ext = Path(upload_file.filename).suffix.lower()
        if file_ext != ".pdf":
            raise ValueError("Only PDF files are supported for resume upload.")

        content = await upload_file.read()
        if not content:
            raise ValueError("Uploaded PDF is empty.")

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                temp_path = tmp.name

            text = self._extract_with_pymupdf(temp_path)

            if not text.strip():
                text = self._extract_with_pdfplumber(temp_path)

            text = self._clean_text(text)

            if not text.strip():
                raise ValueError(
                    "No extractable text found in the PDF. "
                    "The file may be scanned/image-based and will need OCR later."
                )

            return text

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _extract_with_pymupdf(self, pdf_path: str) -> str:
        """
        Extract text using PyMuPDF.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return ""

        text_parts = []
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
            page_limit = self.max_pages if self.max_pages else total_pages
            page_limit = min(page_limit, total_pages)

            for i in range(page_limit):
                page = doc[i]
                page_text = page.get_text("text") or ""
                if page_text.strip():
                    text_parts.append(page_text)

        return "\n".join(text_parts)

    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """
        Extract text using pdfplumber as a fallback.
        """
        try:
            import pdfplumber
        except ImportError:
            return ""

        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            page_limit = self.max_pages if self.max_pages else total_pages
            page_limit = min(page_limit, total_pages)

            for i in range(page_limit):
                page = pdf.pages[i]
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(page_text)

        return "\n".join(text_parts)

    def _clean_text(self, text: str) -> str:
        """
        Normalize whitespace and remove noisy repeated spaces.
        """
        if not text:
            return ""

        text = text.replace("\x00", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" +\n", "\n", text)
        return text.strip()