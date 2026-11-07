# tests/test_retrieval_loader.py
import json

from retrieval.data import load_queries
from retrieval.metrics import recall_at_k


def test_relevant_becomes_a_set(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text(json.dumps([
        {"id": "q01", "user": "alice", "category": "paraphrase",
         "query": "speeding up database queries", "relevant": ["a", "b"]}
    ]))

    [q] = load_queries(path)

    assert q.relevant == {"a", "b"}
    # the integration point that would have raised TypeError with a list
    assert recall_at_k(["a"], q.relevant, k=1) == 0.5