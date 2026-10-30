
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

    return sum(
        item in relevant_ids for item in retrieved
    ) / k


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
        raise ValueError(
            "Each ranking must have a corresponding relevant set."
        )

    if not rankings:
        return 0.0

    scores = [
        reciprocal_rank(ranking, relevant)
        for ranking, relevant in zip(rankings, relevant_sets)
    ]

    return sum(scores) / len(scores)
