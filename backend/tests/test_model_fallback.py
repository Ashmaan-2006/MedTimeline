import time
from uuid import uuid4

from medgraph_api.agents.nodes import answer_generator
from medgraph_api.agents.state import create_initial_clinical_agent_state
from medgraph_api.services.model_fallback import (
    FallbackTextGenerationService,
    ModelFallbackRunner,
    ModelProviderError,
)
from medgraph_api.services.summarization import BasicAISummaryService, FallbackAISummaryService


def test_model_fallback_runner_uses_primary_when_successful() -> None:
    result = ModelFallbackRunner(timeout_seconds=1).run(
        primary=lambda: "primary",
        fallback=lambda: "fallback",
        operation_name="test_generation",
    )

    assert result.output == "primary"
    assert result.used_fallback is False
    assert result.warning is None


def test_model_fallback_runner_uses_fallback_on_provider_error() -> None:
    def primary() -> str:
        raise ModelProviderError("primary unavailable")

    result = ModelFallbackRunner(timeout_seconds=1).run(
        primary=primary,
        fallback=lambda: "fallback",
        operation_name="test_generation",
    )

    assert result.output == "fallback"
    assert result.used_fallback is True
    assert "test_generation used fallback model" in result.warning


def test_model_fallback_runner_uses_fallback_on_timeout() -> None:
    def primary() -> str:
        time.sleep(0.2)
        return "primary"

    result = ModelFallbackRunner(timeout_seconds=0).run(
        primary=primary,
        fallback=lambda: "fallback",
        operation_name="test_generation",
    )

    assert result.output == "fallback"
    assert result.used_fallback is True


def test_fallback_text_generation_service_uses_fallback_client() -> None:
    service = FallbackTextGenerationService(
        primary=lambda prompt: (_ for _ in ()).throw(ModelProviderError("failed")),
        fallback=lambda prompt: f"fallback: {prompt}",
        operation_name="entity_extraction",
        timeout_seconds=1,
    )

    assert service.generate("prompt") == "fallback: prompt"


def test_fallback_summary_service_marks_lower_confidence_summary() -> None:
    class FailingSummaryService(BasicAISummaryService):
        def summarize(self, text: str) -> str:
            raise ModelProviderError("failed")

    service = FallbackAISummaryService(
        primary=FailingSummaryService(),
        fallback=BasicAISummaryService(max_sentences=1),
        timeout_seconds=1,
    )

    summary = service.summarize("First clinical sentence. Second clinical sentence.")

    assert summary == (
        "First clinical sentence. Fallback summary used; review with lower confidence."
    )


def test_answer_generation_falls_back_with_low_confidence(monkeypatch) -> None:
    def failing_primary(state):
        raise ModelProviderError("primary answer failed")

    monkeypatch.setattr(
        answer_generator,
        "_generate_grounded_clinical_answer",
        failing_primary,
    )
    state = create_initial_clinical_agent_state(
        patient_id=str(uuid4()),
        user_question="Did symptoms worsen?",
    )
    state["vector_context"] = [
        {
            "chunk_id": "chunk-1",
            "document_id": "document-1",
            "content": "Patient reported dizziness after medication change.",
        }
    ]

    answer = answer_generator.generate_grounded_clinical_answer(state)

    assert answer["confidence"] == "low"
    assert "lower-confidence fallback answer" in answer["answer"].lower()
    assert "answer_generation used fallback model" in answer["answer"]
