
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.hybrid import HybridRetriever, retriever
from evaluation.metrics import (
    recall_at_k,
    precision_at_k,
    reciprocal_rank,
)
DATASET_PATH = ROOT / "evaluation" / "dataset.json"
REPORT_PATH = ROOT / "evaluation" / "latest_report.json"

K = 5


def source_id(result: dict) -> str:
    """Use the registry's ID, falling back to its filename."""
    value = result.get("id") or result.get("source_file") or result.get("file")

    if not value:
        raise ValueError(
            "Retrieved result has no id, source_file, or file field."
        )

    return str(value)


def main():
    dataset = json.loads(
        DATASET_PATH.read_text(encoding="utf-8")
    )

    if not dataset:
        raise ValueError("Evaluation dataset is empty.")

    retriever = HybridRetriever()
    reports = []

    for case in dataset:
        query = case["query"].strip()
        relevant = {
            str(item) for item in case["relevant_source_ids"]
        }

        if not query or not relevant:
            raise ValueError(
                f"Invalid evaluation case: {case.get('query_id')}"
            )

        results = retriever.search(query, top_k=K)
        ranked_ids = [source_id(item) for item in results]

        # Each source counts once, even if multiple chunks match.
        unique_ranked_ids = list(dict.fromkeys(ranked_ids))

        reports.append({
            "query_id": case["query_id"],
            "query": query,
            "relevant_source_ids": sorted(relevant),
            "retrieved_source_ids": unique_ranked_ids,
            "recall_at_k": round(
                recall_at_k(unique_ranked_ids, relevant, K), 4
            ),
            "precision_at_k": round(
                precision_at_k(unique_ranked_ids, relevant, K), 4
            ),
            "reciprocal_rank": round(
                reciprocal_rank(unique_ranked_ids, relevant), 4
            ),
            "relevant_source_found": bool(
                set(unique_ranked_ids) & relevant
            ),
        })

    summary = {
        "k": K,
        "query_count": len(reports),
        "mean_recall_at_k": round(
            sum(r["recall_at_k"] for r in reports) / len(reports), 4
        ),
        "mean_precision_at_k": round(
            sum(r["precision_at_k"] for r in reports) / len(reports), 4
        ),
        "mean_reciprocal_rank": round(
            sum(r["reciprocal_rank"] for r in reports) / len(reports), 4
        ),
        "failed_queries": [
            r["query_id"]
            for r in reports
            if not r["relevant_source_found"]
        ],
        "results": reports,
    }

    REPORT_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2))
    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
