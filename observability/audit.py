"""Structured audit logging and observability for Healthcare Agentic AI.
Preserves audit traces, latency, model usage, and safety decisions while enforcing data minimization.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("healthcare_agentic_ai.observability")

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = Path(os.getenv("AUDIT_LOG_PATH", str(ROOT / "audit.jsonl")))
MAX_AUDIT_LINES = int(os.getenv("MAX_AUDIT_LINES", "1000"))


def write_audit_event(state: dict[str, Any]) -> None:
    """Write an authentic case execution audit event with node traces and model usage.
    
    Data Minimization Policy:
    - Never log raw API credentials or tokens.
    - Never log raw narrative patient text or sensitive identifiers in audit trails.
    - Record only counts, validated source IDs, safety codes, and timing.
    """
    try:
        now_utc = datetime.now(timezone.utc).isoformat()
        
        # Extract model usage if available
        summary_res = state.get("summary_result") or {}
        model_name = summary_res.get("model_name") or state.get("model_name")
        token_usage = summary_res.get("token_usage") or state.get("token_usage")

        # Collect source IDs
        source_ids = []
        for x in state.get("evidence", []):
            sid = x.get("source_id") or x.get("id")
            if sid and sid not in source_ids:
                source_ids.append(sid)

        # Calculate overall workflow latency from agent_events if present
        agent_events = state.get("agent_events", [])
        total_duration = sum(e.get("duration_seconds", 0.0) for e in agent_events)

        event = {
            "timestamp": now_utc,
            "case_id": state.get("case_id", "UNKNOWN"),
            "trace_id": state.get("trace_id", "UNKNOWN"),
            "workflow_status": state.get("workflow_status", "completed"),
            "case_status": state.get("case_status", "unknown"),
            "request_type": state.get("request_type", "unknown"),
            "workflow_steps": state.get("workflow_steps", []),
            "node_events_count": len(agent_events),
            "agent_events": agent_events,
            "source_ids": source_ids,
            "validation_passed": state.get("validation", {}).get("passed", False),
            "validation_errors": state.get("validation", {}).get("errors", []),
            "retry_count": state.get("retry_count", 0),
            "repair_attempts": state.get("repair_attempts", 0),
            "total_duration_seconds": round(total_duration, 4),
            "model_name": model_name,
            "token_usage": token_usage,
        }

        # Write to JSONL file
        with AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    except Exception as exc:
        logger.error("Failed to write audit event: %s", exc)


def get_recent_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve the most recent audit events for UI dashboard inspection."""
    if not AUDIT_PATH.is_file():
        return []
    try:
        lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()
        recent_lines = lines[-limit:]
        events = []
        for line in reversed(recent_lines):
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue
        return events
    except Exception as exc:
        logger.error("Failed to read audit events: %s", exc)
        return []
