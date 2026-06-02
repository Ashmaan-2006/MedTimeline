from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from medgraph_api.services.similarity_search import (
    PatientDocumentSearchResult,
    PatientDocumentSimilaritySearchService,
)


@dataclass(frozen=True)
class PatientRagCitationSource:
    citation_label: str
    chunk_id: UUID
    document_id: UUID
    patient_id: UUID
    chunk_index: int
    content: str
    embedding_model: str | None
    token_count: int | None
    chunk_metadata: dict | None
    created_at: datetime


@dataclass(frozen=True)
class PatientRagQueryResult:
    patient_id: UUID
    question: str
    answer: str
    sources: list[PatientRagCitationSource]


class PatientRagQueryService:
    def __init__(self, similarity_search: PatientDocumentSimilaritySearchService) -> None:
        self.similarity_search = similarity_search

    def answer_question(
        self,
        patient_id: UUID,
        question: str,
        limit: int = 5,
    ) -> PatientRagQueryResult:
        normalized_question = " ".join(question.split())
        if not normalized_question:
            return PatientRagQueryResult(
                patient_id=patient_id,
                question=question,
                answer="No question was provided.",
                sources=[],
            )

        retrieved_sources = self.similarity_search.search(
            patient_id=patient_id,
            query=normalized_question,
            limit=limit,
        )
        if not retrieved_sources:
            return PatientRagQueryResult(
                patient_id=patient_id,
                question=normalized_question,
                answer="No relevant patient document evidence was found for this question.",
                sources=[],
            )

        sources = self._build_cited_sources(retrieved_sources)
        evidence_summary = " ".join(self._cited_evidence_sentences(sources[:3]))
        return PatientRagQueryResult(
            patient_id=patient_id,
            question=normalized_question,
            answer=f"Based on the retrieved patient documents: {evidence_summary}",
            sources=sources,
        )

    def _build_cited_sources(
        self,
        sources: list[PatientDocumentSearchResult],
    ) -> list[PatientRagCitationSource]:
        return [
            PatientRagCitationSource(
                citation_label=f"[{index}]",
                chunk_id=source.chunk_id,
                document_id=source.document_id,
                patient_id=source.patient_id,
                chunk_index=source.chunk_index,
                content=source.content,
                embedding_model=source.embedding_model,
                token_count=source.token_count,
                chunk_metadata=source.chunk_metadata,
                created_at=source.created_at,
            )
            for index, source in enumerate(sources, start=1)
        ]

    def _cited_evidence_sentences(
        self,
        sources: list[PatientRagCitationSource],
    ) -> list[str]:
        sentences = []
        for source in sources:
            sentence = self._first_sentence(source.content).rstrip(".?!")
            if sentence:
                sentences.append(f"{sentence} {source.citation_label}.")
        return sentences

    @staticmethod
    def _first_sentence(text: str) -> str:
        normalized_text = " ".join(text.split())
        for separator in (". ", "? ", "! "):
            if separator in normalized_text:
                return normalized_text.split(separator, maxsplit=1)[0].strip() + separator.strip()
        return normalized_text
