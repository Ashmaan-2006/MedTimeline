from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from medgraph_api.api.deps import get_patient_rag_query_service, get_patient_repository
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.schemas.rag import PatientRagQueryCreate, PatientRagQueryRead
from medgraph_api.services.rag import PatientRagQueryService

router = APIRouter(prefix="/patients/{patient_id}/rag", tags=["rag"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
RagQueryService = Annotated[PatientRagQueryService, Depends(get_patient_rag_query_service)]


@router.post("/query", response_model=PatientRagQueryRead)
def query_patient_documents(
    patient_id: UUID,
    payload: PatientRagQueryCreate,
    patients: PatientRepo,
    rag_query_service: RagQueryService,
) -> PatientRagQueryRead:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    return rag_query_service.answer_question(
        patient_id=patient_id,
        question=payload.question,
        limit=payload.limit,
    )
