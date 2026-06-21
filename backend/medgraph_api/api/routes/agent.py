import time
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from medgraph_api.agents.state import create_initial_clinical_agent_state
from medgraph_api.api.deps import (
    get_agent_run_repository,
    get_clinical_reasoning_graph,
    get_patient_repository,
)
from medgraph_api.core.config import Settings, get_settings
from medgraph_api.crud.agent_runs import AgentRunRepository
from medgraph_api.crud.patients import PatientRepository
from medgraph_api.schemas.agent import PatientAgentQueryCreate, PatientAgentQueryRead


router = APIRouter(prefix="/patients/{patient_id}/agent", tags=["clinical agent"])

PatientRepo = Annotated[PatientRepository, Depends(get_patient_repository)]
ClinicalReasoningGraph = Annotated[Any, Depends(get_clinical_reasoning_graph)]
AgentRunRepo = Annotated[AgentRunRepository, Depends(get_agent_run_repository)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post("/query", response_model=PatientAgentQueryRead)
def query_patient_agent(
    patient_id: UUID,
    payload: PatientAgentQueryCreate,
    patients: PatientRepo,
    clinical_reasoning_graph: ClinicalReasoningGraph,
    agent_runs: AgentRunRepo,
    settings: AppSettings,
) -> PatientAgentQueryRead:
    patient = patients.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    started_at = time.perf_counter()
    agent_run = agent_runs.start_run(
        patient_id=patient_id,
        question=payload.question,
        model_name=settings.reasoning_model,
    )
    try:
        final_state = execute_clinical_reasoning_graph_with_trace(
            graph=clinical_reasoning_graph,
            initial_state=create_initial_clinical_agent_state(
                patient_id=str(patient_id),
                user_question=payload.question,
            ),
            agent_runs=agent_runs,
            agent_run_id=agent_run.id,
        )
    except Exception as exc:
        latency_ms = elapsed_ms(started_at)
        agent_runs.fail_run(
            run=agent_run,
            latency_ms=latency_ms,
            error=safe_error_message(exc),
        )
        raise

    agent_runs.complete_run(
        run=agent_run,
        intent=final_state.get("intent"),
        latency_ms=elapsed_ms(started_at),
        token_count=estimate_token_count(final_state),
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


def execute_clinical_reasoning_graph_with_trace(
    graph: Any,
    initial_state: dict,
    agent_runs: AgentRunRepository,
    agent_run_id: UUID,
) -> dict:
    if not hasattr(graph, "stream"):
        step_started_at = time.perf_counter()
        final_state = graph.invoke(initial_state)
        agent_runs.create_step(
            agent_run_id=agent_run_id,
            step_name="clinical_reasoning_graph",
            input_summary=summarize_state(initial_state),
            output_summary=summarize_state(final_state),
            latency_ms=elapsed_ms(step_started_at),
        )
        return final_state

    final_state = initial_state.copy()
    previous_summary = summarize_state(final_state)
    step_started_at = time.perf_counter()
    for chunk in graph.stream(initial_state, stream_mode="updates"):
        if not isinstance(chunk, dict):
            continue
        for step_name, update in chunk.items():
            if not isinstance(update, dict):
                continue
            final_state.update(update)
            output_summary = summarize_state(final_state)
            agent_runs.create_step(
                agent_run_id=agent_run_id,
                step_name=step_name,
                input_summary=previous_summary,
                output_summary=output_summary,
                latency_ms=elapsed_ms(step_started_at),
            )
            previous_summary = output_summary
            step_started_at = time.perf_counter()
    return final_state


def summarize_state(state: dict) -> str:
    summary_parts = [
        f"intent={state.get('intent')}",
        f"vector_context={len(state.get('vector_context', []))}",
        f"graph_context={len(state.get('graph_context', []))}",
        f"timeline_context={len(state.get('timeline_context', []))}",
        f"contradictions={len(state.get('contradictions', []))}",
        f"risk_flags={len(state.get('risk_flags', []))}",
        f"citations={len(state.get('citations', []))}",
    ]
    if state.get("final_answer"):
        summary_parts.append("final_answer=set")
    return "; ".join(summary_parts)


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def estimate_token_count(state: dict) -> int | None:
    answer = state.get("final_answer")
    if not isinstance(answer, str) or not answer:
        return None
    return max(1, len(answer.split()))


def safe_error_message(exc: Exception) -> str:
    return str(exc)[:500] or exc.__class__.__name__
