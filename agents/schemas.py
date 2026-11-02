"""Typed input and output contracts for all specialized agents."""
from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


# Agent 1: Intake & Scope
class IntakeInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    case_id: str
    question: str


class IntakeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    request_type: str = Field(description="Classification of user intent (e.g. clinical_evidence_summary, diagnosis_request, prescribing_request)")
    normalized_question: str = Field(description="Normalized, sanitized form of the clinical query")
    scope_status: Literal["within_prototype_scope", "out_of_scope"] = Field(description="Whether the request is within educational decision-support scope")
    required_fields: list[str] = Field(default_factory=list, description="Fields required for complete evaluation")
    missing_fields: list[str] = Field(default_factory=list, description="Fields absent in the input")
    clarification_prompt: str | None = Field(default=None, description="Prompt if clarification is required from clinician")
    reason_codes: list[str] = Field(default_factory=list, description="Diagnostic reason codes explaining scope determination")


# Agent 2: Patient Context
class FactProvenance(BaseModel):
    model_config = ConfigDict(extra="ignore")
    field: str
    value: str
    source_location: str = "supplied_user_record"


class PatientContextInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    documented_facts: list[str] = Field(default_factory=list)
    medications: list[str] | None = None
    allergies: list[str] | None = None
    vital_signs: dict[str, Any] | None = None
    symptom_duration: str | None = None


class PatientContextResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    documented_facts: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    relevant_history: list[str] = Field(default_factory=list)
    vital_signs: dict[str, Any] = Field(default_factory=dict)
    symptom_duration: str | None = None
    fact_provenance: list[FactProvenance] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    extraction_warnings: list[str] = Field(default_factory=list)


# Agent 3: Evidence Retrieval
class RetrievedPassage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_id: str
    document_title: str
    publisher: str = "World Health Organization"
    version: str = "2021"
    publication_date: str | None = None
    effective_date: str | None = None
    page_number: int | None = None
    section: str = "General"
    excerpt: str
    retrieval_score: float = 0.0
    sparse_score: float | None = None
    dense_score: float | None = None
    review_status: str = "approved"


class RetrievalAgentResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    query_used: str
    passages: list[RetrievedPassage] = Field(default_factory=list)
    total_retrieved: int = 0
    top_score: float = 0.0
    no_results_found: bool = False


# Agent 4: Evidence Quality
class ConflictingClaim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_a_id: str
    source_b_id: str
    description: str
    recommendation: str


class EvidenceQualityResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    evidence_quality_status: Literal["acceptable", "mixed", "insufficient", "conflicting"] = "acceptable"
    accepted_evidence: list[RetrievedPassage] = Field(default_factory=list)
    rejected_evidence: list[dict[str, Any]] = Field(default_factory=list)
    duplicate_sources: list[str] = Field(default_factory=list)
    conflicting_claims: list[ConflictingClaim] = Field(default_factory=list)
    freshness_warnings: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    quality_reasons: list[str] = Field(default_factory=list)


# Agent 5: Safety & Policy
class SafetyResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    safety_status: Literal["safe", "human_review_required", "prohibited_blocked"] = "safe"
    review_required: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    escalation_reason: str | None = None
    safe_next_step: str = "Proceed with clinician review of evidence summary."
    policy_violations: list[str] = Field(default_factory=list)
    prompt_injection_detected: bool = False
    sensitive_data_flagged: bool = False


# Agent 6: Summary Agent
class CitationReference(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_id: str
    title: str
    section: str = "General"
    page: int | None = None
    version: str = "2021"


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claim: str
    source_id: str
    section: str = "General"
    page: int | None = None
    source_version: str = "2021"


class SummaryDraftResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    direct_answer: str = Field(description="Evidence-grounded concise clinician summary")
    key_findings: list[str] = Field(default_factory=list, description="Salient evidence points with source attribution")
    evidence_summary: list[EvidenceClaim] = Field(default_factory=list, description="Claim-level evidence mapping")
    citations: list[CitationReference] = Field(default_factory=list, description="List of referenced sources")
    limitations: list[str] = Field(default_factory=list, description="Explicit boundaries and prototype disclaimers")
    uncertainty_notes: list[str] = Field(default_factory=list, description="Areas of incomplete context or low evidence confidence")
    missing_information: list[str] = Field(default_factory=list, description="Patient parameters not supplied")
    human_review_recommendation: str = Field(description="Recommendation for clinical escalation or human oversight")
    generation_mode: str = Field(default="groq_llm_structured", description="Mode of summary synthesis")
    model_name: str | None = None
    token_usage: dict[str, int] | None = None
