import json
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator

ENTITY_KEYS = (
    "symptoms",
    "medications",
    "diagnoses",
    "lab_tests",
    "procedures",
    "findings",
)


class EntityExtractionError(ValueError):
    pass


class ClinicalEntityLLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        pass


class ClinicalEntityExtraction(BaseModel):
    symptoms: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    diagnoses: list[str] = Field(default_factory=list)
    lab_tests: list[str] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)

    @field_validator(*ENTITY_KEYS, mode="before")
    @classmethod
    def validate_entity_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Entity values must be lists.")

        normalized_entities = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("Entity list items must be strings.")
            normalized_item = " ".join(item.split()).strip()
            if normalized_item:
                normalized_entities.append(normalized_item)

        return sorted(set(normalized_entities), key=normalized_entities.index)


class ClinicalEntityExtractionService:
    def __init__(self, llm_client: ClinicalEntityLLMClient) -> None:
        self.llm_client = llm_client

    def extract_entities(self, chunk_text: str) -> ClinicalEntityExtraction:
        normalized_chunk = " ".join(chunk_text.split())
        if not normalized_chunk:
            return ClinicalEntityExtraction()

        response_text = self.llm_client.generate(self._build_prompt(normalized_chunk))
        return self._parse_response(response_text)

    def _build_prompt(self, chunk_text: str) -> str:
        return f"""
You are extracting structured clinical entities from a patient record chunk.

Return only valid JSON. Do not include markdown, comments, explanations, or prose.
The JSON object must contain exactly these keys:
- symptoms
- medications
- diagnoses
- lab_tests
- procedures
- findings

Each value must be an array of strings. Use empty arrays when no entities are present.
Extract only entities explicitly stated in the chunk. Do not infer unstated diagnoses.

Chunk:
{chunk_text}

Strict JSON response:
""".strip()

    def _parse_response(self, response_text: str) -> ClinicalEntityExtraction:
        try:
            parsed_response = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise EntityExtractionError("LLM returned invalid JSON.") from exc

        if not isinstance(parsed_response, dict):
            raise EntityExtractionError("LLM response must be a JSON object.")

        missing_keys = set(ENTITY_KEYS) - parsed_response.keys()
        extra_keys = parsed_response.keys() - set(ENTITY_KEYS)
        if missing_keys or extra_keys:
            raise EntityExtractionError("LLM response did not match the clinical entity schema.")

        try:
            return ClinicalEntityExtraction.model_validate(parsed_response)
        except ValidationError as exc:
            raise EntityExtractionError("LLM response contained invalid entity values.") from exc
