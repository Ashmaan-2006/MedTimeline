from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from medgraph_api.services.similarity_search import (
    PatientDocumentSearchResult,
    PatientDocumentSimilaritySearchService,
)
from medgraph_api.services.graph_query_service import ClinicalGraphQueryService, GraphRelationship
from medgraph_api.services.retrieval_filters import RetrievalFilters


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
class PatientRagGraphEvidence:
    citation_label: str
    source_label: str
    source_name: str
    relationship_type: str
    target_label: str
    target_name: str
    evidence: str | None
    confidence: float | None
    source_chunk_id: str | None


@dataclass(frozen=True)
class PatientRagQueryResult:
    patient_id: UUID
    question: str
    answer: str
    sources: list[PatientRagCitationSource]
    graph_evidence: list[PatientRagGraphEvidence]


class PatientRagQueryService:
    def __init__(
        self,
        similarity_search: PatientDocumentSimilaritySearchService,
        graph_query: ClinicalGraphQueryService | None = None,
    ) -> None:
        self.similarity_search = similarity_search
        self.graph_query = graph_query

    def answer_question(
        self,
        patient_id: UUID,
        question: str,
        limit: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> PatientRagQueryResult:
        normalized_question = " ".join(question.split())
        if not normalized_question:
            return PatientRagQueryResult(
                patient_id=patient_id,
                question=question,
                answer="No question was provided.",
                sources=[],
                graph_evidence=[],
            )

        retrieved_sources = self.similarity_search.search(
            patient_id=patient_id,
            query=normalized_question,
            limit=limit,
            filters=filters,
        )
        graph_evidence = self._retrieve_graph_evidence(
            patient_id=patient_id,
            question=normalized_question,
            limit=limit,
        )
        if not retrieved_sources and not graph_evidence:
            return PatientRagQueryResult(
                patient_id=patient_id,
                question=normalized_question,
                answer="No relevant patient document evidence was found for this question.",
                sources=[],
                graph_evidence=[],
            )

        sources = self._build_cited_sources(retrieved_sources)
        evidence_summary = " ".join(self._cited_evidence_sentences(sources[:3]))
        graph_summary = " ".join(self._graph_evidence_sentences(graph_evidence[:3]))
        context_parts = [part for part in (evidence_summary, graph_summary) if part]
        answer_prefix = (
            "Based on the retrieved patient documents and clinical graph:"
            if graph_evidence
            else "Based on the retrieved patient documents:"
        )
        return PatientRagQueryResult(
            patient_id=patient_id,
            question=normalized_question,
            answer=f"{answer_prefix} {' '.join(context_parts)}",
            sources=sources,
            graph_evidence=graph_evidence,
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

    def _retrieve_graph_evidence(
        self,
        patient_id: UUID,
        question: str,
        limit: int,
    ) -> list[PatientRagGraphEvidence]:
        if self.graph_query is None:
            return []

        relationships = self.graph_query.get_relationships_for_patient(str(patient_id))
        relevant_relationships = [
            relationship
            for relationship in relationships
            if self._relationship_matches_question(relationship, question)
        ]
        if not relevant_relationships:
            relevant_relationships = relationships[:limit]

        return [
            PatientRagGraphEvidence(
                citation_label=f"[G{index}]",
                source_label=relationship.source_label,
                source_name=relationship.source_name,
                relationship_type=relationship.relationship_type,
                target_label=relationship.target_label,
                target_name=relationship.target_name,
                evidence=relationship.evidence,
                confidence=relationship.confidence,
                source_chunk_id=relationship.source_chunk_id,
            )
            for index, relationship in enumerate(relevant_relationships[:limit], start=1)
        ]

    def _relationship_matches_question(
        self,
        relationship: GraphRelationship,
        question: str,
    ) -> bool:
        question_terms = set(self._tokenize(question))
        relationship_terms = set(
            self._tokenize(
                " ".join(
                    [
                        relationship.source_name,
                        relationship.target_name,
                        relationship.relationship_type.replace("_", " "),
                        relationship.evidence or "",
                    ]
                )
            )
        )
        return bool(question_terms & relationship_terms)

    def _graph_evidence_sentences(
        self,
        graph_evidence: list[PatientRagGraphEvidence],
    ) -> list[str]:
        sentences = []
        for evidence in graph_evidence:
            relationship_text = evidence.relationship_type.lower().replace("_", " ")
            evidence_text = f"{evidence.source_name} {relationship_text} {evidence.target_name}"
            if evidence.evidence:
                evidence_text = f"{evidence_text}; evidence: {evidence.evidence}"
            sentences.append(f"{evidence_text} {evidence.citation_label}.")
        return sentences

    @staticmethod
    def _first_sentence(text: str) -> str:
        normalized_text = " ".join(text.split())
        for separator in (". ", "? ", "! "):
            if separator in normalized_text:
                return normalized_text.split(separator, maxsplit=1)[0].strip() + separator.strip()
        return normalized_text

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        stop_words = {
            "a",
            "after",
            "and",
            "did",
            "for",
            "the",
            "to",
            "was",
            "were",
            "what",
            "when",
            "why",
        }
        return [
            token
            for token in "".join(
                character.lower() if character.isalnum() else " " for character in text
            ).split()
            if len(token) > 2 and token not in stop_words
        ]
