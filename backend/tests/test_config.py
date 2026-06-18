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
