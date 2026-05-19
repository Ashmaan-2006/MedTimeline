from medgraph_api.db.base import Base


def test_initial_database_models_are_registered() -> None:
    assert set(Base.metadata.tables) == {"documents", "patients", "timeline_events"}

