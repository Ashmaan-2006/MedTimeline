from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from medgraph_api.api.routes import agent
from medgraph_api.api.routes import documents
from medgraph_api.api.routes import graph
from medgraph_api.api.routes import patients
from medgraph_api.api.routes import rag
from medgraph_api.core.neo4j import close_neo4j_driver
from medgraph_api.db.init import initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    initialize_database()
    try:
        yield
    finally:
        close_neo4j_driver()


app = FastAPI(
    title="MedGraph AI API",
    description="Clinical timeline intelligence API for patient records.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(patients.router)
app.include_router(documents.router)
app.include_router(graph.router)
app.include_router(rag.router)
app.include_router(agent.router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
