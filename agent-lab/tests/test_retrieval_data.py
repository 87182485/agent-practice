# tests/test_retrieval_data.py
import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "retrieval"
CORPUS = json.loads((DATA / "corpus.json").read_text())
QUERIES = json.loads((DATA / "queries.json").read_text())
CATEGORIES = {"lexical", "paraphrase", "distractor"}


def test_corpus_keys_unique():
    keys = [b["key"] for b in CORPUS]
    assert len(keys) == len(set(keys))


def test_query_ids_unique():
    ids = [q["id"] for q in QUERIES]
    assert len(ids) == len(set(ids))


def test_every_query_has_relevant():
    assert all(q["relevant"] for q in QUERIES)


def test_relevant_keys_exist_and_belong_to_query_user():
    by_key = {b["key"]: b for b in CORPUS}
    for q in QUERIES:
        for key in q["relevant"]:
            assert key in by_key, f"{q['id']}: unknown key {key}"
            assert by_key[key]["owner"] == q["user"], f"{q['id']}: {key} not owned by {q['user']}"


def test_categories_valid():
    assert {q["category"] for q in QUERIES} <= CATEGORIES