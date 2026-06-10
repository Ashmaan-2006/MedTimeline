from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from medgraph_api.models.document import Document
from medgraph_api.schemas.document import DocumentCreate, DocumentProcessingUpdate


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: DocumentCreate) -> Document:
        document = Document(**payload.model_dump())
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_for_patient(
        self,
        patient_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(Document.patient_id == patient_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def update_processing(
        self,
        document: Document,
        payload: DocumentProcessingUpdate,
    ) -> Document:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(document, field, value)

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document
