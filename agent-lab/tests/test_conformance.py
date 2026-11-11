# tests/test_conformance.py
import json
import tempfile
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "eval.env")
from evals import BASE, REGISTER_PATH, fresh_api

from retrieval.data import load_queries
from retrieval.retrievers import KeywordRetriever

DATA = Path(__file__).parent.parent / "retrieval"
CORPUS = json.loads((DATA / "corpus.json").read_text())
QUERIES = load_queries(DATA / "queries.json")
LIMIT = 5
PASSWORD = "conformance-pw-123"

pytestmark = pytest.mark.integration   # slow: needs a real API; run with -m integration

@pytest.fixture
def api():
    with (
        tempfile.TemporaryDirectory() as tmp,
        fresh_api(Path(tmp)),
        httpx.Client(base_url=BASE, timeout=10) as client,
    ):
        yield client

def login(client: httpx.Client, username: str) -> dict[str, str]:
    client.post(REGISTER_PATH, json={"username": username, "password": PASSWORD}).raise_for_status()
    r = client.post("/token", data={"username": username, "password": PASSWORD})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_b0_matches_real_list_bookmarks(api):
    headers = {user: login(api, user) for user in ("alice", "bob")}
    id_to_key = {}
    for item in CORPUS:
        body = {"title": item["title"], "url": item['url']}
        if item["notes"] is not None:
            body["note"] = item["notes"]
        r = api.post("/bookmarks", json=body, headers=headers[item["owner"]])
        assert r.status_code == 201, (item["key"], r.text)
        id_to_key[r.json()["id"]] = item["key"]

    b0 = KeywordRetriever(CORPUS, ("title",), "B0")
    mismatches = []
    for q in QUERIES:
        r = api.get("/bookmarks", params={"q": q.query, "limit": LIMIT}, headers=headers[q.user])
        assert r.status_code == 200, (q.id, r.text)
        api_keys = [id_to_key[b["id"]] for b in r.json()["data"]]
        b0_keys = b0.search(q.user, q.query, LIMIT)
        if api_keys != b0_keys:
            mismatches.append((q.id, q.query, api_keys, b0_keys))
    assert mismatches == [], "\n".join(map(str, mismatches))