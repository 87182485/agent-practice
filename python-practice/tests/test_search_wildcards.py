# tests/test_search_wildcards.py
import pytest
from uuid import uuid4

def make(client, headers, title):
    url = f"https://example.com/{uuid4().hex}"
    r = client.post("/bookmarks", json={"title": title, "url": url}, headers=headers)
    assert r.status_code == 201, r.text


def titles(client, headers, q):
    r = client.get("/bookmarks", params={"q": q}, headers=headers)
    assert r.status_code == 200
    return sorted(b["title"] for b in r.json()["data"])


@pytest.mark.parametrize("target, decoy, q", [
    ("snake_case tips", "snakeXcase tips", "snake_case"),
    ("100% coverage",   "100 coverage",    "100%"),
])
def test_like_wildcards_are_literal(client, auth_headers, target, decoy, q):
    headers = auth_headers("alice")
    make(client, headers, target)
    make(client, headers, decoy)
    assert titles(client, headers, q) == [target]


def test_backslash_is_literal(client, auth_headers):
    headers = auth_headers("alice")
    make(client, headers, r"path a\b")
    assert titles(client, headers, "a\\b") == [r"path a\b"]