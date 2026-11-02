"""LangGraph Multi-Agent Orchestration Graph with bounded retries, repair loop, and terminal audit logging."""
from langgraph.graph import StateGraph, END
from agents.nodes import (
    WorkflowState,
    intake_node,
    patient_context_node,
    retrieval_node,
    evidence_quality_node,
    gap_detection_node,
    safety_node,
    summary_node,
    validation_node,
    repair_node,
    audit_node,
)


def route_after_intake(state: WorkflowState) -> str:
    """Route directly to safety evaluation if query is out-of-scope (diagnosis, prescribing, triage)."""
    if state.get("scope_status") == "out_of_scope":
        return "safety"
    return "patient_context"


def route_after_gap_detection(state: WorkflowState) -> str:
    """Conditionally route back for a bounded single retry if evidence coverage has a gap."""
    if state.get("needs_retry") and state.get("retry_count", 0) <= 1:
        return "retrieval"
    return "safety"


def route_after_validation(state: WorkflowState) -> str:
    """Conditionally route to repair node if validation failed and repair budget remains."""
    if state.get("needs_repair") and state.get("repair_attempts", 0) < 1:
        return "repair"
    return "audit"


def build_graph():
    """Build the compiled LangGraph multi-agent workflow with stateful routing and safety guardrails."""
    graph = StateGraph(WorkflowState)

    graph.add_node("intake", intake_node)
    graph.add_node("patient_context", patient_context_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("evidence_quality", evidence_quality_node)
    graph.add_node("gap_detection", gap_detection_node)
    graph.add_node("safety", safety_node)
    graph.add_node("summary", summary_node)
    graph.add_node("validation", validation_node)
    graph.add_node("repair", repair_node)
    graph.add_node("audit", audit_node)

    graph.set_entry_point("intake")

    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "safety": "safety",
            "patient_context": "patient_context",
        },
    )

    graph.add_edge("patient_context", "retrieval")
    graph.add_edge("retrieval", "evidence_quality")
    graph.add_edge("evidence_quality", "gap_detection")

    graph.add_conditional_edges(
        "gap_detection",
        route_after_gap_detection,
        {
            "retrieval": "retrieval",
            "safety": "safety",
        },
    )

    graph.add_edge("safety", "summary")
    graph.add_edge("summary", "validation")

    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "repair": "repair",
            "audit": "audit",
        },
    )

    graph.add_edge("repair", "validation")
    graph.add_edge("audit", END)

    return graph.compile()


workflow = build_graph()
