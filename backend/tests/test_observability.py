import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from medgraph_api.core.config import Settings
from medgraph_api.core.observability import instrument_fastapi_app, observe_span


def test_observe_span_records_exceptions(monkeypatch) -> None:
    class FakeSpan:
        def __init__(self) -> None:
            self.exceptions = []
            self.status = None
            self.attributes = {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def record_exception(self, exc: Exception) -> None:
            self.exceptions.append(exc)

        def set_status(self, status) -> None:
            self.status = status

        def set_attribute(self, key: str, value) -> None:
            self.attributes[key] = value

    class FakeTracer:
        def __init__(self, span: FakeSpan) -> None:
            self.span = span

        def start_as_current_span(self, *args, **kwargs):
            return self.span

    fake_span = FakeSpan()
    monkeypatch.setattr(
        "medgraph_api.core.observability.get_tracer",
        lambda: FakeTracer(fake_span),
    )

    with pytest.raises(RuntimeError, match="boom"):
        with observe_span("test.failure"):
            raise RuntimeError("boom")

    assert isinstance(fake_span.exceptions[0], RuntimeError)
    assert fake_span.status.status_code.name == "ERROR"
    assert fake_span.attributes["error.type"] == "RuntimeError"
    assert "duration_ms" in fake_span.attributes


def test_instrument_fastapi_app_is_noop_when_disabled() -> None:
    app = FastAPI()

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    instrument_fastapi_app(app, Settings(otel_enabled=False))

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
