import json
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from medgraph_api.core.observability import observe_span
from medgraph_api.schemas.clinical_entity import ExtractedClinicalEntities
from medgraph_api.schemas.clinical_relationship import ExtractedClinicalRelationships


class RelationshipExtractionError(ValueError):
    pass


class ClinicalRelationshipLLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        pass


class ClinicalRelationshipExtractionService:
    def __init__(self, llm_client: ClinicalRelationshipLLMClient) -> None:
        self.llm_client = llm_client

    def extract_relationships(
        self,
        source_chunk_id: UUID,
        chunk_text: str,
        entities: ExtractedClinicalEntities,
    ) -> ExtractedClinicalRelationships:
        with observe_span(
            "llm.extract_clinical_relationships",
            attributes={
                "source.chunk_id": str(source_chunk_id),
                "llm.operation": "relationship_extraction",
                "entity.count": len(entities.entities),
            },
        ):
            normalized_chunk = " ".join(chunk_text.split())
            if not normalized_chunk or not entities.entities:
                return ExtractedClinicalRelationships()

            response_text = self.llm_client.generate(
                self._build_prompt(
                    source_chunk_id=source_chunk_id,
                    chunk_text=normalized_chunk,
                    entities=entities,
                )
            )
            return self._parse_response(
                response_text=response_text,
                source_chunk_id=source_chunk_id,
                entities=entities,
            )

    def _build_prompt(
        self,
        source_chunk_id: UUID,
        chunk_text: str,
        entities: ExtractedClinicalEntities,
    ) -> str:
        entity_lines = "\n".join(
            f"- {entity.normalized_name} ({entity.entity_type})" for entity in entities.entities
        )
        return f"""
You are extracting clinical relationships from a patient record chunk.

Return only valid JSON. Do not include markdown, comments, explanations, or prose.
The JSON object must contain exactly one top-level key: relationships.

Each relationship must contain exactly these keys:
- source: normalized_name of one extracted entity
- target: normalized_name of another extracted entity
- type: one of MENTIONED_IN, EVIDENCED_BY, OCCURRED_BEFORE, OCCURRED_AFTER, ASSOCIATED_WITH, SUPPORTS, CONTRAINDICATES, WORSENED_AFTER, IMPROVED_AFTER, STARTED_AT, STOPPED_AT, ORDERED_BECAUSE_OF
- source_chunk_id: "{source_chunk_id}"
- evidence: short exact quote from the chunk, maximum 500 characters
- confidence: number between 0 and 1

Only use source and target values from this extracted entity list:
{entity_lines}

Use an empty relationships array when no meaningful relationships are present.
Extract only relationships explicitly supported by the chunk. Do not infer causality.

Chunk:
{chunk_text}

Strict JSON response:
""".strip()

    def _parse_response(
        self,
        response_text: str,
        source_chunk_id: UUID,
        entities: ExtractedClinicalEntities,
    ) -> ExtractedClinicalRelationships:
        try:
            parsed_response = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RelationshipExtractionError("LLM returned invalid JSON.") from exc

        if not isinstance(parsed_response, dict):
            raise RelationshipExtractionError("LLM response must be a JSON object.")

        if set(parsed_response.keys()) != {"relationships"}:
            raise RelationshipExtractionError(
                "LLM response did not match the clinical relationship schema."
            )

        try:
            extracted_relationships = ExtractedClinicalRelationships.model_validate(parsed_response)
        except ValidationError as exc:
            raise RelationshipExtractionError(
                "LLM response contained invalid relationship values."
            ) from exc

        entity_names = {entity.normalized_name for entity in entities.entities}
        for relationship in extracted_relationships.relationships:
            if relationship.source_chunk_id != source_chunk_id:
                raise RelationshipExtractionError("LLM response referenced the wrong source chunk.")
            if relationship.source not in entity_names or relationship.target not in entity_names:
                raise RelationshipExtractionError(
                    "LLM response referenced an unknown relationship endpoint."
                )

        return extracted_relationships
