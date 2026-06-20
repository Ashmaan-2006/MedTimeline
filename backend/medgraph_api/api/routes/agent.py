from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from medgraph_api.agents.state import create_initial_clinical_agent_state
from medgraph_api.api.deps import get_clinical_reasoning_graph, get_patient_repository
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.schemas.agent import PatientAgentQueryCreate, PatientAgentQueryRead


router = APIRouter(prefix="/patients/{patient_id}/agent", tags=["clinical agent"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
ClinicalReasoningGraph = Annotated[Any, Depends(get_clinical_reasoning_graph)]


@router.post("/query", response_model=PatientAgentQueryRead)
def query_patient_agent(
    patient_id: UUID,
    payload: PatientAgentQueryCreate,
    patients: PatientRepo,
    clinical_reasoning_graph: ClinicalReasoningGraph,
) -> PatientAgentQueryRead:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    final_state = clinical_reasoning_graph.invoke(
        create_initial_clinical_agent_state(
            patient_id=str(patient_id),
            user_question=payload.question,
        )
    )

    return PatientAgentQueryRead(
        answer=final_state.get("final_answer")
        or "Insufficient evidence was retrieved to answer this question.",
        intent=final_state.get("intent"),
        timeline=final_state.get("timeline_context", []),
        contradictions=final_state.get("contradictions", []),
        risk_flags=final_state.get("risk_flags", []),
        citations=final_state.get("citations", []),
        confidence=final_state.get("answer_confidence"),
        limitations=final_state.get("limitations", []),
    )
