"""
Error-handling tests for the part-4 refactor.

CHARACTERIZATION tests pin down behavior that is already correct, so the
refactor can't break it. They should pass BEFORE and AFTER.

BEHAVIOR tests describe what we want but don't have yet. They should FAIL
before the fix (proving they detect the bug) and pass after.
"""
from sqlalchemy.orm.exc import StaleDataError

from routers import bookmarks

from errors import ErrorDetail

# ---- characterization: must pass before AND after the refactor ----

def test_duplicate_url_same_user_is_409(client, auth_headers):
    alice = auth_headers("alice")
    body = {"title": "a", "url": "https://dup.example.com"}
    assert client.post("/bookmarks", headers=alice, json=body).status_code == 201
    r = client.post("/bookmarks", headers=alice, json=body)
    assert r.status_code == 409
    assert r.json()["detail"] == ErrorDetail.DUPLICATE_URL


# ---- behavior: should FAIL now, pass after the refactor ----

def test_tag_conflict_is_not_reported_as_duplicate_url(client, auth_headers, monkeypatch):
    """The tag-creation race, forced deterministically.

    In real life two requests both create the tag "python" at the same moment.
    Here we make get_or_create_tags always build NEW Tag objects, so the
    second bookmark collides on tag.name — same IntegrityError, no race needed.
    """
    monkeypatch.setattr(
        bookmarks, "get_or_create_tags",
        lambda session, names: [bookmarks.Tag(name=n.strip().lower()) for n in names],
    )
    alice = auth_headers("alice")
    client.post("/bookmarks", headers=alice,
                json={"title": "a", "url": "https://a.example.com", "tags": ["python"]})
    r = client.post("/bookmarks", headers=alice,
                    json={"title": "b", "url": "https://b.example.com", "tags": ["python"]})
    assert r.status_code == 409
    assert r.json()["detail"] == ErrorDetail.GENERIC_CONFLICT     # NOT the duplicate-URL message


def test_stale_update_is_404_not_500(client, auth_headers, session, monkeypatch):
    """Another request deleted the bookmark between our load and our commit."""
    alice = auth_headers("alice")
    bid = client.post("/bookmarks", headers=alice,
                      json={"title": "a", "url": "https://a.example.com"}).json()["id"]

    def commit_after_concurrent_delete():
        raise StaleDataError("simulated: row deleted by another request")

    # The app uses this exact session object (conftest's override returns it),
    # so patching it here changes what the endpoint's commit() does.
    monkeypatch.setattr(session, "commit", commit_after_concurrent_delete)

    r = client.patch(f"/bookmarks/{bid}", headers=alice, json={"title": "new"})
    assert r.status_code == 404
    assert r.json()["detail"] == ErrorDetail.BOOKMARK_NOT_FOUND