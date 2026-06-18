from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from medgraph_api.schemas.document import DocumentCreate, DocumentProcessingUpdate
from medgraph_api.services.chunking import TextChunk
from medgraph_api.services.document_processing import DocumentProcessingService
from medgraph_api.services.embeddings import TextEmbedding
from medgraph_api.services.processing_errors import TemporaryDocumentProcessingError
from medgraph_api.tasks.document_tasks import is_retryable_processing_exception


@dataclass
class AsyncDocument:
    id: UUID
    patient_id: UUID
    filename: str
    content_type: str | None
    storage_path: str
    extracted_text: str | None
    summary: str | None
    processing_status: str
    processing_error: str | None
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    celery_task_id: str | None
    processing_attempts: int
    created_at: datetime
    updated_at: datetime


class AsyncDocumentRepository:
    def __init__(self) -> None:
        self.documents: list[AsyncDocument] = []
        self.status_history: list[str] = []

    def create(self, payload: DocumentCreate) -> AsyncDocument:
        now = datetime.now(UTC)
        document = AsyncDocument(
            id=uuid4(),
            extracted_text=None,
            summary=None,
            processing_error=None,
            processing_started_at=None,
            processing_completed_at=None,
            celery_task_id=None,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        self.documents.append(document)
        return document

    def update_processing(
        self,
        document: AsyncDocument,
        payload: DocumentProcessingUpdate,
    ) -> AsyncDocument:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(document, field, value)
        document.updated_at = datetime.now(UTC)
        self.status_history.append(str(document.processing_status))
        return document


class ReplacingChunkRepository:
    def __init__(self) -> None:
        self.chunks: list[object] = ["stale chunk"]
        self.replace_calls = 0

    def replace_for_document(self, document_id: UUID, payloads: list[object]) -> list[object]:
        self.replace_calls += 1
        self.chunks = payloads
        return payloads


class RecordingTimelineRepository:
    def __init__(self) -> None:
        self.events: list[object] = []

    def create_many(self, payloads: list[object]) -> list[object]:
        self.events.extend(payloads)
        return payloads


class StaticExtractionService:
    def extract_text(self, storage_path: str, content_type: str | None) -> str:
        return "Patient reports chest discomfort."


class StaticSummaryService:
    def summarize(self, text: str) -> str:
        return "Patient reports chest discomfort."


class FailingSummaryService:
    def summarize(self, text: str) -> str:
        raise RuntimeError("raw provider timeout with stack details")


class StaticChunkingService:
    def chunk_text(self, text: str) -> list[TextChunk]:
        return [
            TextChunk(
                chunk_index=0,
                content=text,
                token_count=len(text.split()),
                metadata={"char_start": 0, "char_end": len(text)},
            )
        ]


class StaticEmbeddingService:
    def embed_texts(self, texts: list[str]) -> list[TextEmbedding]:
        return [
            TextEmbedding(text=text, embedding=[0.1, 0.2, 0.3], embedding_model="test-model")
            for text in texts
        ]


class EmptyTimelineExtractionService:
    def extract_events(self, patient_id: UUID, source_document_id: UUID, text: str) -> list[object]:
        return []


def create_queued_document(repository: AsyncDocumentRepository) -> AsyncDocument:
    document = repository.create(
        DocumentCreate(
            patient_id=uuid4(),
            filename="note.txt",
            content_type="text/plain",
            storage_path="storage/uploads/note.txt",
        )
    )
    return repository.update_processing(
        document,
        DocumentProcessingUpdate(
            extracted_text=None,
            summary=None,
            processing_status="queued",
            processing_error=None,
            celery_task_id="task-123",
            processing_attempts=0,
        ),
    )


def build_processing_service(
    documents: AsyncDocumentRepository,
    chunks: ReplacingChunkRepository,
    summary_service: object,
) -> DocumentProcessingService:
    return DocumentProcessingService(
        documents=documents,
        document_chunks=chunks,
        timeline_events=RecordingTimelineRepository(),
        extraction_service=StaticExtractionService(),
        chunking_service=StaticChunkingService(),
        embedding_service=StaticEmbeddingService(),
        summary_service=summary_service,
        timeline_extraction_service=EmptyTimelineExtractionService(),
    )


def test_upload_lifecycle_creates_queued_document() -> None:
    documents = AsyncDocumentRepository()

    document = create_queued_document(documents)

    assert document.processing_status == "queued"
    assert document.celery_task_id == "task-123"
    assert document.processing_attempts == 0


def test_successful_async_processing_moves_from_processing_to_completed() -> None:
    documents = AsyncDocumentRepository()
    chunks = ReplacingChunkRepository()
    document = create_queued_document(documents)
    service = build_processing_service(documents, chunks, StaticSummaryService())

    processed_document = service.process(document)

    assert processed_document.processing_status == "completed"
    assert processed_document.processing_error is None
    assert documents.status_history[-2:] == ["processing", "completed"]
    assert processed_document.processing_started_at is not None
    assert processed_document.processing_completed_at is not None


def test_failed_async_processing_stores_safe_failure_state() -> None:
    documents = AsyncDocumentRepository()
    chunks = ReplacingChunkRepository()
    document = create_queued_document(documents)
    service = build_processing_service(documents, chunks, FailingSummaryService())

    with pytest.raises(TemporaryDocumentProcessingError):
        service.process(document)

    assert document.processing_status == "processing"
    assert document.processing_error == "Temporary processing issue. Retrying automatically."
    assert "stack details" not in document.processing_error
    assert is_retryable_processing_exception(TemporaryDocumentProcessingError("temporary"))


def test_reprocessing_replaces_chunks_without_duplication() -> None:
    documents = AsyncDocumentRepository()
    chunks = ReplacingChunkRepository()
    document = create_queued_document(documents)
    service = build_processing_service(documents, chunks, StaticSummaryService())

    service.process(document)

    assert chunks.replace_calls == 1
    assert len(chunks.chunks) == 1
    assert chunks.chunks[0].content == "Patient reports chest discomfort."
