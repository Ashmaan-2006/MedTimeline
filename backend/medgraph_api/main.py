from fastapi import FastAPI

from medgraph_api.api.routes import documents
from medgraph_api.api.routes import patients

app = FastAPI(
    title="MedGraph AI API",
    description="Clinical timeline intelligence API for patient records.",
    version="0.1.0",
)

app.include_router(patients.router)
app.include_router(documents.router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
