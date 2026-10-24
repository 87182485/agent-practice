from fastapi.routing import APIRoute
from main import app
from errors import ErrorDetail

# Built at import time, so parametrize can use it — like computing
# the table for test.each() before the describe block runs.
BOOKMARK_ROUTES = [
    (method, route.path)
    for route in app.routes
    if isinstance(route, APIRoute) and route.path.startswith("/bookmarks")
    for method in route.methods
]

def test_register_returns_201_without_hash(client):
    r = client.post("/users", json={"username": "alice", "password": "test-pw"})
    assert r.status_code == 201, r.text
    body =  r.json()
    assert body["username"] == "alice"
    assert "password" not in body, "Password should not be returned in response"
    assert "hashed_password" not in body, "Hashed password should not be returned in response"

def test_register_returns_400_for_existing_user(client):
    r = client.post("/users", json={"username": "alice", "password": "test-pw"})
    assert r.status_code == 201, r.text
    r = client.post("/users", json={"username": "alice", "password": "test-pw"})
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["detail"] == ErrorDetail.USERNAME_TAKEN

def test_login_returns_token_for_valid_credentials(client):
    r = client.post("/users", json={"username": "alice", "password": "test-pw"})
    assert r.status_code == 201, r.text
    r = client.post("/token", data={"username": "alice", "password": "test-pw"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

def test_login_returns_401_for_invalid_credentials(client):
    r = client.post("/users", json={"username": "alice", "password": "test-pw"})
    assert r.status_code == 201, r.text
    r = client.post("/token", data={"username": "alice", "password": "wrong-pw"})
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["detail"] == ErrorDetail.INVALID_LOGIN

def test_login_returns_401_for_nonexistent_user(client):
    r = client.post("/token", data={"username": "nonexistent", "password": "test-pw"})
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["detail"] == ErrorDetail.INVALID_LOGIN

def test_login_returns_422_for_missing_fields(client):
    r = client.post("/token", data={"username": "alice"})
    assert r.status_code == 422, r.text
    r = client.post("/token", data={"password": "test-pw"})
    assert r.status_code == 422, r.text

def test_same_url_across_users(client, auth_headers):
    """Regression test for a bug where one user's bookmark could be read by another."""
    alice = auth_headers("alice")
    bob = auth_headers("bob")
    body = {"title": "SQLite docs", "url": "https://sqlite.org"}

    print(alice)

    # Alice creates a bookmark
    r = client.post(
        "/bookmarks",
        headers=alice,
        json=body,
    )
    assert r.status_code == 201, r.text
    bookmark_id = r.json()["id"]

    # Bob tries to access Alice's bookmark
    r = client.get(f"/bookmarks/{bookmark_id}", headers=bob)
    assert r.status_code == 404, r.text