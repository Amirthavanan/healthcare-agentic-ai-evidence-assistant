"""Persistent governance audit trail for clinician review decisions.
Enforces that reviewer decisions, dispositions, notes, and trace IDs are persisted
without modifying or mutating any patient clinical records.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("healthcare_agentic_ai.human_review")

ROOT = Path(__file__).resolve().parents[1]
HUMAN_REVIEW_PATH = Path(os.getenv("HUMAN_REVIEW_LOG_PATH", str(ROOT / "data" / "human_reviews.jsonl")))


class ReviewDecisionInput(BaseModel):
    case_id: str = Field(description="Unique identifier for the patient case")
    trace_id: str = Field(description="Workflow execution trace identifier linking the review to the agent run")
    reviewer_id: str = Field(description="Clinician name, NPI, or reviewer identifier")
    disposition: str = Field(description="Clinical decision: APPROVED, ESCALATED, CLARIFICATION_REQUIRED, REJECTED")
    notes: str = Field(description="Reviewer rationale, verification observations, or clinical notes")


class ReviewDecisionRecord(BaseModel):
    review_id: str
    case_id: str
    trace_id: str
    reviewer_id: str
    disposition: str
    notes: str
    timestamp: str
    governance_status: str = "recorded"


def save_review_decision(
    case_id: str,
    trace_id: str,
    reviewer_id: str,
    disposition: str,
    notes: str,
    log_path: Optional[Path] = None,
) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
    """Persist clinician human-review decision, notes, timestamp, and trace ID.
    
    Guarantees:
    - Review decisions strictly log governance metadata; NEVER modify clinical records.
    - Persistence failures (I/O errors, permissions) are safely caught and handled.
    - All entries include UTC ISO timestamps and trace link.
    """
    try:
        target_path = log_path or HUMAN_REVIEW_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)

        now_utc = datetime.now(timezone.utc).isoformat()
        review_id = f"REV-{uuid.uuid4().hex[:8].upper()}"

        record = ReviewDecisionRecord(
            review_id=review_id,
            case_id=case_id.strip(),
            trace_id=trace_id.strip(),
            reviewer_id=reviewer_id.strip(),
            disposition=disposition.strip(),
            notes=notes.strip(),
            timestamp=now_utc,
            governance_status="recorded",
        )

        with target_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")

        return True, None, record.model_dump()
    except Exception as exc:
        logger.error("Failed to persist human review decision for case %s: %s", case_id, exc)
        return False, str(exc), None


def get_review_decisions(
    case_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    log_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Retrieve persisted human review decisions, optionally filtered by case or trace."""
    target_path = log_path or HUMAN_REVIEW_PATH
    if not target_path.is_file():
        return []

    results: list[dict[str, Any]] = []
    try:
        lines = target_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if case_id and data.get("case_id") != case_id:
                    continue
                if trace_id and data.get("trace_id") != trace_id:
                    continue
                results.append(data)
            except Exception:
                continue
        return results
    except Exception as exc:
        logger.error("Failed to read human review decisions: %s", exc)
        return []
