from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://medgraph:medgraph@postgres:5432/medgraph"
    upload_dir: str = "storage/uploads"
    celery_broker_url: str = "amqp://guest:guest@rabbitmq:5672//"
    celery_result_backend: str = "rpc://"
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "password"
    llm_provider: str = "openai"
    reasoning_model: str = "gpt-4.1"
    fast_model: str = "gpt-4.1-mini"
    agent_max_steps: int = 8
    agent_timeout_seconds: int = 60
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "medgraph-ai"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    otel_enabled: bool = False
    otel_service_name: str = "medgraph-ai"
    otel_console_exporter: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
