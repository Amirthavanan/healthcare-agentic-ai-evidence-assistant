"""LangGraph workflow node definitions connecting all specialized agents, validators, and audit trackers."""
import json
import time
from typing import Any, TypedDict
from uuid import uuid4

from agents.evidence_quality_agent import EvidenceQualityAgent
from agents.intake_agent import IntakeScopeAgent
from agents.patient_context_agent import PatientContextAgent
from agents.retrieval_agent import EvidenceRetrievalAgent
from agents.safety_agent import SafetyPolicyAgent
from agents.schemas import (
    IntakeInput,
    PatientContextInput,
    PatientContextResult,
    RetrievedPassage,
    SummaryDraftResult,
)
from agents.summary_agent import SummaryAgent
from observability.audit import write_audit_event
from retrieval.hybrid import REGISTRY_PATH, retriever
from validators.output_validator import OutputValidator


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

    # Enhanced Typed Agent State Attributes
    intake_result: dict[str, Any]
    context_result: dict[str, Any]
    retrieval_result: dict[str, Any]
    evidence_quality_result: dict[str, Any]
    safety_result: dict[str, Any]
    summary_result: dict[str, Any]
    validation_result: dict[str, Any]
    agent_events: list[dict[str, Any]]
    error_events: list[dict[str, Any]]
    workflow_status: str
    repair_attempts: int
    needs_repair: bool
    clarification_prompt: str | None
    safe_next_step: str | None


# Module-level agent instances
intake_agent = IntakeScopeAgent()
context_agent = PatientContextAgent()
retrieval_agent = EvidenceRetrievalAgent(retriever)
evidence_quality_agent = EvidenceQualityAgent()
safety_agent = SafetyPolicyAgent()
summary_agent = SummaryAgent()
output_validator = OutputValidator()


def _record_event(
    state: WorkflowState,
    node_name: str,
    event_type: str,
    status: str,
    duration: float,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Record an authentic, non-simulated node execution event into workflow state."""
    state.setdefault("agent_events", []).append({
        "node_name": node_name,
        "event_type": event_type,
        "status": status,
        "timestamp": time.time(),
        "duration_seconds": round(duration, 4),
        "error_code": error_code,
        "details": details or {},
    })


def intake_node(state: WorkflowState) -> WorkflowState:
    """Classify the user's clinical request and verify prototype scope boundaries."""
    t0 = time.perf_counter()
    state["trace_id"] = state.get("trace_id") or str(uuid4())
    state["workflow_status"] = "in_progress"
    state.setdefault("workflow_steps", []).append("intake_scope")
    state.setdefault("retry_count", 0)
    state.setdefault("repair_attempts", 0)
    state["needs_retry"] = False
    state["needs_repair"] = False

    inp = IntakeInput(
        case_id=state.get("case_id", "UNKNOWN"),
        question=state.get("question", ""),
    )
    res = intake_agent.execute(inp)

    state["intake_result"] = res.model_dump()
    state["request_type"] = res.request_type
    state["scope_status"] = res.scope_status
    state["clarification_prompt"] = res.clarification_prompt
    state["query_intent"] = res.request_type

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="intake_node",
        event_type="scope_classification",
        status="success",
        duration=duration,
        details={"scope_status": res.scope_status, "request_type": res.request_type},
    )
    return state


def patient_context_node(state: WorkflowState) -> WorkflowState:
    """Analyze provided synthetic context and detect missing critical clinical parameters."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("patient_context")

    ctx = state.get("patient_context", {})
    inp = PatientContextInput(
        documented_facts=ctx.get("documented_facts", []),
        medications=ctx.get("medications"),
        allergies=ctx.get("allergies"),
        vital_signs=ctx.get("vital_signs"),
        symptom_duration=ctx.get("symptom_duration"),
    )
    res = context_agent.execute(inp)

    state["context_result"] = res.model_dump()
    state["record_facts"] = res.documented_facts
    state["missing_information"] = res.missing_information

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="patient_context_node",
        event_type="fact_extraction",
        status="success",
        duration=duration,
        details={"facts_count": len(res.documented_facts), "missing_count": len(res.missing_information)},
    )
    return state


def retrieval_node(state: WorkflowState) -> WorkflowState:
    """Execute hybrid retrieval over the registered source guidelines."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("evidence_retrieval")

    query = state.get("question", "")
    facts = state.get("record_facts", [])

    res = retrieval_agent.execute(query=query, patient_facts=facts, top_k=5)
    state["retrieval_result"] = res.model_dump()

    # Maintain backward compatibility with existing evidence list format
    evidence_list = []
    for p in res.passages:
        evidence_list.append({
            "source_id": p.source_id,
            "id": p.source_id,
            "title": p.document_title,
            "publisher": p.publisher,
            "version": p.version,
            "effective_date": p.effective_date or p.publication_date or "2021-01-01",
            "review_status": p.review_status,
            "section": p.section,
            "page": p.page_number,
            "excerpt": p.excerpt,
            "score": p.retrieval_score,
            "sparse_score": p.sparse_score,
            "dense_score": p.dense_score,
        })
    state["evidence"] = evidence_list

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="retrieval_node",
        event_type="hybrid_retrieval",
        status="success",
        duration=duration,
        details={"retrieved_count": len(evidence_list), "top_score": res.top_score},
    )
    return state


def evidence_quality_node(state: WorkflowState) -> WorkflowState:
    """Evaluate evidence coverage, score confidence, authority, freshness, and conflicts."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("evidence_quality")

    # Load registry metadata if available
    registry_data = []
    if REGISTRY_PATH.is_file():
        try:
            registry_data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            registry_data = []

    retrieved_passages = [
        RetrievedPassage(
            source_id=e["source_id"],
            document_title=e["title"],
            publisher=e["publisher"],
            version=e["version"],
            effective_date=e.get("effective_date"),
            page_number=e.get("page"),
            section=e.get("section", "General"),
            excerpt=e.get("excerpt", ""),
            retrieval_score=e.get("score", 0.0),
            review_status=e.get("review_status", "approved"),
        )
        for e in state.get("evidence", [])
    ]

    orig_query = state.get("intake_result", {}).get("normalized_question") or state.get("question", "")
    res = evidence_quality_agent.execute(
        retrieved_passages,
        known_sources_registry=registry_data,
        query=orig_query,
    )
    state["evidence_quality_result"] = res.model_dump()

    # Filter state["evidence"] strictly to accepted passages
    state["evidence"] = [
        {
            "source_id": p.source_id,
            "id": p.source_id,
            "title": p.document_title,
            "publisher": p.publisher,
            "version": p.version,
            "effective_date": p.effective_date or "2021-01-01",
            "review_status": p.review_status,
            "section": p.section,
            "page": p.page_number,
            "excerpt": p.excerpt,
            "score": p.retrieval_score,
            "sparse_score": p.sparse_score,
            "dense_score": p.dense_score,
        }
        for p in res.accepted_evidence
    ]

    conflicts = [c.description for c in res.conflicting_claims]
    state["conflicts"] = conflicts

    limitations = [
        "Educational prototype only; not a diagnosis or treatment plan.",
        "Included source collection contains illustrative demo documents, not authoritative clinical guidance.",
    ]
    if res.freshness_warnings:
        limitations.extend(res.freshness_warnings)
    if not res.accepted_evidence:
        limitations.append("No relevant source was retrieved; substantive evidence claims are unsupported.")

    state["limitations"] = limitations

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="evidence_quality_node",
        event_type="quality_assessment",
        status="success",
        duration=duration,
        details={"quality_status": res.evidence_quality_status, "accepted_count": len(res.accepted_evidence)},
    )
    return state


def gap_detection_node(state: WorkflowState) -> WorkflowState:
    """Identify if evidence coverage is insufficient and trigger a single bounded retry if needed."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("gap_detection")

    evidence = state.get("evidence", [])
    retry_count = state.get("retry_count", 0)

    # Check for empty results or low score (< 0.40) with single retry budget
    if (not evidence or max((x.get("score", 0) for x in evidence), default=0) < 0.40) and retry_count < 1:
        state["needs_retry"] = True
        state["retry_count"] = retry_count + 1
        state["question"] = f"{state.get('question', '')} patient safety guidelines"
    else:
        state["needs_retry"] = False

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="gap_detection_node",
        event_type="gap_analysis",
        status="retry_requested" if state["needs_retry"] else "complete",
        duration=duration,
        details={"retry_count": state["retry_count"], "needs_retry": state["needs_retry"]},
    )
    return state


def safety_node(state: WorkflowState) -> WorkflowState:
    """Evaluate clinical escalation triggers, prompt injection, and set review status."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("safety_policy")

    # Reconstruct schemas
    from agents.schemas import IntakeResult, EvidenceQualityResult

    intake_res = IntakeResult(**state.get("intake_result", {
        "request_type": state.get("request_type", "clinical_evidence_summary"),
        "normalized_question": state.get("question", ""),
        "scope_status": state.get("scope_status", "within_prototype_scope"),
    }))
    ctx_res = PatientContextResult(**state.get("context_result", {
        "documented_facts": state.get("record_facts", []),
        "missing_information": state.get("missing_information", []),
    }))
    qual_res = EvidenceQualityResult(**state.get("evidence_quality_result", {
        "evidence_quality_status": "insufficient" if not state.get("evidence") else "acceptable",
        "accepted_evidence": [],
    }))

    raw_excerpts = [e.get("excerpt", "") for e in state.get("evidence", [])]
    res = safety_agent.execute(intake_res, ctx_res, qual_res, retrieved_raw_texts=raw_excerpts)

    state["safety_result"] = res.model_dump()
    state["escalation_reason"] = res.escalation_reason
    state["safe_next_step"] = res.safe_next_step
    state["case_status"] = res.safety_status

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="safety_node",
        event_type="safety_evaluation",
        status="success",
        duration=duration,
        details={"safety_status": res.safety_status, "review_required": res.review_required},
    )
    return state


def summary_node(state: WorkflowState) -> WorkflowState:
    """Generate structured, evidence-grounded answer and key findings with citations via Groq/Extractive."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("summary_draft")

    from agents.schemas import EvidenceQualityResult, SafetyResult

    ctx_res = PatientContextResult(**state.get("context_result", {
        "documented_facts": state.get("record_facts", []),
        "missing_information": state.get("missing_information", []),
    }))
    qual_res = EvidenceQualityResult(**state.get("evidence_quality_result", {
        "evidence_quality_status": "insufficient" if not state.get("evidence") else "acceptable",
        "accepted_evidence": [
            RetrievedPassage(
                source_id=e["source_id"],
                document_title=e["title"],
                version=e["version"],
                section=e.get("section", "General"),
                page_number=e.get("page"),
                excerpt=e.get("excerpt", ""),
                retrieval_score=e.get("score", 0.0),
            )
            for e in state.get("evidence", [])
        ],
    }))
    safety_res = SafetyResult(**state.get("safety_result", {
        "safety_status": state.get("case_status", "human_review_required"),
        "escalation_reason": state.get("escalation_reason"),
    }))

    question = state.get("question", "")
    summary_res = summary_agent.execute(
        question=question,
        context_result=ctx_res,
        quality_result=qual_res,
        safety_result=safety_res,
    )

    state["summary_result"] = summary_res.model_dump()
    state["direct_answer"] = summary_res.direct_answer
    state["key_findings"] = summary_res.key_findings
    state["evidence_summary"] = [c.model_dump() for c in summary_res.evidence_summary]
    state["citations"] = [c.model_dump() for c in summary_res.citations]
    if summary_res.limitations:
        existing_lims = state.get("limitations", [])
        state["limitations"] = list(dict.fromkeys(existing_lims + summary_res.limitations))

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="summary_node",
        event_type="summary_generation",
        status="success",
        duration=duration,
        details={"mode": summary_res.generation_mode, "citations_count": len(summary_res.citations)},
    )
    return state


def validation_node(state: WorkflowState) -> WorkflowState:
    """Validate that all claims have verified citations in retrieved evidence and required schemas."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("output_validation")

    res = output_validator.validate(dict(state), max_repairs=1)
    state["validation_result"] = res.model_dump()
    state["validation"] = {
        "passed": res.passed,
        "errors": res.error_codes,
        "citation_ids_checked": res.citation_ids_checked,
    }

    if not res.passed:
        state["case_status"] = "human_review_required"
        curr_reason = state.get("escalation_reason") or ""
        state["escalation_reason"] = f"{curr_reason} Output validation failed: {','.join(res.error_codes)}".strip()
        state["needs_repair"] = res.can_retry
    else:
        state["needs_repair"] = False

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="validation_node",
        event_type="output_validation",
        status="passed" if res.passed else "failed",
        duration=duration,
        error_code=res.error_codes[0] if res.error_codes else None,
        details={"error_codes": res.error_codes, "can_retry": res.can_retry},
    )
    return state


def repair_node(state: WorkflowState) -> WorkflowState:
    """Execute a single bounded repair step to clean ungrounded claims or formatting errors."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("validation_repair")
    state["repair_attempts"] = state.get("repair_attempts", 0) + 1
    state["needs_repair"] = False

    # Filter out unsupported citations from evidence_summary
    valid_source_ids = {x.get("source_id") or x.get("id") for x in state.get("evidence", [])}
    cleaned_summary = [
        c for c in state.get("evidence_summary", [])
        if c.get("source_id") in valid_source_ids or c.get("source_id") == "NONE"
    ]
    state["evidence_summary"] = cleaned_summary

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="repair_node",
        event_type="bounded_repair",
        status="repaired",
        duration=duration,
        details={"repair_attempt": state["repair_attempts"]},
    )
    return state


def audit_node(state: WorkflowState) -> WorkflowState:
    """Terminal node writing full audit trace and setting final workflow completion status."""
    t0 = time.perf_counter()
    state.setdefault("workflow_steps", []).append("audit_logging")
    state["workflow_status"] = "completed"

    write_audit_event(dict(state))

    duration = time.perf_counter() - t0
    _record_event(
        state,
        node_name="audit_node",
        event_type="audit_log_persisted",
        status="success",
        duration=duration,
    )
    return state
