from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PatientRagQueryCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2_000)
    limit: int = Field(default=5, ge=1, le=20)


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


class PatientRagQueryRead(BaseModel):
    patient_id: UUID
    question: str
    answer: str
    sources: list[PatientRagSourceRead]
