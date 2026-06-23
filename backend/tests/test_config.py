from medgraph_api.core.config import Settings


def test_settings_include_neo4j_connection_defaults() -> None:
    settings = Settings()

    assert settings.neo4j_uri == "bolt://neo4j:7687"
    assert settings.neo4j_username == "neo4j"
    assert settings.neo4j_password == "password"


def test_settings_include_agent_config_defaults() -> None:
    settings = Settings()

    assert settings.llm_provider == "openai"
    assert settings.reasoning_model == "gpt-4.1"
    assert settings.fast_model == "gpt-4.1-mini"
    assert settings.agent_max_steps == 8
    assert settings.agent_timeout_seconds == 60
    assert settings.openai_api_key is None
    assert settings.anthropic_api_key is None


def test_settings_include_langsmith_tracing_defaults(monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)

    settings = Settings()

    assert settings.langsmith_tracing is False
    assert settings.langsmith_api_key is None
    assert settings.langsmith_project == "medgraph-ai"
    assert settings.langsmith_endpoint == "https://api.smith.langchain.com"


def test_settings_include_opentelemetry_defaults() -> None:
    settings = Settings()

    assert settings.otel_enabled is False
    assert settings.otel_service_name == "medgraph-ai"
    assert settings.otel_console_exporter is True
