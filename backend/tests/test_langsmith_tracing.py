import os
import sys
from types import SimpleNamespace

from medgraph_api.core.config import Settings
from medgraph_api.core.langsmith_tracing import (
    configure_langsmith_environment,
    is_langsmith_tracing_enabled,
    trace_agent_node,
)


def test_langsmith_tracing_requires_flag_and_api_key() -> None:
    assert not is_langsmith_tracing_enabled(Settings(langsmith_tracing=False))
    assert not is_langsmith_tracing_enabled(Settings(langsmith_tracing=True))
    assert is_langsmith_tracing_enabled(
        Settings(langsmith_tracing=True, langsmith_api_key="test-key")
    )


def test_configure_langsmith_environment_sets_expected_variables(monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    settings = Settings(
        langsmith_tracing=True,
        langsmith_api_key="test-key",
        langsmith_project="medgraph-test",
        langsmith_endpoint="https://example.langsmith.test",
    )

    configure_langsmith_environment(settings)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "test-key"
    assert os.environ["LANGSMITH_PROJECT"] == "medgraph-test"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://example.langsmith.test"
    configure_langsmith_environment(Settings(langsmith_tracing=False))


def test_trace_agent_node_returns_original_when_disabled() -> None:
    def node(state):
        return {"ok": state["ok"]}

    traced = trace_agent_node("intent_classifier", node, Settings(langsmith_tracing=False))

    assert traced is node
    assert traced({"ok": True}) == {"ok": True}


def test_trace_agent_node_preserves_callable_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    trace_calls = []

    def fake_traceable(**kwargs):
        trace_calls.append(kwargs)

        def decorator(func):
            def wrapped(*args, **inner_kwargs):
                return func(*args, **inner_kwargs)

            return wrapped

        return decorator

    monkeypatch.setitem(sys.modules, "langsmith", SimpleNamespace(traceable=fake_traceable))

    def node(state):
        return {"ok": state["ok"]}

    traced = trace_agent_node(
        "intent_classifier",
        node,
        Settings(langsmith_tracing=True, langsmith_api_key="test-key"),
    )

    assert traced is not node
    assert traced({"ok": True}) == {"ok": True}
    assert trace_calls == [
        {
            "name": "clinical_agent.intent_classifier",
            "run_type": "chain",
            "metadata": {"workflow": "clinical_reasoning", "node": "intent_classifier"},
        }
    ]
    configure_langsmith_environment(Settings(langsmith_tracing=False))
