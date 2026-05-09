# app/vectorstore/chroma_store.py

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


class ChromaKnowledgeBase:
    """
    Persistent local vector store for role-specific textbook/corpus chunks.
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ) -> None:
        self.persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self.collection_name = collection_name or os.getenv(
            "CHROMA_COLLECTION_NAME", "textbook_kb"
        )
        self.embedding_model = embedding_model or os.getenv(
            "CHROMA_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
        )

        self.client = chromadb.PersistentClient(path=self.persist_dir)

        # Local embedding function; no OpenAI dependency for the KB.
        self.embedding_function = SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model,
            device="cpu",
            normalize_embeddings=False,
        )

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={
                "description": "Role-specific textbook knowledge base for candidate screening"
            },
        )

    def upsert_chunks(
        self,
        ids: List[str],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> None:
        if not ids or not documents:
            raise ValueError("ids and documents cannot be empty.")
        if len(ids) != len(documents) or len(ids) != len(metadatas):
            raise ValueError("ids, documents, and metadatas must have the same length.")

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, query: str, top_k: int = 4) -> Dict[str, Any]:
        if not query or not query.strip():
            raise ValueError("query cannot be empty.")

        return self.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )