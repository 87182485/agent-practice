# retrieval/runner.py
import json
from pathlib import Path

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from retrieval.data import Query, load_queries
from retrieval.metrics import recall_at_k
from retrieval.retrievers import KeywordRetriever, Retriever

DATA_DIR = Path(__file__).parent
KS = (1, 3, 5)


@dataclass(frozen=True)
class Row:
    retriever: str
    query_id: str
    category: str
    k: int
    recall: float


def evaluate(retriever: Retriever, queries: list[Query], ks: tuple[int, ...]) -> list[Row]:
    rows: list[Row] = []
    limit = max(ks)
    for q in queries:
        retrieved = retriever.search(q.user, q.query, limit)
        for k in ks:
            recall = recall_at_k(retrieved, q.relevant, k)
            rows.append(Row(retriever.name, q.id, q.category, k, recall))
    return rows


def summarize(rows: list[Row]) -> dict[tuple[str, str, int], float]:
    groups: defaultdict[tuple[str, str, int], list[float]] = defaultdict(list)
    for row in rows:
        key = (row.retriever, row.category, row.k)
        groups[key].append(row.recall)
    return {key: mean(values) for key, values in groups.items()}


def main() -> None:
    corpus = json.loads((DATA_DIR / "corpus.json").read_text())
    queries = load_queries(DATA_DIR / "queries.json")
    retrievers = [
        KeywordRetriever(corpus, ("title",), "B0"),
        KeywordRetriever(corpus, ("title", "notes"), "B1"),
    ]
    rows = []
    for r in retrievers:
        rows += evaluate(r, queries, KS)
    summary = summarize(rows)
    for (retriever, category, k), value in sorted(summary.items()):
        print(f"{retriever} {category} {k}: {value:.2f}")


if __name__ == "__main__":
    main()