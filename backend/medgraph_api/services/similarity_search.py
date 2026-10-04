from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from medgraph_api.crud.document_chunks import DocumentChunkRepository
from medgraph_api.core.observability import observe_span
from medgraph_api.models.document_chunk import DocumentChunk
from medgraph_api.services.clinical_text import iter_passages, rank_passages
from medgraph_api.services.embeddings import HashingEmbeddingService
from medgraph_api.services.retrieval_filters import RetrievalFilters

CANDIDATE_POOL_MULTIPLIER = 4
MIN_CANDIDATE_POOL = 20


def rerank_chunks(chunks: list[DocumentChunk], query: str) -> list[DocumentChunk]:
    """Order chunks by their best question-matching passage, with vector rank as a tiebreak."""
    passages = [
        passage
        for index, chunk in enumerate(chunks)
        for passage in iter_passages(
            chunk.content,
            initial_section=(chunk.chunk_metadata or {}).get("section"),
            source_index=index,
        )
    ]
    best_scores = [0.0] * len(chunks)
    for passage in rank_passages(passages, query):
        best_scores[passage.source_index] = max(best_scores[passage.source_index], passage.score)

    def combined_score(index: int) -> float:
        vector_score = (len(chunks) - index) / len(chunks)
        return best_scores[index] + vector_score

    order = sorted(range(len(chunks)), key=combined_score, reverse=True)
    return [chunks[index] for index in order]


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
        with observe_span(
            "rag.vector_retrieval",
            attributes={
                "patient.id": str(patient_id),
                "retrieval.limit": limit,
                "retrieval.has_filters": filters is not None,
            },
        ):
            if limit <= 0:
                raise ValueError("limit must be greater than 0.")

            query_embedding = self.embedding_service.embed_text(query)
            if not query_embedding.text:
                return []

            # Pull a wider vector candidate pool, then rerank it lexically: the local hashing
            # embedding misses chunks whose wording matches the question exactly.
            candidates = self.document_chunks.search_similar_for_patient(
                patient_id=patient_id,
                query_embedding=query_embedding.embedding,
                limit=max(limit * CANDIDATE_POOL_MULTIPLIER, MIN_CANDIDATE_POOL),
                filters=filters,
            )
            chunks = rerank_chunks(candidates, query)[:limit]
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
