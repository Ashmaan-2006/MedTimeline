from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TimelineEventCreate(BaseModel):
    patient_id: UUID
    source_document_id: UUID | None
    occurred_at: datetime | None
    event_type: str
    title: str
    description: str | None
    evidence_text: str | None
    confidence: float | None
    event_metadata: dict | None


class TimelineEventRead(TimelineEventCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

