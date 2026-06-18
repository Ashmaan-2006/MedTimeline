from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from medgraph_api.api.deps import (
    get_clinical_graph_sync_service,
    get_patient_repository,
    get_timeline_event_repository,
)
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.crud.timeline_events import TimelineEventRepository
from medgraph_api.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from medgraph_api.schemas.timeline_event import TimelineEventRead
from medgraph_api.services.clinical_graph_sync import ClinicalGraphSyncService

router = APIRouter(prefix="/patients", tags=["patients"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
TimelineEventRepo = Annotated[TimelineEventRepository, Depends(get_timeline_event_repository)]
GraphSync = Annotated[ClinicalGraphSyncService, Depends(get_clinical_graph_sync_service)]


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, patients: PatientRepo, graph_sync: GraphSync) -> PatientRead:
    existing_patient = patients.get_by_medical_record_number(payload.medical_record_number)
    if existing_patient is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A patient with this medical record number already exists.",
        )

    patient = patients.create(payload)
    graph_sync.sync_patient(patient)
    return patient


@router.get("", response_model=list[PatientRead])
def list_patients(patients: PatientRepo, skip: int = 0, limit: int = 100) -> list[PatientRead]:
    return patients.list(skip=skip, limit=limit)


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: UUID, patients: PatientRepo) -> PatientRead:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    return patient


@router.get("/{patient_id}/timeline-events", response_model=list[TimelineEventRead])
def list_patient_timeline_events(
    patient_id: UUID,
    patients: PatientRepo,
    timeline_events: TimelineEventRepo,
    skip: int = 0,
    limit: int = 100,
) -> list[TimelineEventRead]:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    return timeline_events.list_for_patient(patient_id=patient_id, skip=skip, limit=limit)


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(patient_id: UUID, payload: PatientUpdate, patients: PatientRepo) -> PatientRead:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    if payload.medical_record_number is not None:
        existing_patient = patients.get_by_medical_record_number(payload.medical_record_number)
        if existing_patient is not None and existing_patient.id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A patient with this medical record number already exists.",
            )

    return patients.update(patient, payload)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: UUID, patients: PatientRepo) -> Response:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    patients.delete(patient)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
