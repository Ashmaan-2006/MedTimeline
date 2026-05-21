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
from medgraph_api.schemas.document import DocumentCreate, DocumentUploadRead
from medgraph_api.services.storage import LocalUploadStorage

router = APIRouter(prefix="/patients/{patient_id}/documents", tags=["documents"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
DocumentRepo = Annotated[DocumentRepository, Depends(get_document_repository)]
UploadStorage = Annotated[LocalUploadStorage, Depends(get_upload_storage)]


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
    return documents.create(
        DocumentCreate(
            patient_id=patient_id,
            filename=stored_upload.filename,
            content_type=stored_upload.content_type,
            storage_path=stored_upload.storage_path,
        )
    )
