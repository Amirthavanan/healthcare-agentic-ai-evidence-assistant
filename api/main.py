import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    CaseRequest,
    LLMHealthResponse,
    ReviewResponse,
    SearchQueryRequest,
    SearchResponse,
    SearchResultItem,
    SourceItem,
)
from orchestration.graph import workflow
from observability.audit import write_audit_event
from observability.human_review import (
    ReviewDecisionInput,
    save_review_decision,
    get_review_decisions,
)
from retrieval.hybrid import retriever, REGISTRY_PATH
from llm.factory import get_llm_provider

logger = logging.getLogger("healthcare_agentic_ai.api")

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "evaluation" / "latest_report.json"

app = FastAPI(
    title=os.getenv("APP_NAME", "Healthcare Agentic AI Evidence Assistant"),
    version="1.0.0",
    description=(
        "Educational and clinical review prototype grounded in WHO Patient Safety "
        "and Medication Safety guidelines. Not for clinical decisions or medical treatment."
    ),
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check declaring educational prototype boundaries and provider status."""
    try:
        llm = get_llm_provider()
        llm_status = llm.health_check()
        llm_available = llm_status.available
        llm_code = llm_status.status_code
    except Exception:
        llm_available = False
        llm_code = "UNAVAILABLE"

    return {
        "status": "ok",
        "app_name": "Healthcare Agentic AI Evidence Assistant",
        "mode": "educational_prototype",
        "clinical_use": False,
        "indexed_chunks": len(retriever.chunks),
        "llm_available": llm_available,
        "llm_status": llm_code,
    }


@app.get("/llm/health", response_model=LLMHealthResponse)
def check_llm_health():
    """Verify GroqCloud LLM provider connectivity without exposing credentials."""
    llm = get_llm_provider()
    status = llm.health_check()
    return LLMHealthResponse(
        provider=status.provider,
        model=status.model,
        configured=status.configured,
        available=status.available,
        status_code=status.status_code,
        message=status.message,
    )


@app.get("/sources", response_model=list[SourceItem])
def list_sources():
    """Return all registered healthcare guidelines and policy documents."""
    if not REGISTRY_PATH.is_file():
        raise HTTPException(status_code=500, detail="Source registry is not available.")
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        return data
    except Exception as exc:
        logger.error("Failed to read registry: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load document sources.")


@app.post("/retrieval/search", response_model=SearchResponse)
def search_documents(request: SearchQueryRequest):
    """Diagnostic endpoint to perform direct hybrid search over indexed guidelines."""
    try:
        results = retriever.search(
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score,
        )
        items = [
            SearchResultItem(
                source_id=r.get("source_id") or r.get("id", "UNKNOWN"),
                title=r.get("title", ""),
                section=r.get("section", ""),
                page=r.get("page"),
                score=r.get("score", 0.0),
                sparse_score=r.get("sparse_score"),
                dense_score=r.get("dense_score"),
                excerpt=r.get("excerpt", ""),
            )
            for r in results
        ]
        return SearchResponse(
            query=request.query,
            top_k=request.top_k,
            result_count=len(items),
            results=items,
        )
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        raise HTTPException(status_code=500, detail="Search failed safely.")


@app.post("/cases/review", response_model=ReviewResponse)
def review_case(request: CaseRequest):
    """Execute the full agentic clinical evidence and safety workflow."""
    try:
        initial = {
            "case_id": request.case_id,
            "question": request.question,
            "patient_context": request.patient_context.model_dump(),
            "workflow_steps": [],
            "retry_count": 0,
        }
        result = workflow.invoke(initial, config={"recursion_limit": 20})
        write_audit_event(result)

        return ReviewResponse(
            case_id=result["case_id"],
            trace_id=result["trace_id"],
            case_status=result["case_status"],
            request_type=result["request_type"],
            record_facts=result.get("record_facts", []),
            missing_information=result.get("missing_information", []),
            evidence_summary=result.get("evidence_summary", []),
            evidence=result.get("evidence", []),
            conflicts=result.get("conflicts", []),
            limitations=result.get("limitations", []),
            escalation_reason=result.get("escalation_reason"),
            validation=result.get("validation", {}),
            workflow_steps=result.get("workflow_steps", []),
            direct_answer=result.get("direct_answer"),
            key_findings=result.get("key_findings", []),
            citations=result.get("citations", []),
            agent_events=result.get("agent_events", []),
            clarification_prompt=result.get("clarification_prompt"),
            safe_next_step=result.get("safe_next_step"),
            llm_generation_mode=result.get("summary_result", {}).get("generation_mode"),
            model_name=result.get("summary_result", {}).get("model_name"),
        )
    except Exception as exc:
        logger.error("Workflow execution failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Workflow failed safely. Check server logs using the trace context.",
        ) from exc


@app.get("/evaluation/latest")
def get_latest_evaluation():
    """Retrieve the latest automated retrieval evaluation benchmark report."""
    if not REPORT_PATH.is_file():
        raise HTTPException(status_code=404, detail="No evaluation report has been generated yet.")
    try:
        return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to load evaluation report: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load evaluation report.")


@app.get("/evaluation/comprehensive")
def get_comprehensive_evaluation():
    """Retrieve the latest comprehensive multi-dimensional benchmark report."""
    comp_path = ROOT / "evaluation" / "comprehensive_report.json"
    if not comp_path.is_file():
        raise HTTPException(status_code=404, detail="Comprehensive report has not been generated yet.")
    try:
        return json.loads(comp_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to load comprehensive report: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load comprehensive evaluation report.")


@app.get("/evaluation/scenarios")
def get_scenario_evaluation():
    """Retrieve the latest 12 mandatory clinical scenario test execution report."""
    scen_path = ROOT / "evaluation" / "scenario_report.json"
    if not scen_path.is_file():
        raise HTTPException(status_code=404, detail="Scenario report has not been generated yet.")
    try:
        return json.loads(scen_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to load scenario report: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load scenario test report.")


@app.post("/cases/{case_id}/review-decision")
def record_case_review_decision(case_id: str, decision: ReviewDecisionInput):
    """Persist clinician human-review decision, notes, timestamp, and trace ID.
    
    Guarantees:
    - Never mutates or writes to EHR or patient medical records.
    - Captures trace ID linking to the specific agent workflow execution.
    - Safely catches and handles any persistence failure.
    """
    if decision.case_id != case_id:
        raise HTTPException(status_code=400, detail="Path case_id does not match payload case_id.")

    success, err_msg, record = save_review_decision(
        case_id=decision.case_id,
        trace_id=decision.trace_id,
        reviewer_id=decision.reviewer_id,
        disposition=decision.disposition,
        notes=decision.notes,
    )
    if not success:
        logger.error("Review decision persistence failed: %s", err_msg)
        raise HTTPException(status_code=500, detail=f"Failed to persist review decision: {err_msg}")

    return {"status": "persisted", "record": record}


@app.get("/cases/{case_id}/review-decisions")
def list_case_review_decisions(case_id: str):
    """Retrieve all persisted human review decisions for a specific patient case."""
    records = get_review_decisions(case_id=case_id)
    return {"case_id": case_id, "decisions": records}


@app.get("/reviews/decisions")
def list_all_review_decisions():
    """Retrieve all persisted clinical review decisions across all cases."""
    records = get_review_decisions()
    return {"total": len(records), "decisions": records}
