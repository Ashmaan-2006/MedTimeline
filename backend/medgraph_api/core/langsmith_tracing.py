import os
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from medgraph_api.core.config import Settings, get_settings


T = TypeVar("T", bound=Callable[..., Any])


def is_langsmith_tracing_enabled(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.langsmith_tracing and bool(settings.langsmith_api_key)


def configure_langsmith_environment(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not is_langsmith_tracing_enabled(settings):
        os.environ["LANGSMITH_TRACING"] = "false"
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key or ""
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint


def trace_agent_node(
    node_name: str,
    node: T,
    settings: Settings | None = None,
) -> T:
    settings = settings or get_settings()
    if not is_langsmith_tracing_enabled(settings):
        return node

    configure_langsmith_environment(settings)

    try:
        from langsmith import traceable
    except ImportError:
        return node

    traced_node = traceable(
        name=f"clinical_agent.{node_name}",
        run_type="chain",
        metadata={"workflow": "clinical_reasoning", "node": node_name},
    )(node)

    @wraps(node)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        return traced_node(*args, **kwargs)

    return wrapped  # type: ignore[return-value]
