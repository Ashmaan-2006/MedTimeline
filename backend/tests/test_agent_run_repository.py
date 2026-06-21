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
