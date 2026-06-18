from typing import Any

from pydantic import BaseModel, ConfigDict


class PatientGraphSummaryRead(BaseModel):
    patient_id: str
    document_count: int
    chunk_count: int
    entity_count: int
    relationship_count: int

    model_config = ConfigDict(from_attributes=True)


class GraphEntityRead(BaseModel):
    label: str
    normalized_name: str
    name: str | None
    mention_count: int
    evidence_count: int
    latest_seen_at: str | None

    model_config = ConfigDict(from_attributes=True)


class GraphRelationshipRead(BaseModel):
    source_label: str
    source_name: str
    relationship_type: str
    target_label: str
    target_name: str
    evidence: str | None
    confidence: float | None
    source_chunk_id: str | None

    model_config = ConfigDict(from_attributes=True)


class EvidenceChunkRead(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int | None
    content: str
    evidence: str | None
    confidence: float | None
    filename: str | None
    created_at: str | None

    model_config = ConfigDict(from_attributes=True)


class EntityPathStepRead(BaseModel):
    source: dict[str, Any]
    relationship_type: str
    relationship: dict[str, Any]
    target: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
