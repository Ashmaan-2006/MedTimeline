from dataclasses import dataclass
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from medgraph_api.agents.nodes.answer_generator import generate_grounded_answer_node
from medgraph_api.agents.nodes.contradiction_checker import check_contradictions_node
from medgraph_api.agents.nodes.evidence_planner import plan_evidence_node
from medgraph_api.agents.nodes.graph_retriever import retrieve_graph_context_node
from medgraph_api.agents.nodes.intent_classifier import classify_intent_node
from medgraph_api.agents.nodes.risk_flagger import flag_clinical_risks_node
from medgraph_api.agents.nodes.timeline_reasoner import reason_over_timeline_node
from medgraph_api.agents.nodes.vector_retriever import retrieve_vector_context_node
from medgraph_api.agents.state import ClinicalAgentState
from medgraph_api.services.graph_query_service import ClinicalGraphQueryService
from medgraph_api.services.similarity_search import PatientDocumentSimilaritySearchService


RetrievalRoute = Literal["hybrid", "vector_only", "graph_only", "no_retrieval"]
PostRetrievalRoute = Literal["timeline_reasoner", "contradiction_checker"]
PostContradictionRoute = Literal["risk_flagger", "answer_generator"]

INTENT_CLASSIFIER_NODE = "intent_classifier"
EVIDENCE_PLANNER_NODE = "evidence_planner"
VECTOR_RETRIEVER_NODE = "vector_retriever"
GRAPH_RETRIEVER_NODE = "graph_retriever"
POST_RETRIEVAL_NODE = "post_retrieval"
TIMELINE_REASONER_NODE = "timeline_reasoner"
CONTRADICTION_CHECKER_NODE = "contradiction_checker"
RISK_FLAGGER_NODE = "risk_flagger"
ANSWER_GENERATOR_NODE = "answer_generator"


@dataclass(frozen=True)
class ClinicalReasoningGraphServices:
    similarity_search: PatientDocumentSimilaritySearchService
    graph_query: ClinicalGraphQueryService
    retrieval_limit: int = 5


def create_clinical_reasoning_graph(
    services: ClinicalReasoningGraphServices,
) -> CompiledStateGraph:
    graph = StateGraph(ClinicalAgentState)

    graph.add_node(INTENT_CLASSIFIER_NODE, classify_intent_node)
    graph.add_node(EVIDENCE_PLANNER_NODE, plan_evidence_node)
    graph.add_node(
        VECTOR_RETRIEVER_NODE,
        lambda state: _vector_retrieval_update(state, services),
    )
    graph.add_node(
        GRAPH_RETRIEVER_NODE,
        lambda state: _graph_retrieval_update(state, services),
    )
    graph.add_node(POST_RETRIEVAL_NODE, _pass_through_node)
    graph.add_node(TIMELINE_REASONER_NODE, reason_over_timeline_node)
    graph.add_node(CONTRADICTION_CHECKER_NODE, check_contradictions_node)
    graph.add_node(RISK_FLAGGER_NODE, flag_clinical_risks_node)
    graph.add_node(ANSWER_GENERATOR_NODE, generate_grounded_answer_node)

    graph.add_edge(START, INTENT_CLASSIFIER_NODE)
    graph.add_edge(INTENT_CLASSIFIER_NODE, EVIDENCE_PLANNER_NODE)
    graph.add_conditional_edges(EVIDENCE_PLANNER_NODE, route_retrieval_nodes)
    graph.add_edge(VECTOR_RETRIEVER_NODE, POST_RETRIEVAL_NODE)
    graph.add_edge(GRAPH_RETRIEVER_NODE, POST_RETRIEVAL_NODE)
    graph.add_conditional_edges(
        POST_RETRIEVAL_NODE,
        route_after_retrieval,
        {
            "timeline_reasoner": TIMELINE_REASONER_NODE,
            "contradiction_checker": CONTRADICTION_CHECKER_NODE,
        },
    )
    graph.add_edge(TIMELINE_REASONER_NODE, CONTRADICTION_CHECKER_NODE)
    graph.add_conditional_edges(
        CONTRADICTION_CHECKER_NODE,
        route_after_contradiction_check,
        {
            "risk_flagger": RISK_FLAGGER_NODE,
            "answer_generator": ANSWER_GENERATOR_NODE,
        },
    )
    graph.add_edge(RISK_FLAGGER_NODE, ANSWER_GENERATOR_NODE)
    graph.add_edge(ANSWER_GENERATOR_NODE, END)

    return graph.compile()


def route_retrieval(state: ClinicalAgentState) -> RetrievalRoute:
    evidence_plan = state.get("evidence_plan") or {}
    needs_vector_search = evidence_plan.get("needs_vector_search") is True
    needs_graph_search = evidence_plan.get("needs_graph_search") is True

    if needs_vector_search and needs_graph_search:
        return "hybrid"
    if needs_vector_search:
        return "vector_only"
    if needs_graph_search:
        return "graph_only"
    return "no_retrieval"


def route_retrieval_nodes(state: ClinicalAgentState) -> list[str]:
    route = route_retrieval(state)
    if route == "hybrid":
        return [VECTOR_RETRIEVER_NODE, GRAPH_RETRIEVER_NODE]
    if route == "vector_only":
        return [VECTOR_RETRIEVER_NODE]
    if route == "graph_only":
        return [GRAPH_RETRIEVER_NODE]
    return [POST_RETRIEVAL_NODE]


def route_after_retrieval(state: ClinicalAgentState) -> PostRetrievalRoute:
    evidence_plan = state.get("evidence_plan") or {}
    if state.get("intent") == "contradiction_check" and not evidence_plan.get("needs_timeline"):
        return "contradiction_checker"
    if evidence_plan.get("needs_timeline") is False:
        return "contradiction_checker"
    return "timeline_reasoner"


def route_after_contradiction_check(state: ClinicalAgentState) -> PostContradictionRoute:
    if state.get("intent") == "general_question":
        return "answer_generator"
    return "risk_flagger"


def _vector_retrieval_update(
    state: ClinicalAgentState,
    services: ClinicalReasoningGraphServices,
) -> dict:
    next_state = retrieve_vector_context_node(
        state=state,
        similarity_search=services.similarity_search,
        limit=services.retrieval_limit,
    )
    update = {"vector_context": next_state.get("vector_context", [])}
    if next_state.get("errors", []) != state.get("errors", []):
        update["errors"] = next_state.get("errors", [])
    return update


def _graph_retrieval_update(
    state: ClinicalAgentState,
    services: ClinicalReasoningGraphServices,
) -> dict:
    next_state = retrieve_graph_context_node(
        state=state,
        graph_query=services.graph_query,
        limit=services.retrieval_limit,
    )
    update = {"graph_context": next_state.get("graph_context", [])}
    if next_state.get("errors", []) != state.get("errors", []):
        update["errors"] = next_state.get("errors", [])
    return update


def _pass_through_node(state: ClinicalAgentState) -> dict:
    return {}
