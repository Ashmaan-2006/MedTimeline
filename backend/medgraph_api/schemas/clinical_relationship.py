from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ClinicalRelationshipType(StrEnum):
    MENTIONED_IN = "MENTIONED_IN"
    EVIDENCED_BY = "EVIDENCED_BY"
    OCCURRED_BEFORE = "OCCURRED_BEFORE"
    OCCURRED_AFTER = "OCCURRED_AFTER"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    SUPPORTS = "SUPPORTS"
    CONTRAINDICATES = "CONTRAINDICATES"
    WORSENED_AFTER = "WORSENED_AFTER"
    IMPROVED_AFTER = "IMPROVED_AFTER"
    STARTED_AT = "STARTED_AT"
    STOPPED_AT = "STOPPED_AT"
    ORDERED_BECAUSE_OF = "ORDERED_BECAUSE_OF"


class ExtractedClinicalRelationship(BaseModel):
    source: str
    target: str
    type: ClinicalRelationshipType
    source_chunk_id: UUID
    evidence: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("source", "target", "evidence")
    @classmethod
    def normalize_text_field(cls, value: str) -> str:
        normalized_value = " ".join(value.split()).strip()
        if not normalized_value:
            raise ValueError("Relationship text fields cannot be blank.")
        return normalized_value

    @field_validator("source", "target")
    @classmethod
    def normalize_endpoint(cls, value: str) -> str:
        return value.lower()


class ExtractedClinicalRelationships(BaseModel):
    relationships: list[ExtractedClinicalRelationship] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def deduplicate_relationships(self) -> "ExtractedClinicalRelationships":
        seen = set()
        deduplicated_relationships = []
        for relationship in self.relationships:
            key = (
                relationship.source,
                relationship.target,
                relationship.type,
                relationship.source_chunk_id,
                relationship.evidence,
            )
            if key in seen:
                continue
            seen.add(key)
            deduplicated_relationships.append(relationship)

        self.relationships = deduplicated_relationships
        return self
