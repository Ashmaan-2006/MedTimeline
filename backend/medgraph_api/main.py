from fastapi import FastAPI

app = FastAPI(
    title="MedGraph AI API",
    description="Clinical timeline intelligence API for patient records.",
    version="0.1.0",
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}

