"""Unit tests for the 12-rule deterministic output validator."""
import pytest
from validators.output_validator import OutputValidator


@pytest.fixture
def valid_state():
    return {
        "case_id": "SYN-001",
        "trace_id": "trace-1234",
        "case_status": "human_review_required",
        "scope_status": "within_prototype_scope",
        "record_facts": ["Asthma documented in record"],
        "missing_information": ["Current medication list"],
        "direct_answer": "According to WHO guidance, medication safety requires verification.",
        "citations": [
            {
                "source_id": "who_global_patient_safety_001",
                "title": "Global Patient Safety Action Plan",
                "section": "Strategic Objective 1",
                "page": 12,
            }
        ],
        "evidence_summary": [
            {
                "claim": "Safety guidelines emphasize medication reconciliation.",
                "source_id": "who_global_patient_safety_001",
                "section": "Strategic Objective 1",
                "page": 12,
            }
        ],
        "evidence": [
            {
                "source_id": "who_global_patient_safety_001",
                "page_number": 12,
                "excerpt": "Safety guidelines emphasize medication reconciliation.",
            }
        ],
        "conflicts": [],
        "escalation_reason": "Context incomplete: Current medication list.",
        "retry_count": 0,
    }


def test_validator_passes_valid_state(valid_state):
    validator = OutputValidator()
    res = validator.validate(valid_state)
    assert res.passed is True
    assert len(res.error_codes) == 0
    assert len(res.rules_checked) == 12


def test_validator_rejects_missing_required_fields(valid_state):
    del valid_state["case_id"]
    validator = OutputValidator()
    res = validator.validate(valid_state)
    assert res.passed is False
    assert any("MISSING_REQUIRED_FIELDS" in err for err in res.error_codes)


def test_validator_rejects_unsupported_citation(valid_state):
    # Scenario T12: Fabricated citation ID not in retrieved evidence
    valid_state["evidence_summary"][0]["source_id"] = "FABRICATED_GUIDELINE_999"
    valid_state["citations"][0]["source_id"] = "FABRICATED_GUIDELINE_999"
    validator = OutputValidator()
    res = validator.validate(valid_state)
    assert res.passed is False
    assert any("INVALID_SOURCE_ID" in err or "UNSUPPORTED_CLAIM_SOURCE" in err for err in res.error_codes)


def test_validator_rejects_prohibited_prescribing_language(valid_state):
    valid_state["direct_answer"] = "I diagnose you with bronchitis. Take 500mg of amoxicillin daily."
    validator = OutputValidator()
    res = validator.validate(valid_state)
    assert res.passed is False
    assert "PROHIBITED_DIAGNOSIS_OR_PRESCRIBING_OUTPUT" in res.error_codes


def test_validator_enforces_human_review_for_conflicts(valid_state):
    valid_state["conflicts"] = ["Source A contradicts Source B"]
    valid_state["case_status"] = "draft_ready"  # Inconsistent!
    validator = OutputValidator()
    res = validator.validate(valid_state)
    assert res.passed is False
    assert "UNRESOLVED_CONFLICT_WITHOUT_HUMAN_REVIEW" in res.error_codes
