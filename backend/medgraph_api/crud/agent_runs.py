from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from medgraph_api.models.agent_trace import AgentRun, AgentRunStep


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
