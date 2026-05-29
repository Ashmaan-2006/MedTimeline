from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from medgraph_api.models.document_chunk import DocumentChunk
from medgraph_api.schemas.document_chunk import DocumentChunkCreate


class DocumentChunkRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_for_document(
        self,
        document_id: UUID,
        payloads: list[DocumentChunkCreate],
    ) -> list[DocumentChunk]:
        self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

        chunks = [DocumentChunk(**payload.model_dump()) for payload in payloads]
        self.db.add_all(chunks)
        self.db.commit()

        for chunk in chunks:
            self.db.refresh(chunk)

        return chunks

    def list_for_document(
        self,
        document_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def search_similar_for_patient(
        self,
        patient_id: UUID,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.patient_id == patient_id)
            .where(DocumentChunk.embedding.is_not(None))
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())
