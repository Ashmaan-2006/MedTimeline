from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from medgraph_api.db.session import Base

if TYPE_CHECKING:
    from medgraph_api.models.patient import Patient


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    question: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", server_default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    model_name: Mapped[str | None] = mapped_column(String(255))
    token_count: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship()
    steps: Mapped[list["AgentRunStep"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
    )
    eval_results: Mapped[list["AgentEvalResult"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
    )
    llm_call_metrics: Mapped[list["LLMCallMetric"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
    )
    retrieval_metrics: Mapped[list["RetrievalMetric"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
    )


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    step_name: Mapped[str] = mapped_column(String(128), index=True)
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="completed", server_default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run: Mapped[AgentRun] = relationship(back_populates="steps")


class AgentEvalResult(Base):
    __tablename__ = "agent_eval_results"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    evaluator_name: Mapped[str] = mapped_column(String(128), index=True)
    eval_score: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    details_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run: Mapped[AgentRun] = relationship(back_populates="eval_results")


class LLMCallMetric(Base):
    __tablename__ = "llm_call_metrics"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    step_name: Mapped[str | None] = mapped_column(String(128), index=True)
    model_name: Mapped[str | None] = mapped_column(String(255), index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run: Mapped[AgentRun] = relationship(back_populates="llm_call_metrics")


class RetrievalMetric(Base):
    __tablename__ = "retrieval_metrics"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        index=True,
    )
    retrieval_type: Mapped[str] = mapped_column(String(64), index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retrieved_chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    graph_entity_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    graph_relationship_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent_run: Mapped[AgentRun] = relationship(back_populates="retrieval_metrics")
