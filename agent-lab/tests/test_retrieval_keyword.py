# tests/test_retrieval_keyword.py
from retrieval.retrievers import KeywordRetriever

CORPUS = [
    {"key": "a1", "owner": "alice", "title": "Postgres index guide", "notes": "B-tree basics"},
    {"key": "a2", "owner": "alice", "title": "Sourdough starter", "notes": "feed daily; Postgres not involved"},
    {"key": "a3", "owner": "alice", "title": "Postgres EXPLAIN", "notes": None},
    {"key": "b1", "owner": "bob",   "title": "Postgres index guide", "notes": "B-tree basics"},
]


def title_only():
    return KeywordRetriever(CORPUS, fields=("title",), name="B0")


def title_and_notes():
    return KeywordRetriever(CORPUS, fields=("title", "notes"), name="B1")


def test_never_returns_other_users_bookmarks():
    assert "b1" not in title_only().search("alice", "Postgres", limit=10)


def test_title_only_ignores_notes():
    assert title_only().search("alice", "Postgres", limit=10) == ["a1", "a3"]


def test_title_and_notes_matches_notes():
    assert title_and_notes().search("alice", "Postgres", limit=10) == ["a1", "a2", "a3"]


def test_missing_notes_does_not_crash():
    # a3 has notes=None; B1 must still work
    assert "a3" in title_and_notes().search("alice", "EXPLAIN", limit=10)


def test_limit_respected():
    assert len(title_and_notes().search("alice", "Postgres", limit=2)) == 2


def test_no_match_returns_empty():
    assert title_only().search("alice", "kubernetes", limit=10) == []