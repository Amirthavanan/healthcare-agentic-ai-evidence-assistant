from orchestration.graph import workflow


def run_case(question="Prepare an evidence summary for clinician review.", ctx=None):
    return workflow.invoke({
        "case_id": "TEST-001",
        "question": question,
        "patient_context": ctx
        or {
            "documented_facts": ["Cough is reported"],
            "medications": None,
            "allergies": None,
            "vital_signs": None,
            "symptom_duration": None,
        },
        "workflow_steps": [],
        "retry_count": 0,
    })


def test_missing_information_is_visible():
    result = run_case()
    assert "Current medication list" in result["missing_information"]
    assert "Vital signs" in result["missing_information"]
    assert result["case_status"] == "human_review_required"


def test_diagnosis_request_is_out_of_scope():
    result = run_case("Give me a diagnosis for this patient")
    assert result["scope_status"] == "out_of_scope"
    assert result["case_status"] == "human_review_required"


def test_output_validation_passes_for_basic_flow():
    result = run_case()
    assert result["validation"]["passed"] is True
    assert "output_validation" in result["workflow_steps"]


def test_sources_are_flagged_as_illustrative():
    result = run_case()
    assert any("illustrative" in item.lower() for item in result["limitations"])


def test_grounded_answer_and_citations_present():
    result = run_case("What are the five moments for medication safety?")
    assert result["direct_answer"]
    assert len(result["direct_answer"]) > 20
    assert len(result["evidence"]) > 0
    assert len(result["evidence_summary"]) > 0
    # Every evidence summary item must reference a valid source_id from retrieved evidence
    valid_ids = {e["source_id"] for e in result["evidence"]}
    for claim in result["evidence_summary"]:
        assert claim["source_id"] in valid_ids or claim["source_id"] == "NONE"


def test_gap_detection_workflow_step():
    result = run_case("What system and organizational factors can contribute to patient harm?")
    assert "gap_detection" in result["workflow_steps"]
    assert "intake_scope" in result["workflow_steps"]
    assert "evidence_retrieval" in result["workflow_steps"]
