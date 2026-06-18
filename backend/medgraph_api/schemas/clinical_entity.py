from datetime import date as Date
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ClinicalEntityType(StrEnum):
    SYMPTOM = "symptom"
    MEDICATION = "medication"
    DIAGNOSIS = "diagnosis"
    LAB_TEST = "lab_test"
    PROCEDURE = "procedure"
    FINDING = "finding"


class ExtractedClinicalEntity(BaseModel):
    entity_type: ClinicalEntityType
    name: str
    normalized_name: str
    source_chunk_id: UUID
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_quote: str = Field(min_length=1, max_length=500)
    date: Date | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "normalized_name", "evidence_quote")
    @classmethod
    def normalize_text_field(cls, value: str) -> str:
        normalized_value = " ".join(value.split()).strip()
        if not normalized_value:
            raise ValueError("Text fields cannot be blank.")
        return normalized_value

    @field_validator("normalized_name")
    @classmethod
    def normalize_entity_key(cls, value: str) -> str:
        return value.lower()


class ExtractedClinicalEntities(BaseModel):
    entities: list[ExtractedClinicalEntity] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def deduplicate_entities(self) -> "ExtractedClinicalEntities":
        seen = set()
        deduplicated_entities = []
        for entity in self.entities:
            key = (
                entity.entity_type,
                entity.normalized_name,
                entity.source_chunk_id,
                entity.evidence_quote,
            )
            if key in seen:
                continue
            seen.add(key)
            deduplicated_entities.append(entity)

        self.entities = deduplicated_entities
        return self
