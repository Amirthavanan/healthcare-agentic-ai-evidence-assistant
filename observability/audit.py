import json, os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = Path(os.getenv("AUDIT_LOG_PATH", str(ROOT / "audit.jsonl")))

def write_audit_event(state: dict) -> None:
    # By design, do not write the question or patient context to the audit log.
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case_id": state.get("case_id"),
        "trace_id": state.get("trace_id"),
        "case_status": state.get("case_status"),
        "workflow_steps": state.get("workflow_steps", []),
        "source_ids": [x.get("source_id") for x in state.get("evidence", [])],
        "validation_passed": state.get("validation", {}).get("passed", False),
    }
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
