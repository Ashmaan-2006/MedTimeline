from uuid import UUID

from pydantic import BaseModel


class DocumentChunkCreate(BaseModel):
    patient_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    embedding: list[float]
    embedding_model: str
    token_count: int
    chunk_metadata: dict[str, int]
