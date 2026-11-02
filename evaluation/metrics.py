"""Comprehensive evaluation metrics for Retrieval, Grounding, Citations, Safety, Extraction, Reliability, and Efficiency."""
import math
from typing import Any


def recall_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int = 5,
) -> float:
    if not relevant_ids:
        return 0.0
    retrieved = set(retrieved_ids[:k])
    return len(retrieved & relevant_ids) / len(relevant_ids)


def precision_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int = 5,
) -> float:
    if k < 1:
        raise ValueError("k must be >= 1")
    retrieved = retrieved_ids[:k]
    if len(retrieved) < k:
        retrieved = retrieved + [None] * (k - len(retrieved))
    return sum(item in relevant_ids for item in retrieved) / k


def reciprocal_rank(
    retrieved_ids: list[str],
    relevant_ids: set[str],
) -> float:
    for rank, source_id in enumerate(retrieved_ids, start=1):
        if source_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(
    rankings: list[list[str]],
    relevant_sets: list[set[str]],
) -> float:
    if len(rankings) != len(relevant_sets):
        raise ValueError("Each ranking must have a corresponding relevant set.")
    if not rankings:
        return 0.0
    scores = [
        reciprocal_rank(ranking, relevant)
        for ranking, relevant in zip(rankings, relevant_sets)
    ]
    return sum(scores) / len(scores)


def ndcg_at_k(
    retrieved_ids: list[str],
    relevant_ids: set[str],
    k: int = 5,
) -> float:
    """Normalized Discounted Cumulative Gain at rank K.
    
    In standard Information Retrieval with binary document relevance, each relevant document
    can only be credited once. Duplicate passages from an already credited document provide
    no additional gain, ensuring 0.0 <= NDCG <= 1.0.
    """
    if not relevant_ids or k < 1:
        return 0.0
    retrieved = retrieved_ids[:k]
    dcg = 0.0
    seen_relevant = set()
    for idx, sid in enumerate(retrieved, start=1):
        if sid in relevant_ids and sid not in seen_relevant:
            dcg += 1.0 / math.log2(idx + 1)
            seen_relevant.add(sid)

    # Ideal DCG: best possible ranking where relevant documents appear first
    idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, min(len(relevant_ids), k) + 1))
    return dcg / idcg if idcg > 0 else 0.0


def compute_grounding_metrics(evidence_summaries: list[dict[str, Any]], retrieved_source_ids: set[str]) -> dict[str, float]:
    """Calculate grounded claim support rate and unsupported claim rate."""
    if not evidence_summaries:
        return {"claim_support_rate": 1.0, "unsupported_claim_rate": 0.0}
    supported = sum(
        1 for c in evidence_summaries
        if c.get("source_id") in retrieved_source_ids or c.get("source_id") == "NONE"
    )
    total = len(evidence_summaries)
    return {
        "claim_support_rate": round(supported / total, 4) if total else 1.0,
        "unsupported_claim_rate": round((total - supported) / total, 4) if total else 0.0,
    }


def compute_citation_metrics(citations: list[dict[str, Any]], retrieved_source_ids: set[str]) -> dict[str, Any]:
    """Calculate citation validity and passage presence."""
    if not citations:
        return {"citation_count": 0, "valid_citation_rate": 1.0}
    valid = sum(1 for c in citations if c.get("source_id") in retrieved_source_ids or c.get("source_id") == "NONE")
    return {
        "citation_count": len(citations),
        "valid_citation_rate": round(valid / len(citations), 4),
    }


def compute_percentiles(latencies: list[float]) -> dict[str, float]:
    """Calculate P50 and P95 latency metrics."""
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0}
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    p50_idx = int(0.50 * n)
    p95_idx = min(int(0.95 * n), n - 1)
    return {
        "p50": round(sorted_lats[p50_idx], 4),
        "p95": round(sorted_lats[p95_idx], 4),
        "mean": round(sum(sorted_lats) / n, 4),
    }
