from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from medgraph_api.api.deps import (
    get_clinical_graph_query_service,
    get_patient_repository,
)
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.schemas.clinical_graph import (
    EntityPathStepRead,
    EvidenceChunkRead,
    GraphEntityRead,
    GraphRelationshipRead,
    PatientGraphSummaryRead,
)
from medgraph_api.services.graph_query_service import ClinicalGraphQueryService

router = APIRouter(prefix="/patients/{patient_id}/graph", tags=["clinical graph"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
GraphQuery = Annotated[ClinicalGraphQueryService, Depends(get_clinical_graph_query_service)]


def ensure_patient_exists(patient_id: UUID, patients: PatientRepo) -> None:
    if patients.get(patient_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")


@router.get("/summary", response_model=PatientGraphSummaryRead)
def get_patient_graph_summary(
    patient_id: UUID,
    patients: PatientRepo,
    graph_query: GraphQuery,
) -> PatientGraphSummaryRead:
    ensure_patient_exists(patient_id, patients)
    return graph_query.get_patient_graph_summary(str(patient_id))


@router.get("/entities", response_model=list[GraphEntityRead])
def get_patient_graph_entities(
    patient_id: UUID,
    patients: PatientRepo,
    graph_query: GraphQuery,
) -> list[GraphEntityRead]:
    ensure_patient_exists(patient_id, patients)
    return graph_query.get_entities_for_patient(str(patient_id))


@router.get("/relationships", response_model=list[GraphRelationshipRead])
def get_patient_graph_relationships(
    patient_id: UUID,
    patients: PatientRepo,
    graph_query: GraphQuery,
) -> list[GraphRelationshipRead]:
    ensure_patient_exists(patient_id, patients)
    return graph_query.get_relationships_for_patient(str(patient_id))


@router.get("/entity/{entity_name}/evidence", response_model=list[EvidenceChunkRead])
def get_patient_graph_entity_evidence(
    patient_id: UUID,
    entity_name: str,
    patients: PatientRepo,
    graph_query: GraphQuery,
) -> list[EvidenceChunkRead]:
    ensure_patient_exists(patient_id, patients)
    try:
        return graph_query.get_evidence_chunks_for_entity(str(patient_id), entity_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/path", response_model=list[list[EntityPathStepRead]])
def get_patient_graph_path(
    patient_id: UUID,
    patients: PatientRepo,
    graph_query: GraphQuery,
    source: str = Query(..., min_length=1),
    target: str = Query(..., min_length=1),
    max_hops: int = Query(4, ge=1, le=6),
) -> list[list[EntityPathStepRead]]:
    ensure_patient_exists(patient_id, patients)
    try:
        return graph_query.get_paths_between_entities(
            patient_id=str(patient_id),
            source=source,
            target=target,
            max_hops=max_hops,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
