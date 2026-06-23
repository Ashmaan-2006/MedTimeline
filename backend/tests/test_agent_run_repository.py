from uuid import uuid4

from medgraph_api.crud.agent_runs import AgentRunRepository


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commit_count = 0
        self.refreshed = []

    def add(self, value) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commit_count += 1

    def refresh(self, value) -> None:
        self.refreshed.append(value)


def test_agent_run_repository_records_run_lifecycle() -> None:
    session = FakeSession()
    repository = AgentRunRepository(session)
    patient_id = uuid4()

    run = repository.start_run(
        patient_id=patient_id,
        question="Did symptoms worsen?",
        model_name="gpt-test",
    )
    completed_run = repository.complete_run(
        run=run,
        intent="symptom_progression",
        latency_ms=123,
        token_count=42,
    )

    assert completed_run.patient_id == patient_id
    assert completed_run.question == "Did symptoms worsen?"
    assert completed_run.model_name == "gpt-test"
    assert completed_run.intent == "symptom_progression"
    assert completed_run.status == "completed"
    assert completed_run.latency_ms == 123
    assert completed_run.token_count == 42
    assert session.commit_count == 2


def test_agent_run_repository_records_step_and_failure() -> None:
    session = FakeSession()
    repository = AgentRunRepository(session)
    run = repository.start_run(uuid4(), "Question?")

    step = repository.create_step(
        agent_run_id=run.id,
        step_name="intent_classifier",
        input_summary="intent=None",
        output_summary="intent=general_question",
        latency_ms=7,
    )
    failed_run = repository.fail_run(
        run=run,
        intent="general_question",
        latency_ms=21,
        error="Graph failed",
    )

    assert step.agent_run_id == run.id
    assert step.step_name == "intent_classifier"
    assert step.status == "completed"
    assert failed_run.status == "failed"
    assert failed_run.error == "Graph failed"


def test_agent_run_repository_records_eval_result() -> None:
    session = FakeSession()
    repository = AgentRunRepository(session)
    run = repository.start_run(uuid4(), "Question?")

    result = repository.record_eval_result(
        agent_run_id=run.id,
        evaluator_name="groundedness",
        eval_score=0.87,
        latency_ms=42,
        error_count=1,
        details_json='{"unsupported_claims": 1}',
    )

    assert result.agent_run_id == run.id
    assert result.evaluator_name == "groundedness"
    assert result.eval_score == 0.87
    assert result.latency_ms == 42
    assert result.error_count == 1
    assert result.details_json == '{"unsupported_claims": 1}'


def test_agent_run_repository_records_llm_call_metric() -> None:
    session = FakeSession()
    repository = AgentRunRepository(session)
    run = repository.start_run(uuid4(), "Question?")

    metric = repository.record_llm_call_metric(
        agent_run_id=run.id,
        step_name="answer_generator",
        model_name="gpt-test",
        latency_ms=312,
        tokens_input=1200,
        tokens_output=240,
        error_count=0,
    )

    assert metric.agent_run_id == run.id
    assert metric.step_name == "answer_generator"
    assert metric.model_name == "gpt-test"
    assert metric.latency_ms == 312
    assert metric.tokens_input == 1200
    assert metric.tokens_output == 240
    assert metric.error_count == 0


def test_agent_run_repository_records_retrieval_metric() -> None:
    session = FakeSession()
    repository = AgentRunRepository(session)
    run = repository.start_run(uuid4(), "Question?")

    metric = repository.record_retrieval_metric(
        agent_run_id=run.id,
        retrieval_type="hybrid",
        latency_ms=88,
        retrieved_chunk_count=5,
        graph_entity_count=7,
        graph_relationship_count=3,
        error_count=0,
    )

    assert metric.agent_run_id == run.id
    assert metric.retrieval_type == "hybrid"
    assert metric.latency_ms == 88
    assert metric.retrieved_chunk_count == 5
    assert metric.graph_entity_count == 7
    assert metric.graph_relationship_count == 3
    assert metric.error_count == 0
