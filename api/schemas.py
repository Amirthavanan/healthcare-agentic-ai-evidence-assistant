from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class PatientContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documented_facts: list[str] = Field(default_factory=list, max_length=100)
    medications: list[str] | None = None
    allergies: list[str] | None = None
    vital_signs: dict[str, Any] | None = None
    symptom_duration: str | None = None


class CaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=3, max_length=5000)
    patient_context: PatientContext = Field(default_factory=PatientContext)


class EvidenceItem(BaseModel):
    source_id: str
    title: str
    publisher: str
    version: str
    effective_date: str
    section: str
    excerpt: str
    score: float
    page: int | None = None
    review_status: str | None = None


class ReviewResponse(BaseModel):
    case_id: str
    trace_id: str
    case_status: str
    request_type: str
    record_facts: list[str]
    missing_information: list[str]
    evidence_summary: list[dict[str, Any]]
    evidence: list[EvidenceItem]
    conflicts: list[str]
    limitations: list[str]
    escalation_reason: str | None
    validation: dict[str, Any]
    workflow_steps: list[str]
    direct_answer: str | None = None
    key_findings: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)


class SearchQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResultItem(BaseModel):
    source_id: str
    title: str
    section: str
    page: int | None = None
    score: float
    sparse_score: float | None = None
    dense_score: float | None = None
    excerpt: str


class SearchResponse(BaseModel):
    query: str
    top_k: int
    result_count: int
    results: list[SearchResultItem]


class SourceItem(BaseModel):
    id: str
    file: str
    title: str
    publisher: str
    version: str
    effective_date: str
    review_status: str
    description: str | None = None
