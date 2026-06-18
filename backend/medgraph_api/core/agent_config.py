from enum import StrEnum
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph

from medgraph_api.core.config import Settings, get_settings


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


ModelSpeed = Literal["reasoning", "fast"]


class UnsupportedLLMProviderError(ValueError):
    pass


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    try:
        return LLMProvider(settings.llm_provider.lower())
    except ValueError as exc:
        raise UnsupportedLLMProviderError(
            f"Unsupported LLM_PROVIDER: {settings.llm_provider}"
        ) from exc


def get_model_name(speed: ModelSpeed, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if speed == "reasoning":
        return settings.reasoning_model
    return settings.fast_model


def create_chat_model(
    speed: ModelSpeed = "fast",
    settings: Settings | None = None,
) -> BaseChatModel:
    settings = settings or get_settings()
    model_name = get_model_name(speed, settings)
    provider = get_llm_provider(settings)

    if provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=model_name,
            timeout=settings.agent_timeout_seconds,
        )

    if provider == LLMProvider.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=model_name,
            timeout=settings.agent_timeout_seconds,
        )

    raise UnsupportedLLMProviderError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


def create_state_graph(state_schema: type) -> StateGraph:
    return StateGraph(state_schema)
