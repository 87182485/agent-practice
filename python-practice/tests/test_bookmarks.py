"""Starter tests. Each one gets a FRESH in-memory database via the fixtures."""

import pytest

def test_tags_round_trip(client, auth_headers):
    """Would have caught the missing-tags bug on the first run."""
    alice = auth_headers("alice")
    r = client.post(
        "/bookmarks",
        headers=alice,
        json={"title": "SQLite docs", "url": "https://sqlite.org",
              "tags": ["Database", " database ", "reference", ""]},
    )
    assert r.status_code == 201, r.text

    # Not just "201": check the tags actually came back, normalized + deduped.
    names = sorted(t["name"] for t in r.json()["tags"])
    assert names == ["database", "reference"]

    # And that they persist — read it back with a separate request.
    r = client.get(f"/bookmarks/{r.json()['id']}", headers=alice)
    assert sorted(t["name"] for t in r.json()["tags"]) == ["database", "reference"]


def test_app_still_works_after_a_conflict(client, auth_headers):
    """A failed commit must be rolled back, or every LATER request on the same
    session fails. Only visible if you make another request after the error."""
    alice = auth_headers("alice")
    body = {"title": "a", "url": "https://example.com/dup"}
    client.post("/bookmarks", headers=alice, json=body)
    assert client.post("/bookmarks", headers=alice, json=body).status_code == 409

    r = client.post("/bookmarks", headers=alice,
                    json={"title": "b", "url": "https://example.com/other"})
    assert r.status_code == 201, r.text
    assert client.get("/bookmarks", headers=alice).json()["total"] == 2

def test_put_to_my_other_url_is_409_and_changes_nothing(client, auth_headers):
    alice = auth_headers("alice")
    client.post("/bookmarks", headers=alice, json={"title": "a", "url": "https://example.com/a"})
    bid = client.post("/bookmarks", headers=alice,
                      json={"title": "b", "url": "https://example.com/b"}).json()["id"]

    r = client.put(f"/bookmarks/{bid}", headers=alice,
                   json={"title": "renamed", "url": "https://example.com/a"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "A bookmark with this URL already exists"

    after = client.get(f"/bookmarks/{bid}", headers=alice).json()
    assert after["url"] == "https://example.com/b"
    assert after["title"] == "b"      # the whole update was rolled back, not just the URL


# parametrize = Jest's test.each: one test body, run once per row.
@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH", "DELETE"])
def test_cannot_touch_another_users_bookmark(client, auth_headers, method):
    """The IDOR regression test. This bug existed once; this keeps it dead."""
    alice = auth_headers("alice")
    bob = auth_headers("bob")
    r = client.post("/bookmarks", headers=alice,
                    json={"title": "alice's", "url": "https://example.com"})
    bookmark_id = r.json()["id"]

    r = client.request(method, f"/bookmarks/{bookmark_id}", headers=bob,
                       json={"title": "pwned"} if method == "PATCH" else None)
    assert r.status_code == 404

    # The status code alone isn't enough: a DELETE could 404 AFTER deleting.
    r = client.get(f"/bookmarks/{bookmark_id}", headers=alice)
    assert r.status_code == 200
    assert r.json()["title"] == "alice's"