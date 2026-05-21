from uuid import UUID

from pydantic import BaseModel


class DocumentUploadRead(BaseModel):
    patient_id: UUID
    filename: str
    content_type: str | None
    size_bytes: int
    storage_path: str

