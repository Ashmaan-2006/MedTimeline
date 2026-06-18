from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from medgraph_api.schemas.document import DocumentProcessingUpdate
from medgraph_api.schemas.document_chunk import DocumentChunkCreate
from medgraph_api.schemas.clinical_entity import (
    ExtractedClinicalEntities,
    ExtractedClinicalEntity,
)
from medgraph_api.schemas.clinical_relationship import (
    ExtractedClinicalRelationship,
    ExtractedClinicalRelationships,
)
from medgraph_api.schemas.timeline_event import TimelineEventCreate
from medgraph_api.services.chunking import TextChunk
from medgraph_api.services.document_processing import DocumentProcessingService
from medgraph_api.services.embeddings import TextEmbedding
from medgraph_api.services.extraction import UnsupportedDocumentTypeError
from medgraph_api.services.processing_errors import TemporaryDocumentProcessingError


@dataclass
class FakeDocument:
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


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.updates: list[DocumentProcessingUpdate] = []

    def update_processing(
        self,
        document: FakeDocument,
        payload: DocumentProcessingUpdate,
    ) -> FakeDocument:
        self.updates.append(payload)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(document, field, value)
        document.updated_at = datetime.now(UTC)
        return document


class FakeDocumentChunkRepository:
    def __init__(self) -> None:
        self.document_id: UUID | None = None
        self.chunks: list[DocumentChunkCreate] = []

    def replace_for_document(
        self,
        document_id: UUID,
        payloads: list[DocumentChunkCreate],
    ) -> list[DocumentChunkCreate]:
        self.document_id = document_id
        self.chunks = payloads
        return payloads


@dataclass
class FakeStoredChunk:
    id: UUID
    patient_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    embedding_model: str | None
    token_count: int | None
    chunk_metadata: dict | None
    created_at: datetime


class FakeStoredDocumentChunkRepository:
    def __init__(self) -> None:
        self.chunks: list[FakeStoredChunk] = []

    def replace_for_document(
        self,
        document_id: UUID,
        payloads: list[DocumentChunkCreate],
    ) -> list[FakeStoredChunk]:
        self.chunks = [
            FakeStoredChunk(
                id=uuid4(),
                patient_id=payload.patient_id,
                document_id=document_id,
                chunk_index=payload.chunk_index,
                content=payload.content,
                embedding_model=payload.embedding_model,
                token_count=payload.token_count,
                chunk_metadata=payload.chunk_metadata,
                created_at=datetime.now(UTC),
            )
            for payload in payloads
        ]
        return self.chunks


class FakeTimelineEventRepository:
    def __init__(self) -> None:
        self.events: list[TimelineEventCreate] = []

    def create_many(self, payloads: list[TimelineEventCreate]) -> list[TimelineEventCreate]:
        self.events.extend(payloads)
        return payloads


class FakeExtractionService:
    def __init__(self, text: str = "2026-01-05 Patient reports chest discomfort.") -> None:
        self.text = text
        self.storage_path: str | None = None
        self.content_type: str | None = None

    def extract_text(self, storage_path: str, content_type: str | None) -> str:
        self.storage_path = storage_path
        self.content_type = content_type
        return self.text


class FailingExtractionService:
    def extract_text(self, storage_path: str, content_type: str | None) -> str:
        raise UnsupportedDocumentTypeError


class FakeSummaryService:
    def summarize(self, text: str) -> str:
        return f"Summary: {text}"


class FailingSummaryService:
    def summarize(self, text: str) -> str:
        raise RuntimeError("provider stack trace with secret token")


class FakeChunkingService:
    def chunk_text(self, text: str) -> list[TextChunk]:
        return [
            TextChunk(
                chunk_index=0,
                content=text,
                token_count=len(text.split()),
                metadata={"char_start": 0, "char_end": len(text)},
            )
        ]


class FakeEmbeddingService:
    def embed_texts(self, texts: list[str]) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                text=text,
                embedding=[0.1, 0.2, 0.3],
                embedding_model="fake-embedding-v1",
            )
            for text in texts
        ]


class FakeTimelineExtractionService:
    def extract_events(
        self,
        patient_id: UUID,
        source_document_id: UUID,
        text: str,
    ) -> list[TimelineEventCreate]:
        return [
            TimelineEventCreate(
                patient_id=patient_id,
                source_document_id=source_document_id,
                occurred_at=None,
                event_type="symptom",
                title="Chest discomfort",
                description=text,
                evidence_text=text,
                confidence=0.65,
                event_metadata={"extractor": "fake"},
            )
        ]


class FakeEntityExtractionService:
    def __init__(self) -> None:
        self.chunk_ids: list[UUID] = []

    def extract_entities(self, source_chunk_id: UUID, chunk_text: str) -> ExtractedClinicalEntities:
        self.chunk_ids.append(source_chunk_id)
        return ExtractedClinicalEntities(
            entities=[
                ExtractedClinicalEntity(
                    entity_type="symptom",
                    name="chest discomfort",
                    normalized_name="chest discomfort",
                    source_chunk_id=source_chunk_id,
                    confidence=0.81,
                    evidence_quote=chunk_text,
                )
            ]
        )


class FakeRelationshipExtractionService:
    def __init__(self) -> None:
        self.chunk_ids: list[UUID] = []

    def extract_relationships(
        self,
        source_chunk_id: UUID,
        chunk_text: str,
        entities: ExtractedClinicalEntities,
    ) -> ExtractedClinicalRelationships:
        self.chunk_ids.append(source_chunk_id)
        return ExtractedClinicalRelationships(
            relationships=[
                ExtractedClinicalRelationship(
                    source="chest discomfort",
                    target="chest discomfort",
                    type="ASSOCIATED_WITH",
                    source_chunk_id=source_chunk_id,
                    evidence=chunk_text,
                    confidence=0.61,
                )
            ]
        )


class FakeGraphSyncService:
    def __init__(self) -> None:
        self.documents: list[FakeDocument] = []
        self.chunks: list[list[FakeStoredChunk]] = []
        self.entity_calls: list[tuple[FakeStoredChunk, ExtractedClinicalEntities]] = []
        self.relationship_calls: list[
            tuple[ExtractedClinicalEntities, ExtractedClinicalRelationships]
        ] = []

    def sync_document(self, document: FakeDocument) -> None:
        self.documents.append(document)

    def sync_chunks(self, chunks: list[FakeStoredChunk]) -> None:
        self.chunks.append(chunks)

    def sync_entities_for_chunk(
        self,
        chunk: FakeStoredChunk,
        entities: ExtractedClinicalEntities,
    ) -> None:
        self.entity_calls.append((chunk, entities))

    def sync_relationships(
        self,
        entities: ExtractedClinicalEntities,
        relationships: ExtractedClinicalRelationships,
    ) -> None:
        self.relationship_calls.append((entities, relationships))


@pytest.fixture
def document() -> FakeDocument:
    now = datetime.now(UTC)
    return FakeDocument(
        id=uuid4(),
        patient_id=uuid4(),
        filename="note.txt",
        content_type="text/plain",
        storage_path="storage/uploads/note.txt",
        extracted_text=None,
        summary=None,
        processing_status="uploaded",
        processing_error=None,
        processing_started_at=None,
        processing_completed_at=None,
        celery_task_id=None,
        processing_attempts=0,
        created_at=now,
        updated_at=now,
    )


def test_document_processing_service_runs_full_pipeline(document: FakeDocument) -> None:
    documents = FakeDocumentRepository()
    document_chunks = FakeDocumentChunkRepository()
    timeline_events = FakeTimelineEventRepository()
    extraction_service = FakeExtractionService()
    service = DocumentProcessingService(
        documents=documents,
        document_chunks=document_chunks,
        timeline_events=timeline_events,
        extraction_service=extraction_service,
        chunking_service=FakeChunkingService(),
        embedding_service=FakeEmbeddingService(),
        summary_service=FakeSummaryService(),
        timeline_extraction_service=FakeTimelineExtractionService(),
    )

    processed_document = service.process(document)

    assert processed_document.processing_status == "completed"
    assert processed_document.processing_error is None
    assert processed_document.processing_started_at is not None
    assert processed_document.processing_completed_at is not None
    assert processed_document.processing_attempts == 1
    assert processed_document.extracted_text == extraction_service.text
    assert processed_document.summary == f"Summary: {extraction_service.text}"
    assert extraction_service.storage_path == document.storage_path
    assert extraction_service.content_type == document.content_type
    assert document_chunks.document_id == document.id
    assert len(document_chunks.chunks) == 1
    assert document_chunks.chunks[0].content == extraction_service.text
    assert document_chunks.chunks[0].embedding_model == "fake-embedding-v1"
    assert len(timeline_events.events) == 1
    assert timeline_events.events[0].source_document_id == document.id
    assert [update.processing_status for update in documents.updates] == [
        "processing",
        "processing",
        "completed",
    ]


def test_document_processing_service_builds_clinical_graph(document: FakeDocument) -> None:
    documents = FakeDocumentRepository()
    document_chunks = FakeStoredDocumentChunkRepository()
    timeline_events = FakeTimelineEventRepository()
    graph_sync_service = FakeGraphSyncService()
    entity_extraction_service = FakeEntityExtractionService()
    relationship_extraction_service = FakeRelationshipExtractionService()
    service = DocumentProcessingService(
        documents=documents,
        document_chunks=document_chunks,
        timeline_events=timeline_events,
        extraction_service=FakeExtractionService(),
        chunking_service=FakeChunkingService(),
        embedding_service=FakeEmbeddingService(),
        summary_service=FakeSummaryService(),
        timeline_extraction_service=FakeTimelineExtractionService(),
        graph_sync_service=graph_sync_service,
        entity_extraction_service=entity_extraction_service,
        relationship_extraction_service=relationship_extraction_service,
    )

    service.process(document)

    stored_chunk = document_chunks.chunks[0]
    assert graph_sync_service.chunks == [[stored_chunk]]
    assert entity_extraction_service.chunk_ids == [stored_chunk.id]
    assert relationship_extraction_service.chunk_ids == [stored_chunk.id]
    assert graph_sync_service.entity_calls[0][0] == stored_chunk
    assert graph_sync_service.relationship_calls[0][1].relationships[0].type == "ASSOCIATED_WITH"


def test_document_processing_service_marks_unsupported_documents_failed(
    document: FakeDocument,
) -> None:
    documents = FakeDocumentRepository()
    document_chunks = FakeDocumentChunkRepository()
    timeline_events = FakeTimelineEventRepository()
    service = DocumentProcessingService(
        documents=documents,
        document_chunks=document_chunks,
        timeline_events=timeline_events,
        extraction_service=FailingExtractionService(),
        chunking_service=FakeChunkingService(),
        embedding_service=FakeEmbeddingService(),
        summary_service=FakeSummaryService(),
        timeline_extraction_service=FakeTimelineExtractionService(),
    )

    processed_document = service.process(document)

    assert processed_document.processing_status == "failed"
    assert processed_document.processing_error == "Unsupported document type."
    assert processed_document.processing_started_at is not None
    assert processed_document.processing_completed_at is not None
    assert processed_document.processing_attempts == 1
    assert document_chunks.chunks == []
    assert timeline_events.events == []
    assert [update.processing_status for update in documents.updates] == [
        "processing",
        "failed",
    ]


def test_document_processing_service_stores_safe_message_for_temporary_failures(
    document: FakeDocument,
) -> None:
    documents = FakeDocumentRepository()
    document_chunks = FakeDocumentChunkRepository()
    timeline_events = FakeTimelineEventRepository()
    service = DocumentProcessingService(
        documents=documents,
        document_chunks=document_chunks,
        timeline_events=timeline_events,
        extraction_service=FakeExtractionService(),
        chunking_service=FakeChunkingService(),
        embedding_service=FakeEmbeddingService(),
        summary_service=FailingSummaryService(),
        timeline_extraction_service=FakeTimelineExtractionService(),
    )

    with pytest.raises(TemporaryDocumentProcessingError):
        service.process(document)

    assert document.processing_status == "processing"
    assert document.processing_error == "Temporary processing issue. Retrying automatically."
    assert "secret token" not in document.processing_error
    assert document.processing_completed_at is None
    assert document.processing_attempts == 1
    assert document_chunks.chunks == []
    assert timeline_events.events == []
