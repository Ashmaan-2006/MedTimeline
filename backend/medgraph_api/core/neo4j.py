from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from neo4j import Driver, GraphDatabase, Session

from medgraph_api.core.config import get_settings

_driver: Driver | None = None


def create_neo4j_driver() -> Driver:
    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )


def get_neo4j_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = create_neo4j_driver()
    return _driver


def check_neo4j_connection() -> bool:
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run("RETURN 1 AS ok")
        record = result.single()
        return record is not None and record["ok"] == 1


@contextmanager
def neo4j_session(**kwargs: Any) -> Iterator[Session]:
    session = get_neo4j_driver().session(**kwargs)
    try:
        yield session
    finally:
        session.close()


def close_neo4j_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
