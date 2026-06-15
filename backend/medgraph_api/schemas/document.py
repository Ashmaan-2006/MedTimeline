from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentProcessingStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCreate(BaseModel):
    patient_id: UUID
    filename: str
    content_type: str | None
    storage_path: str
    processing_status: DocumentProcessingStatus = DocumentProcessingStatus.UPLOADED
    processing_attempts: int = 0


class DocumentProcessingUpdate(BaseModel):
    extracted_text: str | None
    summary: str | None
    processing_status: DocumentProcessingStatus
    processing_error: str | None = None
    processing_started_at: datetime | None = None
    processing_completed_at: datetime | None = None
    celery_task_id: str | None = None
    processing_attempts: int | None = None


class DocumentUploadRead(BaseModel):
    id: UUID
    patient_id: UUID
    filename: str
    content_type: str | None
    storage_path: str
    extracted_text: str | None
    summary: str | None
    processing_status: DocumentProcessingStatus
    processing_error: str | None
    processing_started_at: datetime | None
    processing_completed_at: datetime | None
    celery_task_id: str | None
    processing_attempts: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentProcessingStatusRead(BaseModel):
    document_id: UUID
    status: DocumentProcessingStatus
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
