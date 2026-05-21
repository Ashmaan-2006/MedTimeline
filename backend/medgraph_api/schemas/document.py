from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentCreate(BaseModel):
    patient_id: UUID
    filename: str
    content_type: str | None
    storage_path: str


class DocumentProcessingUpdate(BaseModel):
    extracted_text: str | None
    summary: str | None


class DocumentUploadRead(BaseModel):
    id: UUID
    patient_id: UUID
    filename: str
    content_type: str | None
    storage_path: str
    extracted_text: str | None
    summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
