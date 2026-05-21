from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from medgraph_api.api.deps import get_patient_repository, get_upload_storage
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.schemas.document import DocumentUploadRead
from medgraph_api.services.storage import LocalUploadStorage

router = APIRouter(prefix="/patients/{patient_id}/documents", tags=["documents"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
UploadStorage = Annotated[LocalUploadStorage, Depends(get_upload_storage)]


@router.post("", response_model=DocumentUploadRead, status_code=status.HTTP_201_CREATED)
def upload_patient_document(
    patient_id: UUID,
    patients: PatientRepo,
    storage: UploadStorage,
    file: UploadFile = File(...),
) -> DocumentUploadRead:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required.")

    stored_upload = storage.save(patient_id, file)
    return DocumentUploadRead(patient_id=patient_id, **stored_upload.__dict__)

