from pathlib import Path


AGENT_TEST_MODULES = {
    "test_intent_classifier.py",
    "test_evidence_planner.py",
    "test_vector_retriever.py",
    "test_graph_retriever.py",
    "test_timeline_reasoner.py",
    "test_contradiction_checker.py",
    "test_risk_flagger.py",
    "test_answer_generator.py",
    "test_clinical_reasoning_graph.py",
    "test_agent_api.py",
    "test_agent_run_repository.py",
}


def test_clinical_agent_workflow_has_expected_test_modules() -> None:
    test_dir = Path(__file__).parent
    existing_modules = {path.name for path in test_dir.glob("test_*.py")}

    assert AGENT_TEST_MODULES.issubset(existing_modules)
