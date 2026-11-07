# tests/test_retrieval_runner.py
from retrieval.data import Query
from retrieval.runner import Row, evaluate, summarize


class FakeRetriever:
    """Returns a fixed ranking per query and records every call."""

    def __init__(self, results: dict[str, list[str]]):
        self.name = "fake"
        self.results = results  # query text -> ranked keys
        self.calls: list[tuple[str, str, int]] = []

    def search(self, user, query, limit):
        self.calls.append((user, query, limit))
        return self.results[query][:limit]


QUERIES = [
    Query(id="q1", user="alice", category="lexical", query="index",
          relevant=frozenset({"a"})),
    Query(id="q2", user="alice", category="paraphrase", query="slow db",
          relevant=frozenset({"a", "b"})),
]

FAKE = {"index": ["a", "x", "y"], "slow db": ["x", "a", "b"]}


def test_searches_once_per_query_with_max_k():
    r = FakeRetriever(FAKE)
    evaluate(r, QUERIES, ks=(1, 3))
    assert r.calls == [("alice", "index", 3), ("alice", "slow db", 3)]


def test_one_row_per_query_and_k():
    rows = evaluate(FakeRetriever(FAKE), QUERIES, ks=(1, 3))
    assert len(rows) == 4


def test_recall_values():
    rows = evaluate(FakeRetriever(FAKE), QUERIES, ks=(1, 3))
    got = {(row.query_id, row.k): row.recall for row in rows}
    assert got == {("q1", 1): 1.0, ("q1", 3): 1.0,
                   ("q2", 1): 0.0, ("q2", 3): 1.0}


def test_recall_never_decreases_with_k():
    rows = evaluate(FakeRetriever(FAKE), QUERIES, ks=(1, 2, 3))
    for qid in ("q1", "q2"):
        scores = [row.recall for row in sorted(rows, key=lambda r: r.k) if row.query_id == qid]
        assert scores == sorted(scores)


def test_summarize_means_per_retriever_category_k():
    rows = [
        Row("B0", "q1", "lexical", 1, 1.0),
        Row("B0", "q2", "lexical", 1, 0.0),
        Row("B0", "q3", "paraphrase", 1, 0.5),
    ]
    assert summarize(rows) == {("B0", "lexical", 1): 0.5,
                               ("B0", "paraphrase", 1): 0.5}


def test_summarize_omits_empty_groups():
    # no distractor rows -> no distractor key (absent, not 0.0)
    rows = [Row("B0", "q1", "lexical", 1, 1.0)]
    assert ("B0", "distractor", 1) not in summarize(rows)