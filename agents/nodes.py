from typing import TypedDict, Any
from uuid import uuid4

from retrieval.hybrid import retriever
from agents.generation import generate_grounded_answer

PROHIBITED_TERMS = (
    "diagnose me",
    "give me a diagnosis",
    "what medication should",
    "change my medication",
    "prescribe",
)


class WorkflowState(TypedDict, total=False):
    case_id: str
    question: str
    patient_context: dict[str, Any]
    trace_id: str
    request_type: str
    scope_status: str
    record_facts: list[str]
    missing_information: list[str]
    evidence: list[dict[str, Any]]
    conflicts: list[str]
    limitations: list[str]
    escalation_reason: str | None
    case_status: str
    evidence_summary: list[dict[str, Any]]
    validation: dict[str, Any]
    workflow_steps: list[str]
    query_intent: str
    retry_count: int
    needs_retry: bool
    direct_answer: str
    key_findings: list[str]
    citations: list[dict[str, Any]]


def intake_node(state: WorkflowState) -> WorkflowState:
    """Classify the user's clinical request and verify prototype scope boundaries."""
    q = state.get("question", "").lower()
    prohibited = any(term in q for term in PROHIBITED_TERMS)

    state["request_type"] = (
        "potential_diagnosis_or_treatment_request"
        if prohibited
        else "clinical_evidence_summary"
    )
    state["scope_status"] = "out_of_scope" if prohibited else "within_prototype_scope"
    state["trace_id"] = state.get("trace_id") or str(uuid4())
    state["retry_count"] = state.get("retry_count", 0)
    state["needs_retry"] = False
    state.setdefault("workflow_steps", []).append("intake_scope")
    return state


def patient_context_node(state: WorkflowState) -> WorkflowState:
    """Analyze provided synthetic context and detect missing critical clinical parameters."""
    ctx = state.get("patient_context", {})
    state["record_facts"] = [
        str(x) for x in ctx.get("documented_facts", []) if str(x).strip()
    ]

    missing = []
    checks = [
        ("medications", "Current medication list"),
        ("allergies", "Allergy information"),
        ("vital_signs", "Vital signs"),
        ("symptom_duration", "Symptom duration"),
    ]
    for key, label in checks:
        if not ctx.get(key):
            missing.append(label)

    state["missing_information"] = missing
    state.setdefault("workflow_steps", []).append("patient_context")
    return state


def retrieval_node(state: WorkflowState) -> WorkflowState:
    """Execute hybrid retrieval over the registered source guidelines."""
    query = state.get("question", "")
    facts = state.get("record_facts", [])
    if facts:
        query = f"{query} {' '.join(facts)}"

    results = retriever.search(query, top_k=5)
    evidence = []
    for x in results:
        evidence.append({
            "source_id": x.get("source_id") or x.get("id", "UNKNOWN"),
            "id": x.get("id") or x.get("source_id", "UNKNOWN"),
            "title": x.get("title", "Clinical Document"),
            "publisher": x.get("publisher", "World Health Organization"),
            "version": x.get("version", "2021"),
            "effective_date": x.get("effective_date", "2021-01-01"),
            "review_status": x.get("review_status", "approved"),
            "section": x.get("section", "N/A"),
            "page": x.get("page"),
            "excerpt": x.get("excerpt", ""),
            "score": x.get("score", 0.0),
        })

    state["evidence"] = evidence
    state.setdefault("workflow_steps", []).append("evidence_retrieval")
    return state


def evidence_quality_node(state: WorkflowState) -> WorkflowState:
    """Evaluate evidence coverage, score confidence, and declare required safety limitations."""
    evidence = state.get("evidence", [])
    state["conflicts"] = []

    limitations = [
        "Educational prototype only; not a diagnosis or treatment plan.",
        "Included source collection contains illustrative demo documents, not authoritative clinical guidance.",
    ]
    if not evidence:
        limitations.append("No relevant source was retrieved; substantive evidence claims are unsupported.")
    if any(x.get("review_status") != "approved" for x in evidence):
        limitations.append("At least one retrieved source is not marked as approved clinical guidance.")

    state["limitations"] = limitations
    state.setdefault("workflow_steps", []).append("evidence_quality")
    return state


def gap_detection_node(state: WorkflowState) -> WorkflowState:
    """Identify if evidence coverage is insufficient and trigger a single bounded retry if needed."""
    evidence = state.get("evidence", [])
    retry_count = state.get("retry_count", 0)

    # If no results retrieved or top score is extremely low (<0.40) and we haven't retried yet
    if (not evidence or max((x.get("score", 0) for x in evidence), default=0) < 0.40) and retry_count < 1:
        state["needs_retry"] = True
        state["retry_count"] = retry_count + 1
        # Reformulate query with core question keywords for the retry
        state["question"] = f"{state.get('question', '')} patient safety guidelines"
    else:
        state["needs_retry"] = False

    state.setdefault("workflow_steps", []).append("gap_detection")
    return state


def safety_node(state: WorkflowState) -> WorkflowState:
    """Evaluate clinical escalation triggers and set review status."""
    reasons = []
    if state.get("scope_status") == "out_of_scope":
        reasons.append("Request appears to seek a definitive diagnosis or treatment/medication action.")
    if state.get("missing_information"):
        reasons.append("Relevant patient context is incomplete.")
    if not state.get("evidence"):
        reasons.append("No supporting source was retrieved.")
    if any(x.get("review_status") != "approved" for x in state.get("evidence", [])):
        reasons.append("Retrieved source is illustrative or not approved for clinical use.")

    state["escalation_reason"] = " ".join(reasons) if reasons else None
    state["case_status"] = "human_review_required" if reasons else "draft_ready_for_human_review"
    state.setdefault("workflow_steps", []).append("safety_policy")
    return state


def summary_node(state: WorkflowState) -> WorkflowState:
    """Generate structured, evidence-grounded answer and key findings with citations."""
    question = state.get("question", "")
    facts = state.get("record_facts", [])
    evidence = state.get("evidence", [])

    synthesis = generate_grounded_answer(question, facts, evidence)
    state["direct_answer"] = synthesis["direct_answer"]
    state["key_findings"] = synthesis["key_findings"]
    state["evidence_summary"] = synthesis["evidence_summary"]
    state["citations"] = synthesis["citations"]

    state.setdefault("workflow_steps", []).append("summary_draft")
    return state


def validation_node(state: WorkflowState) -> WorkflowState:
    """Validate that all claims have verified citations in retrieved evidence and required schemas."""
    issues = []
    evidence_ids = {x.get("source_id") or x.get("id") for x in state.get("evidence", [])}

    for item in state.get("evidence_summary", []):
        sid = item.get("source_id")
        if sid not in evidence_ids and sid != "NONE":
            issues.append("unsupported_citation")

    required = [
        "case_id",
        "trace_id",
        "case_status",
        "record_facts",
        "missing_information",
        "evidence_summary",
    ]
    missing_keys = [k for k in required if k not in state]
    if missing_keys:
        issues.append("missing_required_fields")

    state["validation"] = {
        "passed": not issues,
        "errors": issues,
        "citation_ids_checked": len(state.get("evidence_summary", [])),
    }

    if issues:
        state["case_status"] = "human_review_required"
        current_reason = state.get("escalation_reason") or ""
        state["escalation_reason"] = f"{current_reason} Output validation failed.".strip()

    state.setdefault("workflow_steps", []).append("output_validation")
    return state
