from medgraph_api.db.base import Base
from medgraph_api.db.session import engine


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)

