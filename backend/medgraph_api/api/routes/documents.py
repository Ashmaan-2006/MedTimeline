from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from medgraph_api.api.deps import (
    get_document_extraction_service,
    get_document_repository,
    get_patient_repository,
    get_summary_service,
    get_timeline_event_extraction_service,
    get_timeline_event_repository,
    get_upload_storage,
)
from medgraph_api.crud.documents import DocumentRepository
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.crud.timeline_events import TimelineEventRepository
from medgraph_api.schemas.document import (
    DocumentCreate,
    DocumentProcessingUpdate,
    DocumentUploadRead,
)
from medgraph_api.services.extraction import DocumentExtractionService, UnsupportedDocumentTypeError
from medgraph_api.services.storage import LocalUploadStorage
from medgraph_api.services.summarization import BasicAISummaryService
from medgraph_api.services.timeline_extraction import BasicTimelineEventExtractionService

router = APIRouter(prefix="/patients/{patient_id}/documents", tags=["documents"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
DocumentRepo = Annotated[DocumentRepository, Depends(get_document_repository)]
TimelineEventRepo = Annotated[TimelineEventRepository, Depends(get_timeline_event_repository)]
UploadStorage = Annotated[LocalUploadStorage, Depends(get_upload_storage)]
ExtractionService = Annotated[DocumentExtractionService, Depends(get_document_extraction_service)]
SummaryService = Annotated[BasicAISummaryService, Depends(get_summary_service)]
TimelineExtractionService = Annotated[
    BasicTimelineEventExtractionService,
    Depends(get_timeline_event_extraction_service),
]


@router.post("", response_model=DocumentUploadRead, status_code=status.HTTP_201_CREATED)
def upload_patient_document(
    patient_id: UUID,
    patients: PatientRepo,
    documents: DocumentRepo,
    timeline_events: TimelineEventRepo,
    storage: UploadStorage,
    extraction_service: ExtractionService,
    summary_service: SummaryService,
    timeline_extraction_service: TimelineExtractionService,
    file: UploadFile = File(...),
) -> DocumentUploadRead:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required.")

    stored_upload = storage.save(patient_id, file)
    document = documents.create(
        DocumentCreate(
            patient_id=patient_id,
            filename=stored_upload.filename,
            content_type=stored_upload.content_type,
            storage_path=stored_upload.storage_path,
        )
    )

    try:
        extracted_text = extraction_service.extract_text(
            storage_path=stored_upload.storage_path,
            content_type=stored_upload.content_type,
        )
    except UnsupportedDocumentTypeError:
        return document

    processed_document = documents.update_processing(
        document,
        DocumentProcessingUpdate(
            extracted_text=extracted_text,
            summary=summary_service.summarize(extracted_text),
        ),
    )

    extracted_events = timeline_extraction_service.extract_events(
        patient_id=patient_id,
        source_document_id=processed_document.id,
        text=extracted_text,
    )
    timeline_events.create_many(extracted_events)

    return processed_document
