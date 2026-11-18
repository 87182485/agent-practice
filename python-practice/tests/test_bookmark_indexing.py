# tests/test_bookmark_indexing.py
import pytest
from app.vector_store import nearest
from models.bookmarks import Bookmark  # adjust to where Bookmark lives

BODY = {"title": "Use The Index", "url": "https://example.com/a", "note": "B-tree basics", "tags": []}


def create(client, headers, **overrides):
    r = client.post("/bookmarks", json={**BODY, **overrides}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def stored(session, bookmark_id) -> Bookmark:
    session.expire_all()                       # re-read from the DB, not a cached object
    return session.get(Bookmark, bookmark_id)


def test_create_indexes_bookmark(client, auth_headers, session, fake_embedder):
    bid = create(client, auth_headers("alice"))
    b = stored(session, bid)
    assert b.embedding_model == fake_embedder.model
    [(hit, dist)] = nearest(session, b.user_id, fake_embedder.vector_for(b.title, b.note), k=1)
    assert hit == bid and dist == pytest.approx(0.0, abs=1e-6)


def test_create_survives_embedding_failure(client, auth_headers, session, fake_embedder):
    fake_embedder.fail = True
    bid = create(client, auth_headers("alice"))            # still 201
    b = stored(session, bid)
    assert b.embedding_model is None
    assert nearest(session, b.user_id, fake_embedder.vector_for(b.title, b.note), k=5) == []


def test_put_title_change_reembeds(client, auth_headers, session, fake_embedder):
    h = auth_headers("alice")
    bid = create(client, h)
    r = client.put(f"/bookmarks/{bid}", json={**BODY, "title": "Postgres indexes"}, headers=h)
    assert r.status_code == 200, r.text
    b = stored(session, bid)
    [(hit, dist)] = nearest(session, b.user_id, fake_embedder.vector_for("Postgres indexes", b.note), k=1)
    assert hit == bid and dist == pytest.approx(0.0, abs=1e-6)


def test_patch_url_only_does_not_reembed(client, auth_headers, fake_embedder):
    h = auth_headers("alice")
    bid = create(client, h)
    calls_after_create = len(fake_embedder.calls)
    r = client.patch(f"/bookmarks/{bid}", json={"url": "https://example.com/b"}, headers=h)
    assert r.status_code == 200, r.text
    assert len(fake_embedder.calls) == calls_after_create


def test_failed_reembed_removes_stale_vector(client, auth_headers, session, fake_embedder):
    h = auth_headers("alice")
    bid = create(client, h)
    fake_embedder.fail = True
    r = client.patch(f"/bookmarks/{bid}", json={"title": "New title"}, headers=h)
    assert r.status_code == 200, r.text
    b = stored(session, bid)
    assert b.embedding_model is None
    assert nearest(session, b.user_id, fake_embedder.vector_for(BODY["title"], BODY["note"]), k=5) == []


def test_unindexed_bookmark_heals_on_any_edit(client, auth_headers, session, fake_embedder):
    h = auth_headers("alice")
    fake_embedder.fail = True
    bid = create(client, h)
    fake_embedder.fail = False
    client.patch(f"/bookmarks/{bid}", json={"url": "https://example.com/c"}, headers=h)
    assert stored(session, bid).embedding_model == fake_embedder.model


def test_delete_removes_vector(client, auth_headers, session, fake_embedder):
    h = auth_headers("alice")
    bid = create(client, h)
    user_id = stored(session, bid).user_id
    assert client.delete(f"/bookmarks/{bid}", headers=h).status_code == 204
    assert nearest(session, user_id, fake_embedder.vector_for(BODY["title"], BODY["note"]), k=5) == []


def test_client_cannot_set_embedding_model(client, auth_headers, session, fake_embedder):
    fake_embedder.fail = True
    bid = create(client, auth_headers("alice"), embedding_model="nomic-embed-text")
    assert stored(session, bid).embedding_model is None