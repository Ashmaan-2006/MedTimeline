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

    def update_processing(
        self,
        document: Document,
        payload: DocumentProcessingUpdate,
    ) -> Document:
        for field, value in payload.model_dump().items():
            setattr(document, field, value)

        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document
