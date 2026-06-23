from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from medgraph_api.models.agent_trace import (
    AgentEvalResult,
    AgentRun,
    AgentRunStep,
    LLMCallMetric,
    RetrievalMetric,
)


class AgentRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start_run(
        self,
        patient_id: UUID,
        question: str,
        model_name: str | None = None,
    ) -> AgentRun:
        run = AgentRun(
            patient_id=patient_id,
            question=question,
            model_name=model_name,
            status="running",
            started_at=datetime.now(UTC),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def complete_run(
        self,
        run: AgentRun,
        intent: str | None,
        latency_ms: int,
        token_count: int | None = None,
    ) -> AgentRun:
        run.intent = intent
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        run.latency_ms = latency_ms
        run.token_count = token_count
        run.error = None
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def fail_run(
        self,
        run: AgentRun,
        latency_ms: int,
        error: str,
        intent: str | None = None,
    ) -> AgentRun:
        run.intent = intent
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        run.latency_ms = latency_ms
        run.error = error
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def create_step(
        self,
        agent_run_id: UUID,
        step_name: str,
        input_summary: str | None,
        output_summary: str | None,
        latency_ms: int | None,
        status: str = "completed",
    ) -> AgentRunStep:
        step = AgentRunStep(
            agent_run_id=agent_run_id,
            step_name=step_name,
            input_summary=input_summary,
            output_summary=output_summary,
            latency_ms=latency_ms,
            status=status,
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def record_eval_result(
        self,
        agent_run_id: UUID,
        evaluator_name: str,
        eval_score: float | None,
        latency_ms: int | None = None,
        error_count: int = 0,
        details_json: str | None = None,
    ) -> AgentEvalResult:
        result = AgentEvalResult(
            agent_run_id=agent_run_id,
            evaluator_name=evaluator_name,
            eval_score=eval_score,
            latency_ms=latency_ms,
            error_count=error_count,
            details_json=details_json,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result

    def record_llm_call_metric(
        self,
        agent_run_id: UUID,
        step_name: str | None,
        model_name: str | None,
        latency_ms: int | None,
        tokens_input: int | None,
        tokens_output: int | None,
        error_count: int = 0,
    ) -> LLMCallMetric:
        metric = LLMCallMetric(
            agent_run_id=agent_run_id,
            step_name=step_name,
            model_name=model_name,
            latency_ms=latency_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            error_count=error_count,
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric

    def record_retrieval_metric(
        self,
        agent_run_id: UUID,
        retrieval_type: str,
        latency_ms: int | None,
        retrieved_chunk_count: int = 0,
        graph_entity_count: int = 0,
        graph_relationship_count: int = 0,
        error_count: int = 0,
    ) -> RetrievalMetric:
        metric = RetrievalMetric(
            agent_run_id=agent_run_id,
            retrieval_type=retrieval_type,
            latency_ms=latency_ms,
            retrieved_chunk_count=retrieved_chunk_count,
            graph_entity_count=graph_entity_count,
            graph_relationship_count=graph_relationship_count,
            error_count=error_count,
        )
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        return metric
