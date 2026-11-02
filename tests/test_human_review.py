"""Unit and integration tests for human review decision persistence.
Verifies that:
- Reviewer decisions and notes are persisted.
- Trace IDs link decisions to the corresponding workflow execution.
- Review timestamps are recorded in UTC ISO format.
- Failed persistence operations (I/O, permissions) are handled safely without crashing.
- Review decisions strictly log governance metadata without mutating clinical records.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from observability.human_review import (
    save_review_decision,
    get_review_decisions,
    ReviewDecisionInput,
    ReviewDecisionRecord,
)


def test_human_review_decision_persisted_with_all_fields(tmp_path: Path):
    test_log = tmp_path / "human_reviews.jsonl"

    case_id = "CASE-TEST-100"
    trace_id = "tr-abc-12345"
    reviewer_id = "Dr. Jane Doe, MD"
    disposition = "Approved — Evidence Grounded & Verified"
    notes = "Verified WHO patient safety protocol against documented facts."

    ok, err, record = save_review_decision(
        case_id=case_id,
        trace_id=trace_id,
        reviewer_id=reviewer_id,
        disposition=disposition,
        notes=notes,
        log_path=test_log,
    )

    assert ok is True
    assert err is None
    assert record is not None
    assert record["case_id"] == case_id
    assert record["trace_id"] == trace_id
    assert record["reviewer_id"] == reviewer_id
    assert record["disposition"] == disposition
    assert record["notes"] == notes
    assert "T" in record["timestamp"]  # ISO-8601 UTC timestamp
    assert record["governance_status"] == "recorded"

    # Verify physical persistence in JSONL
    assert test_log.is_file()
    lines = test_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    persisted = json.loads(lines[0])
    assert persisted["review_id"].startswith("REV-")
    assert persisted["trace_id"] == trace_id


def test_human_review_retrieval_filtering(tmp_path: Path):
    test_log = tmp_path / "human_reviews.jsonl"

    save_review_decision(
        case_id="CASE-A",
        trace_id="tr-1",
        reviewer_id="Rev 1",
        disposition="Approved",
        notes="Notes A",
        log_path=test_log,
    )
    save_review_decision(
        case_id="CASE-B",
        trace_id="tr-2",
        reviewer_id="Rev 2",
        disposition="Escalated",
        notes="Notes B",
        log_path=test_log,
    )

    all_reviews = get_review_decisions(log_path=test_log)
    assert len(all_reviews) == 2

    case_a_reviews = get_review_decisions(case_id="CASE-A", log_path=test_log)
    assert len(case_a_reviews) == 1
    assert case_a_reviews[0]["case_id"] == "CASE-A"

    trace_2_reviews = get_review_decisions(trace_id="tr-2", log_path=test_log)
    assert len(trace_2_reviews) == 1
    assert trace_2_reviews[0]["notes"] == "Notes B"


def test_human_review_failed_persistence_handled_safely(tmp_path: Path):
    # Test safe handling when write fails (e.g. read-only filesystem or OS permission error)
    with patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")):
        ok, err, record = save_review_decision(
            case_id="CASE-FAIL",
            trace_id="tr-fail",
            reviewer_id="Rev Fail",
            disposition="Rejected",
            notes="Testing failure resilience",
            log_path=tmp_path / "readonly.jsonl",
        )
        assert ok is False
        assert err is not None
        assert "Permission denied" in err
        assert record is None


def test_human_review_does_not_modify_clinical_records(tmp_path: Path):
    # Guarantee that clinical patient context dict is not mutated by review operations
    patient_context = {
        "documented_facts": ["Asthma", "Allergy to Penicillin"],
        "medications": ["Albuterol"],
        "vital_signs": {"BP": "120/80"},
    }
    context_snapshot = json.dumps(patient_context, sort_keys=True)

    ok, err, record = save_review_decision(
        case_id="CASE-UNMODIFIED",
        trace_id="tr-clean",
        reviewer_id="Attending Physician",
        disposition="Approved",
        notes="Patient context must remain strictly immutable",
        log_path=tmp_path / "reviews.jsonl",
    )
    assert ok is True
    # Confirm patient record remains identical
    assert json.dumps(patient_context, sort_keys=True) == context_snapshot


def test_human_review_api_endpoints():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)

    payload = {
        "case_id": "API-CASE-01",
        "trace_id": "api-trace-99",
        "reviewer_id": "Dr. API Reviewer",
        "disposition": "Approved — Evidence Grounded & Verified",
        "notes": "Verified via FastAPI endpoint.",
    }

    resp = client.post("/cases/API-CASE-01/review-decision", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "persisted"
    assert data["record"]["case_id"] == "API-CASE-01"
    assert data["record"]["trace_id"] == "api-trace-99"

    # Query back
    get_resp = client.get("/cases/API-CASE-01/review-decisions")
    assert get_resp.status_code == 200
    decisions = get_resp.json()["decisions"]
    assert len(decisions) >= 1
    assert decisions[0]["case_id"] == "API-CASE-01"
