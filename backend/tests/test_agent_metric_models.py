from medgraph_api.db.session import Base
from medgraph_api.models.agent_trace import (
    AgentEvalResult,
    AgentRun,
    LLMCallMetric,
    RetrievalMetric,
)


def test_agent_metric_tables_are_registered_with_metadata() -> None:
    assert AgentEvalResult.__tablename__ in Base.metadata.tables
    assert LLMCallMetric.__tablename__ in Base.metadata.tables
    assert RetrievalMetric.__tablename__ in Base.metadata.tables


def test_agent_run_has_metric_relationships() -> None:
    relationship_names = set(AgentRun.__mapper__.relationships.keys())

    assert "eval_results" in relationship_names
    assert "llm_call_metrics" in relationship_names
    assert "retrieval_metrics" in relationship_names


def test_agent_metric_models_include_operational_columns() -> None:
    eval_columns = set(AgentEvalResult.__table__.columns.keys())
    llm_columns = set(LLMCallMetric.__table__.columns.keys())
    retrieval_columns = set(RetrievalMetric.__table__.columns.keys())

    assert {
        "agent_run_id",
        "evaluator_name",
        "eval_score",
        "latency_ms",
        "error_count",
    } <= eval_columns
    assert {
        "agent_run_id",
        "model_name",
        "latency_ms",
        "tokens_input",
        "tokens_output",
        "error_count",
    } <= llm_columns
    assert {
        "agent_run_id",
        "retrieved_chunk_count",
        "graph_entity_count",
        "graph_relationship_count",
        "error_count",
    } <= retrieval_columns
