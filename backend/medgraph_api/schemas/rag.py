from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PatientRagQueryCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2_000)
    limit: int = Field(default=5, ge=1, le=20)
    document_id: UUID | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "PatientRagQueryCreate":
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from > self.created_to
        ):
            raise ValueError("created_from must be before or equal to created_to.")
        return self


class PatientRagSourceRead(BaseModel):
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


class PatientRagGraphEvidenceRead(BaseModel):
    citation_label: str
    source_label: str
    source_name: str
    relationship_type: str
    target_label: str
    target_name: str
    evidence: str | None
    confidence: float | None
    source_chunk_id: str | None


class PatientRagQueryRead(BaseModel):
    patient_id: UUID
    question: str
    answer: str
    sources: list[PatientRagSourceRead]
    graph_evidence: list[PatientRagGraphEvidenceRead]
