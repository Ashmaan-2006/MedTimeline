from medgraph_api.core.config import Settings


def test_settings_include_neo4j_connection_defaults() -> None:
    settings = Settings()

    assert settings.neo4j_uri == "bolt://neo4j:7687"
    assert settings.neo4j_username == "neo4j"
    assert settings.neo4j_password == "password"
