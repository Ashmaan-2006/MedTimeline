from typing import Any
from uuid import UUID

from celery import Task
from sqlalchemy.orm import Session

from medgraph_api.core.celery_app import celery_app
from medgraph_api.crud.document_chunks import DocumentChunkRepository
from medgraph_api.crud.documents import DocumentRepository
from medgraph_api.crud.timeline_events import TimelineEventRepository
from medgraph_api.db.session import SessionLocal
from medgraph_api.schemas.document import DocumentProcessingStatus, DocumentProcessingUpdate
from medgraph_api.services.chunking import TextChunkingService
from medgraph_api.services.document_processing import DocumentProcessingService
from medgraph_api.services.embeddings import HashingEmbeddingService
from medgraph_api.services.extraction import DocumentExtractionService
from medgraph_api.services.summarization import BasicAISummaryService
from medgraph_api.services.timeline_extraction import BasicTimelineEventExtractionService


def build_document_processing_service(db: Session) -> DocumentProcessingService:
    return DocumentProcessingService(
        documents=DocumentRepository(db),
        document_chunks=DocumentChunkRepository(db),
        timeline_events=TimelineEventRepository(db),
        extraction_service=DocumentExtractionService(),
        chunking_service=TextChunkingService(),
        embedding_service=HashingEmbeddingService(),
        summary_service=BasicAISummaryService(),
        timeline_extraction_service=BasicTimelineEventExtractionService(),
    )


@celery_app.task(bind=True, max_retries=3)
def process_document_task(self: Task, document_id: str) -> dict[str, Any]:
    try:
        parsed_document_id = UUID(document_id)
    except ValueError:
        return {
            "document_id": document_id,
            "status": DocumentProcessingStatus.FAILED,
            "error": "Invalid document ID.",
        }

    with SessionLocal() as db:
        documents = DocumentRepository(db)
        document = documents.get(parsed_document_id)
        if document is None:
            return {
                "document_id": document_id,
                "status": DocumentProcessingStatus.FAILED,
                "error": "Document not found.",
            }

        if self.request.id is not None:
            document = documents.update_processing(
                document,
                DocumentProcessingUpdate(
                    extracted_text=document.extracted_text,
                    summary=document.summary,
                    processing_status=DocumentProcessingStatus.QUEUED,
                    processing_error=None,
                    celery_task_id=self.request.id,
                    processing_attempts=document.processing_attempts,
                ),
            )

        try:
            processed_document = build_document_processing_service(db).process(document)
        except Exception as exc:
            if self.request.retries >= self.max_retries:
                return {
                    "document_id": document_id,
                    "status": DocumentProcessingStatus.FAILED,
                    "error": str(exc),
                }

            countdown = min(60, 2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown) from exc

    return {
        "document_id": str(processed_document.id),
        "status": processed_document.processing_status,
    }
