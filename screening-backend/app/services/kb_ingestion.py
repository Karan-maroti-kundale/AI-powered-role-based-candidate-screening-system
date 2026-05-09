# app/services/kb_ingestion.py

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4
from typing import Any, Dict, List

from langchain_community.document_loaders import PyPDFLoader

from app.vectorstore.chroma_store import ChromaKnowledgeBase


class KnowledgeBaseIngestor:
    """
    Loads a PDF, chunks it, and stores the chunks in Chroma.
    """

    def __init__(
        self,
        chunk_size: int = 900,
        chunk_overlap: int = 120,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.kb = ChromaKnowledgeBase()

    def ingest_pdf(
        self,
        pdf_path: str,
        role_name: str,
        source_name: str | None = None,
        topic_hint: str | None = None,
    ) -> Dict[str, Any]:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files are supported for ingestion.")

        loader = PyPDFLoader(str(path))
        pages = loader.load()

        chunk_ids: List[str] = []
        chunk_docs: List[str] = []
        chunk_metas: List[Dict[str, Any]] = []

        for page_index, doc in enumerate(pages):
            page_text = (doc.page_content or "").strip()
            if not page_text:
                continue

            chunks = self._chunk_text(page_text)

            for chunk_index, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                chunk_ids.append(str(uuid4()))
                chunk_docs.append(chunk)
                chunk_metas.append(
                    {
                        "role_name": role_name,
                        "source_name": source_name or path.name,
                        "topic_hint": topic_hint or role_name,
                        "page_number": doc.metadata.get("page", page_index),
                        "chunk_index": chunk_index,
                        "source_type": "pdf",
                    }
                )

        if not chunk_docs:
            raise ValueError("No text chunks were extracted from the PDF.")

        self.kb.upsert_chunks(
            ids=chunk_ids,
            documents=chunk_docs,
            metadatas=chunk_metas,
        )

        return {
            "success": True,
            "role_name": role_name,
            "source_name": source_name or path.name,
            "chunks_ingested": len(chunk_docs),
        }

    def _chunk_text(self, text: str) -> List[str]:
        """
        Simple deterministic chunker.
        Keeps paragraphs together as much as possible, then hard-splits long blocks.
        """
        normalized = re.sub(r"\r\n", "\n", text).strip()
        paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]

        chunks: List[str] = []
        current = ""

        for para in paragraphs:
            if len(para) > self.chunk_size:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._split_long_text(para))
                continue

            if not current:
                current = para
            elif len(current) + len(para) + 2 <= self.chunk_size:
                current = f"{current}\n\n{para}"
            else:
                chunks.append(current.strip())
                current = para

        if current.strip():
            chunks.append(current.strip())

        # Add overlap by lightly stitching the tail of previous chunk to the next.
        if self.chunk_overlap > 0 and len(chunks) > 1:
            overlapped: List[str] = []
            prev_tail = ""
            for chunk in chunks:
                if prev_tail:
                    merged = f"{prev_tail}\n\n{chunk}"
                    overlapped.append(merged[: self.chunk_size + self.chunk_overlap])
                else:
                    overlapped.append(chunk)
                prev_tail = chunk[-self.chunk_overlap :]
            chunks = overlapped

        return chunks

    def _split_long_text(self, text: str) -> List[str]:
        words = text.split()
        if not words:
            return []

        parts: List[str] = []
        buffer: List[str] = []
        buffer_len = 0

        for word in words:
            word_len = len(word) + 1
            if buffer and buffer_len + word_len > self.chunk_size:
                parts.append(" ".join(buffer).strip())
                buffer = [word]
                buffer_len = len(word) + 1
            else:
                buffer.append(word)
                buffer_len += word_len

        if buffer:
            parts.append(" ".join(buffer).strip())

        return parts