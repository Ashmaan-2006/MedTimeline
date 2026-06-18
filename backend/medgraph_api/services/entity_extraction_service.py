import json
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from medgraph_api.schemas.clinical_entity import ExtractedClinicalEntities


class EntityExtractionError(ValueError):
    pass


class ClinicalEntityLLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        pass


class ClinicalEntityExtractionService:
    def __init__(self, llm_client: ClinicalEntityLLMClient) -> None:
        self.llm_client = llm_client

    def extract_entities(self, source_chunk_id: UUID, chunk_text: str) -> ExtractedClinicalEntities:
        normalized_chunk = " ".join(chunk_text.split())
        if not normalized_chunk:
            return ExtractedClinicalEntities()

        response_text = self.llm_client.generate(
            self._build_prompt(source_chunk_id=source_chunk_id, chunk_text=normalized_chunk)
        )
        return self._parse_response(response_text, source_chunk_id=source_chunk_id)

    def _build_prompt(self, source_chunk_id: UUID, chunk_text: str) -> str:
        return f"""
You are extracting structured clinical entities from a patient record chunk.

Return only valid JSON. Do not include markdown, comments, explanations, or prose.
The JSON object must contain exactly one top-level key: entities.

Each entity must contain exactly these keys:
- entity_type: one of symptom, medication, diagnosis, lab_test, procedure, finding
- name: entity text as written in the source
- normalized_name: lowercase normalized entity name
- source_chunk_id: "{source_chunk_id}"
- confidence: number between 0 and 1
- evidence_quote: short exact quote from the chunk, maximum 500 characters
- date: ISO date if explicitly available, otherwise null

Use an empty entities array when no entities are present.
Extract only entities explicitly stated in the chunk. Do not infer unstated diagnoses.

Chunk:
{chunk_text}

Strict JSON response:
""".strip()

    def _parse_response(
        self,
        response_text: str,
        source_chunk_id: UUID,
    ) -> ExtractedClinicalEntities:
        try:
            parsed_response = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise EntityExtractionError("LLM returned invalid JSON.") from exc

        if not isinstance(parsed_response, dict):
            raise EntityExtractionError("LLM response must be a JSON object.")

        if set(parsed_response.keys()) != {"entities"}:
            raise EntityExtractionError("LLM response did not match the clinical entity schema.")

        try:
            extracted_entities = ExtractedClinicalEntities.model_validate(parsed_response)
        except ValidationError as exc:
            raise EntityExtractionError("LLM response contained invalid entity values.") from exc

        if any(entity.source_chunk_id != source_chunk_id for entity in extracted_entities.entities):
            raise EntityExtractionError("LLM response referenced the wrong source chunk.")

        return extracted_entities
