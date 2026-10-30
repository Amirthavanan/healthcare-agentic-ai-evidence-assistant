from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["clinical_use"] is False
    assert data["status"] == "ok"
    assert data["indexed_chunks"] > 0


def test_sources_endpoint():
    response = client.get("/sources")
    assert response.status_code == 200
    sources = response.json()
    assert isinstance(sources, list)
    assert len(sources) >= 4
    source_ids = [s["id"] for s in sources]
    assert "who_global_patient_safety_001" in source_ids
    assert "who_five_moments_medication_002" in source_ids
    assert "who_global_patient_safety_003" in source_ids
    assert "who_medication_without_harm_004" in source_ids


def test_retrieval_search_endpoint():
    response = client.post(
        "/retrieval/search",
        json={"query": "patient safety harm", "top_k": 3, "min_score": 0.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result_count"] <= 3
    assert len(data["results"]) > 0
    assert "source_id" in data["results"][0]
    assert "score" in data["results"][0]


def test_retrieval_search_empty_query():
    response = client.post(
        "/retrieval/search",
        json={"query": "", "top_k": 3},
    )
    # Pydantic validates min_length=1
    assert response.status_code == 422


def test_evaluation_latest_endpoint():
    response = client.get("/evaluation/latest")
    assert response.status_code == 200
    report = response.json()
    assert "mean_recall_at_k" in report
    assert "mean_reciprocal_rank" in report
    assert "results" in report


def test_case_review_endpoint():
    response = client.post(
        "/cases/review",
        json={
            "case_id": "SYN-API-001",
            "question": "Prepare a clinical evidence summary for clinician review.",
            "patient_context": {
                "documented_facts": ["Cough reported"],
                "medications": None,
                "allergies": None,
                "vital_signs": None,
                "symptom_duration": None,
            },
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["case_status"] == "human_review_required"
    assert data["trace_id"]
    assert data["validation"]["passed"] is True
    assert "evidence" in data
    assert len(data["evidence"]) > 0
