from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from medgraph_api.crud.document_chunks import DocumentChunkRepository
from medgraph_api.crud.documents import DocumentRepository
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.crud.timeline_events import TimelineEventRepository
from medgraph_api.db.session import get_db
from medgraph_api.services.chunking import TextChunkingService
from medgraph_api.services.embeddings import HashingEmbeddingService
from medgraph_api.services.extraction import DocumentExtractionService
from medgraph_api.services.storage import LocalUploadStorage
from medgraph_api.services.summarization import BasicAISummaryService
from medgraph_api.services.timeline_extraction import BasicTimelineEventExtractionService


def get_patient_repository(db: Session = Depends(get_db)) -> Generator[PatientRepository, None, None]:
    yield PatientRepository(db)


def get_document_repository(db: Session = Depends(get_db)) -> Generator[DocumentRepository, None, None]:
    yield DocumentRepository(db)


def get_document_chunk_repository(
    db: Session = Depends(get_db),
) -> Generator[DocumentChunkRepository, None, None]:
    yield DocumentChunkRepository(db)


def get_timeline_event_repository(
    db: Session = Depends(get_db),
) -> Generator[TimelineEventRepository, None, None]:
    yield TimelineEventRepository(db)


def get_upload_storage() -> LocalUploadStorage:
    return LocalUploadStorage()


def get_document_extraction_service() -> DocumentExtractionService:
    return DocumentExtractionService()


def get_text_chunking_service() -> TextChunkingService:
    return TextChunkingService()


def get_embedding_service() -> HashingEmbeddingService:
    return HashingEmbeddingService()


def get_summary_service() -> BasicAISummaryService:
    return BasicAISummaryService()


def get_timeline_event_extraction_service() -> BasicTimelineEventExtractionService:
    return BasicTimelineEventExtractionService()
