from sqlalchemy import text

from medgraph_api.db.base import Base
from medgraph_api.db.session import engine


def initialize_database() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
