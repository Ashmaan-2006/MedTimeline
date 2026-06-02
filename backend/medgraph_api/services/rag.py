from dataclasses import dataclass
from uuid import UUID

from medgraph_api.services.similarity_search import (
    PatientDocumentSearchResult,
    PatientDocumentSimilaritySearchService,
)


@dataclass(frozen=True)
class PatientRagQueryResult:
    patient_id: UUID
    question: str
    answer: str
    sources: list[PatientDocumentSearchResult]


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

        sources = self.similarity_search.search(
            patient_id=patient_id,
            query=normalized_question,
            limit=limit,
        )
        if not sources:
            return PatientRagQueryResult(
                patient_id=patient_id,
                question=normalized_question,
                answer="No relevant patient document evidence was found for this question.",
                sources=[],
            )

        evidence_summary = " ".join(
            self._first_sentence(source.content) for source in sources[:3] if source.content.strip()
        )
        return PatientRagQueryResult(
            patient_id=patient_id,
            question=normalized_question,
            answer=f"Based on the retrieved patient documents: {evidence_summary}",
            sources=sources,
        )

    @staticmethod
    def _first_sentence(text: str) -> str:
        normalized_text = " ".join(text.split())
        for separator in (". ", "? ", "! "):
            if separator in normalized_text:
                return normalized_text.split(separator, maxsplit=1)[0].strip() + separator.strip()
        return normalized_text
