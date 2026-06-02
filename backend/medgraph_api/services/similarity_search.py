from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from medgraph_api.crud.document_chunks import DocumentChunkRepository
from medgraph_api.services.embeddings import HashingEmbeddingService
from medgraph_api.services.retrieval_filters import RetrievalFilters


@dataclass(frozen=True)
class PatientDocumentSearchResult:
    chunk_id: UUID
    document_id: UUID
    patient_id: UUID
    chunk_index: int
    content: str
    embedding_model: str | None
    token_count: int | None
    chunk_metadata: dict | None
    created_at: datetime


class PatientDocumentSimilaritySearchService:
    def __init__(
        self,
        document_chunks: DocumentChunkRepository,
        embedding_service: HashingEmbeddingService,
    ) -> None:
        self.document_chunks = document_chunks
        self.embedding_service = embedding_service

    def search(
        self,
        patient_id: UUID,
        query: str,
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> list[PatientDocumentSearchResult]:
        if limit <= 0:
            raise ValueError("limit must be greater than 0.")

        query_embedding = self.embedding_service.embed_text(query)
        if not query_embedding.text:
            return []

        chunks = self.document_chunks.search_similar_for_patient(
            patient_id=patient_id,
            query_embedding=query_embedding.embedding,
            limit=limit,
            filters=filters,
        )
        return [
            PatientDocumentSearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                patient_id=chunk.patient_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding_model=chunk.embedding_model,
                token_count=chunk.token_count,
                chunk_metadata=chunk.chunk_metadata,
                created_at=chunk.created_at,
            )
            for chunk in chunks
        ]
