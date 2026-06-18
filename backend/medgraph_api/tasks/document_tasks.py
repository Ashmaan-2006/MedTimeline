from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery import Task
from neo4j.exceptions import ServiceUnavailable, TransientError
from sqlalchemy.exc import DisconnectionError, OperationalError
from sqlalchemy.orm import Session

from medgraph_api.core.celery_app import celery_app
from medgraph_api.core.neo4j import neo4j_session
from medgraph_api.crud.document_chunks import DocumentChunkRepository
from medgraph_api.crud.documents import DocumentRepository
from medgraph_api.crud.timeline_events import TimelineEventRepository
from medgraph_api.db.session import SessionLocal
from medgraph_api.repositories.clinical_graph_repository import ClinicalGraphRepository
from medgraph_api.schemas.document import DocumentProcessingStatus, DocumentProcessingUpdate
from medgraph_api.services.chunking import TextChunkingService
from medgraph_api.services.clinical_graph_sync import ClinicalGraphSyncService
from medgraph_api.services.document_processing import DocumentProcessingService
from medgraph_api.services.embeddings import HashingEmbeddingService
from medgraph_api.services.entity_extraction_service import ClinicalEntityExtractionService
from medgraph_api.services.extraction import DocumentExtractionService
from medgraph_api.services.local_clinical_llm import (
    LocalClinicalEntityLLMClient,
    LocalClinicalRelationshipLLMClient,
)
from medgraph_api.services.processing_errors import (
    PermanentDocumentProcessingError,
    TemporaryDocumentProcessingError,
)
from medgraph_api.services.relationship_extraction_service import (
    ClinicalRelationshipExtractionService,
)
from medgraph_api.services.summarization import BasicAISummaryService
from medgraph_api.services.timeline_extraction import BasicTimelineEventExtractionService

FINAL_TEMPORARY_FAILURE_MESSAGE = (
    "Document processing is temporarily unavailable. Try uploading the document again."
)


def build_document_processing_service(
    db: Session,
    graph_sync_service: ClinicalGraphSyncService | None = None,
) -> DocumentProcessingService:
    return DocumentProcessingService(
        documents=DocumentRepository(db),
        document_chunks=DocumentChunkRepository(db),
        timeline_events=TimelineEventRepository(db),
        extraction_service=DocumentExtractionService(),
        chunking_service=TextChunkingService(),
        embedding_service=HashingEmbeddingService(),
        summary_service=BasicAISummaryService(),
        timeline_extraction_service=BasicTimelineEventExtractionService(),
        graph_sync_service=graph_sync_service,
        entity_extraction_service=ClinicalEntityExtractionService(LocalClinicalEntityLLMClient()),
        relationship_extraction_service=ClinicalRelationshipExtractionService(
            LocalClinicalRelationshipLLMClient()
        ),
    )


def is_retryable_processing_exception(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            TemporaryDocumentProcessingError,
            OperationalError,
            DisconnectionError,
            ServiceUnavailable,
            TimeoutError,
            TransientError,
        ),
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

    try:
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
                with neo4j_session() as graph_session:
                    graph_sync_service = ClinicalGraphSyncService(
                        ClinicalGraphRepository(graph_session)
                    )
                    graph_sync_service.sync_document(document)
                    processed_document = build_document_processing_service(
                        db,
                        graph_sync_service=graph_sync_service,
                    ).process(document)
            except PermanentDocumentProcessingError as exc:
                processed_document = documents.update_processing(
                    document,
                    DocumentProcessingUpdate(
                        extracted_text=document.extracted_text,
                        summary=document.summary,
                        processing_status=DocumentProcessingStatus.FAILED,
                        processing_error=exc.safe_message,
                        processing_started_at=document.processing_started_at,
                        processing_completed_at=datetime.now(UTC),
                        processing_attempts=document.processing_attempts,
                    ),
                )
            except Exception as exc:
                if not is_retryable_processing_exception(exc):
                    processed_document = documents.update_processing(
                        document,
                        DocumentProcessingUpdate(
                            extracted_text=document.extracted_text,
                            summary=document.summary,
                            processing_status=DocumentProcessingStatus.FAILED,
                            processing_error="Document processing failed.",
                            processing_started_at=document.processing_started_at,
                            processing_completed_at=datetime.now(UTC),
                            processing_attempts=document.processing_attempts,
                        ),
                    )
                    return {
                        "document_id": str(processed_document.id),
                        "status": processed_document.processing_status,
                        "error": processed_document.processing_error,
                    }

                if self.request.retries >= self.max_retries:
                    processed_document = documents.update_processing(
                        document,
                        DocumentProcessingUpdate(
                            extracted_text=document.extracted_text,
                            summary=document.summary,
                            processing_status=DocumentProcessingStatus.FAILED,
                            processing_error=FINAL_TEMPORARY_FAILURE_MESSAGE,
                            processing_started_at=document.processing_started_at,
                            processing_completed_at=datetime.now(UTC),
                            processing_attempts=document.processing_attempts,
                        ),
                    )
                    return {
                        "document_id": str(processed_document.id),
                        "status": processed_document.processing_status,
                        "error": processed_document.processing_error,
                    }

                countdown = min(60, 2 ** self.request.retries)
                raise self.retry(exc=exc, countdown=countdown) from exc

        return {
            "document_id": str(processed_document.id),
            "status": processed_document.processing_status,
        }
    except Exception as exc:
        if not is_retryable_processing_exception(exc):
            raise

        if self.request.retries >= self.max_retries:
            return {
                "document_id": document_id,
                "status": DocumentProcessingStatus.FAILED,
                "error": FINAL_TEMPORARY_FAILURE_MESSAGE,
            }

        countdown = min(60, 2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown) from exc
