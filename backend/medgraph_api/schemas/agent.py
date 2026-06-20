from typing import Any

from pydantic import BaseModel, Field


class PatientAgentQueryCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2_000)


class PatientAgentQueryRead(BaseModel):
    answer: str
    intent: str | None
    timeline: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    risk_flags: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    confidence: str | None = None
    limitations: list[str] = Field(default_factory=list)
