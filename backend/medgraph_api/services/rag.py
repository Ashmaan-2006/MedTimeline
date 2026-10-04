from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from medgraph_api.services.similarity_search import (
    PatientDocumentSearchResult,
    PatientDocumentSimilaritySearchService,
)
from medgraph_api.core.observability import observe_span
from medgraph_api.services.clinical_text import (
    iter_passages,
    select_relevant_passages,
    stem_terms,
)
from medgraph_api.services.graph_query_service import ClinicalGraphQueryService, GraphRelationship
from medgraph_api.services.retrieval_filters import RetrievalFilters
from medgraph_api.services.text_snippets import build_source_snippet

MAX_ANSWER_PASSAGES = 5
MAX_PASSAGE_CHARS = 220


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
        with observe_span(
            "rag.answer_question",
            attributes={"patient.id": str(patient_id), "retrieval.limit": limit},
        ):
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
            document_lines, matched_question = self._cited_evidence_lines(
                sources, normalized_question
            )
            graph_lines = self._graph_evidence_sentences(graph_evidence[:3])
            if document_lines and not matched_question:
                # Say so rather than presenting unrelated sentences as the answer.
                answer_prefix = (
                    "No retrieved passage directly addresses this question. "
                    "Closest document evidence:"
                )
            elif graph_evidence:
                answer_prefix = "Based on the retrieved patient documents and clinical graph:"
            else:
                answer_prefix = "Based on the retrieved patient documents:"
            # One cited fact per bullet so the UI can render a readable list.
            answer_lines = [answer_prefix, *document_lines]
            if graph_lines:
                answer_lines.extend(["Clinical graph links:", *graph_lines])
            return PatientRagQueryResult(
                patient_id=patient_id,
                question=normalized_question,
                answer="\n".join(answer_lines),
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

    def _cited_evidence_lines(
        self,
        sources: list[PatientRagCitationSource],
        question: str,
    ) -> tuple[list[str], bool]:
        # Rank sentences from every retrieved chunk together so the answer quotes the
        # passages that address the question rather than whatever each chunk starts with.
        passages = [
            passage
            for index, source in enumerate(sources)
            for passage in iter_passages(
                source.content,
                initial_section=_chunk_section(source.chunk_metadata),
                source_index=index,
            )
        ]
        selected = select_relevant_passages(passages, question, MAX_ANSWER_PASSAGES)
        lines = []
        for passage in selected:
            text = build_source_snippet(passage.display_text(), max_length=MAX_PASSAGE_CHARS)
            if not text.endswith("..."):
                text = text.rstrip(".?!")
            lines.append(f"- {text} {sources[passage.source_index].citation_label}.")
        # Fallback passages carry no score: nothing matched the question's terms.
        return lines, any(passage.score > 0 for passage in selected)

    def _retrieve_graph_evidence(
        self,
        patient_id: UUID,
        question: str,
        limit: int,
    ) -> list[PatientRagGraphEvidence]:
        with observe_span(
            "rag.graph_retrieval",
            attributes={"patient.id": str(patient_id), "retrieval.limit": limit},
        ):
            if self.graph_query is None:
                return []

            relationships = self.graph_query.get_relationships_for_patient(str(patient_id))
            # Only relationships that mention the question's terms; unrelated graph edges
            # ("diabetes associated with hypertension") just add noise to the answer.
            relevant_relationships = [
                relationship
                for relationship in relationships
                if self._relationship_matches_question(relationship, question)
            ]

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
        question_terms = stem_terms(question)
        named_terms = stem_terms(
            " ".join(
                [
                    relationship.source_name,
                    relationship.target_name,
                    relationship.relationship_type.replace("_", " "),
                ]
            )
        )
        if question_terms & named_terms:
            return True
        # Evidence text is broad, so require a stronger overlap before trusting it alone.
        evidence_terms = stem_terms(relationship.evidence or "")
        return len(question_terms & evidence_terms) >= 2

    def _graph_evidence_sentences(
        self,
        graph_evidence: list[PatientRagGraphEvidence],
    ) -> list[str]:
        # The evidence quote is shown in the citation card, so the answer stays one line each.
        return [
            f"- {evidence.source_name} {evidence.relationship_type.lower().replace('_', ' ')} "
            f"{evidence.target_name} {evidence.citation_label}."
            for evidence in graph_evidence
        ]


def _chunk_section(chunk_metadata: dict | None) -> str | None:
    section = (chunk_metadata or {}).get("section")
    return section if isinstance(section, str) else None
