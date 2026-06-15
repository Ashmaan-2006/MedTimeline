from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from medgraph_api.crud.document_chunks import DocumentChunkRepository
from medgraph_api.crud.documents import DocumentRepository
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.crud.timeline_events import TimelineEventRepository
from medgraph_api.db.session import get_db
from medgraph_api.services.chunking import TextChunkingService
from medgraph_api.services.document_processing import DocumentProcessingService
from medgraph_api.services.embeddings import HashingEmbeddingService
from medgraph_api.services.extraction import DocumentExtractionService
from medgraph_api.services.rag import PatientRagQueryService
from medgraph_api.services.similarity_search import PatientDocumentSimilaritySearchService
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


def get_patient_document_similarity_search_service(
    document_chunks: DocumentChunkRepository = Depends(get_document_chunk_repository),
    embedding_service: HashingEmbeddingService = Depends(get_embedding_service),
) -> PatientDocumentSimilaritySearchService:
    return PatientDocumentSimilaritySearchService(
        document_chunks=document_chunks,
        embedding_service=embedding_service,
    )


def get_patient_rag_query_service(
    similarity_search: PatientDocumentSimilaritySearchService = Depends(
        get_patient_document_similarity_search_service
    ),
) -> PatientRagQueryService:
    return PatientRagQueryService(similarity_search=similarity_search)


def get_summary_service() -> BasicAISummaryService:
    return BasicAISummaryService()


def get_timeline_event_extraction_service() -> BasicTimelineEventExtractionService:
    return BasicTimelineEventExtractionService()


def get_document_processing_service(
    documents: DocumentRepository = Depends(get_document_repository),
    document_chunks: DocumentChunkRepository = Depends(get_document_chunk_repository),
    timeline_events: TimelineEventRepository = Depends(get_timeline_event_repository),
    extraction_service: DocumentExtractionService = Depends(get_document_extraction_service),
    chunking_service: TextChunkingService = Depends(get_text_chunking_service),
    embedding_service: HashingEmbeddingService = Depends(get_embedding_service),
    summary_service: BasicAISummaryService = Depends(get_summary_service),
    timeline_extraction_service: BasicTimelineEventExtractionService = Depends(
        get_timeline_event_extraction_service
    ),
) -> DocumentProcessingService:
    return DocumentProcessingService(
        documents=documents,
        document_chunks=document_chunks,
        timeline_events=timeline_events,
        extraction_service=extraction_service,
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        summary_service=summary_service,
        timeline_extraction_service=timeline_extraction_service,
    )
