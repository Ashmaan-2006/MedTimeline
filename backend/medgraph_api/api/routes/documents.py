from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from medgraph_api.api.deps import (
    get_document_repository,
    get_patient_repository,
    get_upload_storage,
)
from medgraph_api.crud.documents import DocumentRepository
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.schemas.document import (
    DocumentCreate,
    DocumentProcessingStatusRead,
    DocumentProcessingStatus,
    DocumentProcessingUpdate,
    DocumentUploadRead,
)
from medgraph_api.services.storage import LocalUploadStorage
from medgraph_api.tasks.document_tasks import process_document_task

router = APIRouter(prefix="/patients/{patient_id}/documents", tags=["documents"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
DocumentRepo = Annotated[DocumentRepository, Depends(get_document_repository)]
UploadStorage = Annotated[LocalUploadStorage, Depends(get_upload_storage)]


@router.get("", response_model=list[DocumentUploadRead])
def list_patient_documents(
    patient_id: UUID,
    patients: PatientRepo,
    documents: DocumentRepo,
    skip: int = 0,
    limit: int = 100,
) -> list[DocumentUploadRead]:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    return documents.list_for_patient(patient_id=patient_id, skip=skip, limit=limit)


@router.get("/{document_id}/status", response_model=DocumentProcessingStatusRead)
def get_patient_document_processing_status(
    patient_id: UUID,
    document_id: UUID,
    patients: PatientRepo,
    documents: DocumentRepo,
) -> DocumentProcessingStatusRead:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    document = documents.get(document_id)
    if document is None or document.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return DocumentProcessingStatusRead(
        document_id=document.id,
        status=document.processing_status,
        started_at=document.processing_started_at,
        completed_at=document.processing_completed_at,
        error=document.processing_error,
    )


@router.post("", response_model=DocumentUploadRead, status_code=status.HTTP_201_CREATED)
def upload_patient_document(
    patient_id: UUID,
    patients: PatientRepo,
    documents: DocumentRepo,
    storage: UploadStorage,
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

    queued_task = process_document_task.delay(str(document.id))
    return documents.update_processing(
        document,
        DocumentProcessingUpdate(
            extracted_text=document.extracted_text,
            summary=document.summary,
            processing_status=DocumentProcessingStatus.QUEUED,
            processing_error=None,
            celery_task_id=queued_task.id,
            processing_attempts=document.processing_attempts,
        ),
    )
