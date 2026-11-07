# retrieval/metrics.py


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant keys that appear in the top k retrieved keys."""
    if k <= 0:
        raise ValueError("k must be a positive integer")
    if not relevant:
        raise ValueError("relevant must be a non-empty set")
    top_k = retrieved[:k]
    relevant_in_top_k = len(set(top_k) & relevant)
    return relevant_in_top_k / len(relevant)