"""Tests for the collections feature. All passing."""

import pytest

from routers.collections import router

def test_list_only_counts_my_collections(client, auth_headers):
    alice = auth_headers("alice")
    bob = auth_headers("bob")
    client.post("/collections", headers=alice, json={"name": "a1"})
    client.post("/collections", headers=alice, json={"name": "a2"})
    client.post("/collections", headers=bob, json={"name": "b1"})

    body = client.get("/collections", headers=alice).json()
    assert body["total"] == 2
    assert sorted(c["name"] for c in body["data"]) == ["a1", "a2"]


def test_patch_can_clear_description(client, auth_headers):
    alice = auth_headers("alice")
    cid = client.post("/collections", headers=alice,
                      json={"name": "x", "description": "remove me"}).json()["id"]
    r = client.patch(f"/collections/{cid}", headers=alice, json={"description": None})
    assert r.status_code == 200, r.text
    assert r.json()["description"] is None

def test_create_collection(client, auth_headers):
    alice = auth_headers("alice")
    r = client.post("/collections", headers=alice, json={"name": "work", "description": "job stuff"})
    assert r.status_code == 201
    assert r.json()["name"] == "work"


def test_list_collections(client, auth_headers):
    alice = auth_headers("alice")
    client.post("/collections", headers=alice, json={"name": "work"})
    client.post("/collections", headers=alice, json={"name": "reading"})
    r = client.get("/collections", headers=alice)
    assert r.status_code == 200
    assert r.json()["total"] == 2


def test_cannot_read_another_users_collection(client, auth_headers):
    alice = auth_headers("alice")
    bob = auth_headers("bob")
    cid = client.post("/collections", headers=alice, json={"name": "private"}).json()["id"]
    r = client.get(f"/collection/{cid}", headers=bob)
    assert r.status_code == 404


PROTECTED_ROUTES = [route for route in router.routes if route.dependencies]


@pytest.mark.parametrize("route", PROTECTED_ROUTES)
def test_collection_routes_require_auth(client, route):
    method = sorted(route.methods)[0]
    r = client.request(method, route.path.replace("{collection_id}", "1").replace("{bookmark_id}", "1"))
    assert r.status_code == 401

@pytest.mark.parametrize("method, body", [
    ("GET", None),
    ("PATCH", {"name": "pwned"}),
    ("DELETE", None),
])
def test_cannot_touch_another_users_collection(client, auth_headers, method, body):
    alice = auth_headers("alice")
    bob = auth_headers("bob")
    cid = client.post("/collections", headers=alice, json={"name": "private"}).json()["id"]

    r = client.request(method, f"/collections/{cid}", headers=bob, json=body)
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Collection not found"

    after = client.get(f"/collections/{cid}", headers=alice)
    assert after.status_code == 200
    assert after.json()["name"] == "private"