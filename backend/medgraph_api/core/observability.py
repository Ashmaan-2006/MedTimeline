from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import Enum
from typing import Any

from fastapi import FastAPI, Request

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import SpanKind, Status, StatusCode
except ModuleNotFoundError:
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None

    class SpanKind(Enum):
        INTERNAL = "internal"
        SERVER = "server"
        CLIENT = "client"
        CONSUMER = "consumer"

    class StatusCode(Enum):
        ERROR = "error"

    class Status:
        def __init__(self, status_code: StatusCode, description: str | None = None) -> None:
            self.status_code = status_code
            self.description = description

    class _NoOpSpan:
        def __enter__(self) -> "_NoOpSpan":
            return self

        def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
            return False

        def record_exception(self, exc: Exception) -> None:
            return None

        def set_status(self, status: Status) -> None:
            return None

        def set_attribute(self, key: str, value: Any) -> None:
            return None

    class _NoOpTracer:
        def start_as_current_span(self, *args: Any, **kwargs: Any) -> _NoOpSpan:
            return _NoOpSpan()

    class _NoOpTraceModule:
        def get_tracer(self, name: str) -> _NoOpTracer:
            return _NoOpTracer()

        def get_current_span(self) -> _NoOpSpan:
            return _NoOpSpan()

        def set_tracer_provider(self, provider: Any) -> None:
            return None

    trace = _NoOpTraceModule()

from medgraph_api.core.config import Settings, get_settings


_TRACER_NAME = "medgraph_api"
_configured = False


def configure_opentelemetry(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.otel_enabled:
        return
    if TracerProvider is None or Resource is None:
        return

    global _configured
    if _configured:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": settings.otel_service_name}))
    if settings.otel_console_exporter and BatchSpanProcessor and ConsoleSpanExporter:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer() -> trace.Tracer:
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def observe_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, Any] | None = None,
) -> Iterator[None]:
    with get_tracer().start_as_current_span(name, kind=kind, attributes=attributes or {}) as span:
        start = time.perf_counter()
        try:
            yield
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.set_attribute("error.type", exc.__class__.__name__)
            raise
        finally:
            span.set_attribute("duration_ms", round((time.perf_counter() - start) * 1000, 3))


def instrument_fastapi_app(app: FastAPI, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    configure_opentelemetry(settings)
    if not settings.otel_enabled:
        return

    @app.middleware("http")
    async def open_telemetry_request_middleware(
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Any:
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        span_name = f"{request.method} {route_path}"
        with observe_span(
            span_name,
            kind=SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.route": route_path,
                "http.target": request.url.path,
            },
        ):
            response = await call_next(request)
            current_span = trace.get_current_span()
            current_span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= 500:
                current_span.set_status(Status(StatusCode.ERROR))
            return response
