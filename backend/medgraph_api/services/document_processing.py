from datetime import UTC, datetime

from medgraph_api.crud.document_chunks import DocumentChunkRepository
from medgraph_api.crud.documents import DocumentRepository
from medgraph_api.crud.timeline_events import TimelineEventRepository
from medgraph_api.models.document import Document
from medgraph_api.models.document_chunk import DocumentChunk
from medgraph_api.schemas.document import DocumentProcessingStatus, DocumentProcessingUpdate
from medgraph_api.schemas.document_chunk import DocumentChunkCreate
from medgraph_api.services.chunking import TextChunkingService
from medgraph_api.services.clinical_graph_sync import ClinicalGraphSyncService
from medgraph_api.services.embeddings import HashingEmbeddingService
from medgraph_api.services.entity_extraction_service import ClinicalEntityExtractionService
from medgraph_api.services.extraction import DocumentExtractionService
from medgraph_api.services.processing_errors import (
    PermanentDocumentProcessingError,
    TemporaryDocumentProcessingError,
)
from medgraph_api.services.relationship_extraction_service import (
    ClinicalRelationshipExtractionService,
)
from medgraph_api.services.summarization import BasicAISummaryService
from medgraph_api.services.timeline_extraction import BasicTimelineEventExtractionService

RETRYABLE_PROCESSING_ERROR_MESSAGE = "Temporary processing issue. Retrying automatically."


class DocumentProcessingService:
    def __init__(
        self,
        documents: DocumentRepository,
        document_chunks: DocumentChunkRepository,
        timeline_events: TimelineEventRepository,
        extraction_service: DocumentExtractionService,
        chunking_service: TextChunkingService,
        embedding_service: HashingEmbeddingService,
        summary_service: BasicAISummaryService,
        timeline_extraction_service: BasicTimelineEventExtractionService,
        graph_sync_service: ClinicalGraphSyncService | None = None,
        entity_extraction_service: ClinicalEntityExtractionService | None = None,
        relationship_extraction_service: ClinicalRelationshipExtractionService | None = None,
    ) -> None:
        self.documents = documents
        self.document_chunks = document_chunks
        self.timeline_events = timeline_events
        self.extraction_service = extraction_service
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.summary_service = summary_service
        self.timeline_extraction_service = timeline_extraction_service
        self.graph_sync_service = graph_sync_service
        self.entity_extraction_service = entity_extraction_service
        self.relationship_extraction_service = relationship_extraction_service

    def process(self, document: Document) -> Document:
        attempt_number = document.processing_attempts + 1
        processing_started_at = datetime.now(UTC)
        processing_document = self.documents.update_processing(
            document,
            DocumentProcessingUpdate(
                extracted_text=document.extracted_text,
                summary=document.summary,
                processing_status=DocumentProcessingStatus.PROCESSING,
                processing_error=None,
                processing_started_at=processing_started_at,
                processing_completed_at=None,
                processing_attempts=attempt_number,
            ),
        )

        try:
            if self.graph_sync_service is not None:
                self.graph_sync_service.sync_document(processing_document)

            extracted_text = self.extraction_service.extract_text(
                storage_path=processing_document.storage_path,
                content_type=processing_document.content_type,
            )
            summary = self.summary_service.summarize(extracted_text)
            processing_document = self.documents.update_processing(
                processing_document,
                DocumentProcessingUpdate(
                    extracted_text=extracted_text,
                    summary=summary,
                    processing_status=DocumentProcessingStatus.PROCESSING,
                    processing_error=None,
                    processing_started_at=processing_started_at,
                    processing_completed_at=None,
                    processing_attempts=attempt_number,
                ),
            )

            stored_chunks = self._store_chunks(processing_document, extracted_text)
            self._store_timeline_events(processing_document, extracted_text)
            self._build_clinical_graph(stored_chunks)

            completed_document = self.documents.update_processing(
                processing_document,
                DocumentProcessingUpdate(
                    extracted_text=extracted_text,
                    summary=summary,
                    processing_status=DocumentProcessingStatus.COMPLETED,
                    processing_error=None,
                    processing_started_at=processing_started_at,
                    processing_completed_at=datetime.now(UTC),
                    processing_attempts=attempt_number,
                ),
            )
            if self.graph_sync_service is not None:
                self.graph_sync_service.sync_document(completed_document)

            return completed_document
        except PermanentDocumentProcessingError as exc:
            return self._mark_failed(
                processing_document,
                attempt_number=attempt_number,
                error=exc.safe_message,
                processing_started_at=processing_started_at,
            )
        except TemporaryDocumentProcessingError as exc:
            self._mark_processing_retryable_error(
                processing_document,
                attempt_number=attempt_number,
                error=exc.safe_message,
                processing_started_at=processing_started_at,
            )
            raise
        except Exception as exc:
            self._mark_processing_retryable_error(
                processing_document,
                attempt_number=attempt_number,
                error=RETRYABLE_PROCESSING_ERROR_MESSAGE,
                processing_started_at=processing_started_at,
            )
            raise TemporaryDocumentProcessingError(RETRYABLE_PROCESSING_ERROR_MESSAGE) from exc

    def _store_chunks(self, document: Document, extracted_text: str) -> list[DocumentChunk]:
        text_chunks = self.chunking_service.chunk_text(extracted_text)
        embeddings = self.embedding_service.embed_texts([chunk.content for chunk in text_chunks])
        stored_chunks = self.document_chunks.replace_for_document(
            document_id=document.id,
            payloads=[
                DocumentChunkCreate(
                    patient_id=document.patient_id,
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    embedding=embedding.embedding,
                    embedding_model=embedding.embedding_model,
                    token_count=chunk.token_count,
                    chunk_metadata=chunk.metadata,
                )
                for chunk, embedding in zip(text_chunks, embeddings, strict=True)
            ],
        )
        if self.graph_sync_service is not None:
            self.graph_sync_service.sync_chunks(stored_chunks)
        return stored_chunks

    def _store_timeline_events(self, document: Document, extracted_text: str) -> None:
        extracted_events = self.timeline_extraction_service.extract_events(
            patient_id=document.patient_id,
            source_document_id=document.id,
            text=extracted_text,
        )
        self.timeline_events.create_many(extracted_events)

    def _build_clinical_graph(self, chunks: list[DocumentChunk]) -> None:
        if (
            self.graph_sync_service is None
            or self.entity_extraction_service is None
            or self.relationship_extraction_service is None
        ):
            return

        for chunk in chunks:
            entities = self.entity_extraction_service.extract_entities(
                source_chunk_id=chunk.id,
                chunk_text=chunk.content,
            )
            self.graph_sync_service.sync_entities_for_chunk(chunk, entities)
            relationships = self.relationship_extraction_service.extract_relationships(
                source_chunk_id=chunk.id,
                chunk_text=chunk.content,
                entities=entities,
            )
            self.graph_sync_service.sync_relationships(entities, relationships)

    def _mark_failed(
        self,
        document: Document,
        attempt_number: int,
        error: str,
        processing_started_at: datetime,
    ) -> Document:
        return self.documents.update_processing(
            document,
            DocumentProcessingUpdate(
                extracted_text=document.extracted_text,
                summary=document.summary,
                processing_status=DocumentProcessingStatus.FAILED,
                processing_error=error,
                processing_started_at=processing_started_at,
                processing_completed_at=datetime.now(UTC),
                processing_attempts=attempt_number,
            ),
        )

    def _mark_processing_retryable_error(
        self,
        document: Document,
        attempt_number: int,
        error: str,
        processing_started_at: datetime,
    ) -> Document:
        return self.documents.update_processing(
            document,
            DocumentProcessingUpdate(
                extracted_text=document.extracted_text,
                summary=document.summary,
                processing_status=DocumentProcessingStatus.PROCESSING,
                processing_error=error,
                processing_started_at=processing_started_at,
                processing_completed_at=None,
                processing_attempts=attempt_number,
            ),
        )
