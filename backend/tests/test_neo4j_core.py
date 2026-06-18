from types import SimpleNamespace

from medgraph_api.core import neo4j


class FakeResult:
    def single(self) -> dict[str, int]:
        return {"ok": 1}


class FakeSession:
    def __init__(self) -> None:
        self.closed = False
        self.queries: list[str] = []

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def run(self, query: str) -> FakeResult:
        self.queries.append(query)
        return FakeResult()

    def close(self) -> None:
        self.closed = True


class FakeDriver:
    def __init__(self) -> None:
        self.closed = False
        self.last_session: FakeSession | None = None
        self.session_kwargs: dict | None = None

    def session(self, **kwargs) -> FakeSession:
        self.session_kwargs = kwargs
        self.last_session = FakeSession()
        return self.last_session

    def close(self) -> None:
        self.closed = True


def test_create_neo4j_driver_uses_configured_settings(monkeypatch) -> None:
    calls = []

    def fake_driver(uri, auth):
        calls.append((uri, auth))
        return "driver"

    monkeypatch.setattr(
        neo4j,
        "get_settings",
        lambda: SimpleNamespace(
            neo4j_uri="bolt://graph:7687",
            neo4j_username="neo4j",
            neo4j_password="secret",
        ),
    )
    monkeypatch.setattr(neo4j.GraphDatabase, "driver", fake_driver)

    assert neo4j.create_neo4j_driver() == "driver"
    assert calls == [("bolt://graph:7687", ("neo4j", "secret"))]


def test_check_neo4j_connection_runs_basic_query(monkeypatch) -> None:
    driver = FakeDriver()
    monkeypatch.setattr(neo4j, "get_neo4j_driver", lambda: driver)

    assert neo4j.check_neo4j_connection() is True
    assert driver.last_session is not None
    assert driver.last_session.queries == ["RETURN 1 AS ok"]
    assert driver.last_session.closed is True


def test_neo4j_session_closes_session(monkeypatch) -> None:
    driver = FakeDriver()
    monkeypatch.setattr(neo4j, "get_neo4j_driver", lambda: driver)

    with neo4j.neo4j_session(database="neo4j") as session:
        assert session is driver.last_session

    assert driver.last_session is not None
    assert driver.last_session.closed is True
    assert driver.session_kwargs == {"database": "neo4j"}


def test_close_neo4j_driver_closes_and_clears_cached_driver(monkeypatch) -> None:
    driver = FakeDriver()
    monkeypatch.setattr(neo4j, "_driver", driver)

    neo4j.close_neo4j_driver()

    assert driver.closed is True
    assert neo4j._driver is None
