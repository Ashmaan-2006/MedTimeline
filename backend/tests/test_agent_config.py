from typing import TypedDict

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph

from medgraph_api.core.agent_config import (
    UnsupportedLLMProviderError,
    create_chat_model,
    create_state_graph,
    get_llm_provider,
    get_model_name,
)
from medgraph_api.core.config import Settings


class AgentState(TypedDict):
    question: str


def test_create_state_graph_initializes_langgraph_graph() -> None:
    graph = create_state_graph(AgentState)

    assert isinstance(graph, StateGraph)


def test_get_model_name_uses_reasoning_and_fast_models() -> None:
    settings = Settings(reasoning_model="reasoning-model", fast_model="fast-model")

    assert get_model_name("reasoning", settings) == "reasoning-model"
    assert get_model_name("fast", settings) == "fast-model"


def test_get_llm_provider_rejects_unknown_provider() -> None:
    settings = Settings(llm_provider="unsupported")

    with pytest.raises(UnsupportedLLMProviderError, match="Unsupported LLM_PROVIDER"):
        get_llm_provider(settings)


def test_create_chat_model_initializes_openai_client() -> None:
    settings = Settings(
        llm_provider="openai",
        fast_model="gpt-test-fast",
        agent_timeout_seconds=12,
        openai_api_key="test-openai-key",
    )

    model = create_chat_model("fast", settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-test-fast"
    assert model.request_timeout == 12


def test_create_chat_model_initializes_anthropic_client() -> None:
    settings = Settings(
        llm_provider="anthropic",
        reasoning_model="claude-test-reasoning",
        agent_timeout_seconds=15,
        anthropic_api_key="test-anthropic-key",
    )

    model = create_chat_model("reasoning", settings)

    assert isinstance(model, ChatAnthropic)
    assert model.model == "claude-test-reasoning"
    assert model.default_request_timeout == 15
