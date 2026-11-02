
import pytest

from evaluation.metrics import (
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
    mean_reciprocal_rank,
)


def test_recall_at_k():
    assert recall_at_k(
        ["A", "B", "C"],
        {"A", "C", "D"},
        k=2,
    ) == pytest.approx(1 / 3)


def test_precision_at_k():
    assert precision_at_k(
        ["A", "B", "C"],
        {"A", "C"},
        k=2,
    ) == pytest.approx(0.5)


def test_reciprocal_rank():
    assert reciprocal_rank(
        ["X", "B", "A"],
        {"A", "B"},
    ) == pytest.approx(0.5)


def test_no_relevant_result():
    assert reciprocal_rank(
        ["X", "Y"],
        {"A"},
    ) == 0.0


def test_mean_reciprocal_rank():
    assert mean_reciprocal_rank(
        [["A", "B"], ["X", "B"]],
        [{"A"}, {"B"}],
    ) == pytest.approx(0.75)


def test_invalid_k():
    with pytest.raises(ValueError):
        precision_at_k(["A"], {"A"}, k=0)


def test_ndcg_at_k_perfect_ranking():
    from evaluation.metrics import ndcg_at_k
    assert ndcg_at_k(["A", "B", "C"], {"A"}, k=3) == pytest.approx(1.0)


def test_ndcg_at_k_bounded_with_duplicate_retrieved_passages():
    from evaluation.metrics import ndcg_at_k
    # Multiple chunks of the same relevant document must not exceed 1.0
    score = ndcg_at_k(["A", "A", "A", "B"], {"A"}, k=3)
    assert 0.0 <= score <= 1.0
    assert score == pytest.approx(1.0)


def test_claim_grounding_evaluator_verbatim_support():
    from evaluation.claim_grounding import ClaimGroundingEvaluator
    evaluator = ClaimGroundingEvaluator()

    passages = [{
        "source_id": "who_gpsap_001",
        "excerpt": "Medication errors are a leading cause of avoidable harm in healthcare systems worldwide.",
        "page": 12,
    }]
    claims = [{
        "claim_id": "CLM-001",
        "claim": "Medication errors are a leading cause of avoidable harm in healthcare systems worldwide.",
        "source_id": "who_gpsap_001",
        "page_number": 12,
    }]

    summary = evaluator.evaluate_claims(claims, passages)
    assert summary.total_claims == 1
    assert summary.supported_count == 1
    assert summary.records[0].grounding_status == "supported"
    assert summary.records[0].evaluation_method == "deterministic_verbatim"
    assert summary.records[0].overlap_score == 1.0


def test_claim_grounding_evaluator_rejects_hallucination_despite_valid_citation():
    from evaluation.claim_grounding import ClaimGroundingEvaluator
    evaluator = ClaimGroundingEvaluator()

    passages = [{
        "source_id": "who_gpsap_001",
        "excerpt": "Global patient safety action plan establishes strategic objectives for reporting adverse incidents.",
        "page": 5,
    }]
    # Fabricated medical prescription claim citing legitimate source ID
    claims = [{
        "claim_id": "CLM-002",
        "claim": "Prescribe 500mg amoxicillin capsule orally three times daily for bacterial infection.",
        "source_id": "who_gpsap_001",
        "page_number": 5,
    }]

    summary = evaluator.evaluate_claims(claims, passages)
    assert summary.total_claims == 1
    # Must NOT be supported despite valid source_id!
    assert summary.supported_count == 0
    assert summary.unsupported_count == 1
    assert summary.records[0].grounding_status == "unsupported"
    assert summary.records[0].overlap_score < 0.35


def test_claim_grounding_evaluator_unmatched_source_id():
    from evaluation.claim_grounding import ClaimGroundingEvaluator
    evaluator = ClaimGroundingEvaluator()

    passages = [{
        "source_id": "who_gpsap_001",
        "excerpt": "Guidelines for patient safety.",
    }]
    claims = [{
        "claim_id": "CLM-003",
        "claim": "Important clinical finding.",
        "source_id": "FABRICATED_SOURCE_999",
    }]

    summary = evaluator.evaluate_claims(claims, passages)
    assert summary.records[0].grounding_status == "unsupported"
    assert summary.records[0].evaluation_method == "unmatched_source"


def test_claim_grounding_evaluator_lexical_containment():
    from evaluation.claim_grounding import ClaimGroundingEvaluator
    evaluator = ClaimGroundingEvaluator()

    passages = [{
        "source_id": "who_gpsap_001",
        "excerpt": "Establishing national reporting and learning systems is critical for preventing adverse drug events.",
        "page": 8,
    }]
    # Paraphrased claim with substantial content-word overlap
    claims = [{
        "claim_id": "CLM-004",
        "claim": "National reporting and learning systems prevent adverse drug events effectively.",
        "source_id": "who_gpsap_001",
        "page_number": 8,
    }]

    summary = evaluator.evaluate_claims(claims, passages)
    assert summary.total_claims == 1
    assert summary.supported_count == 1
    assert summary.records[0].grounding_status == "supported"
    assert summary.records[0].evaluation_method == "deterministic_lexical_containment"


def test_claim_grounding_evaluator_semantic_llm_mocked():
    from unittest.mock import MagicMock
    from evaluation.claim_grounding import ClaimGroundingEvaluator, SemanticGroundingVerdict

    mock_llm = MagicMock()
    mock_verdict = SemanticGroundingVerdict(
        grounding_status="supported",
        rationale="Evidence passage entails clinical claim via synonymy.",
    )
    mock_llm.generate_structured.return_value = (mock_verdict, MagicMock())

    evaluator = ClaimGroundingEvaluator(llm_provider=mock_llm)

    passages = [{
        "source_id": "who_gpsap_001",
        "excerpt": "High-risk medications require strict double-checking before administration.",
        "page": 15,
    }]
    claims = [{
        "claim_id": "CLM-005",
        "claim": "Healthcare personnel must conduct redundant verification on high-alert drugs.",
        "source_id": "who_gpsap_001",
        "page_number": 15,
    }]

    summary = evaluator.evaluate_claims(claims, passages, use_semantic_evaluator=True)
    assert summary.total_claims == 1
    assert summary.supported_count == 1
    assert summary.records[0].grounding_status == "supported"
    assert summary.records[0].evaluation_method == "semantic_llm_entailment"
    assert "not clinically validated" in summary.records[0].details["disclaimer"].lower()


