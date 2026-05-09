# scripts/ingest_backend_engineering.py

from app.services.kb_ingestion import KnowledgeBaseIngestor

if __name__ == "__main__":
    ingestor = KnowledgeBaseIngestor(
        chunk_size=900,
        chunk_overlap=120,
    )

    result = ingestor.ingest_pdf(
        pdf_path="data/knowledge_base/backend_engineer/backend_engineering.pdf",
        role_name="Backend Engineer",
        source_name="backend_engineering.pdf",
        topic_hint="backend engineering fundamentals",
    )

    print(result)