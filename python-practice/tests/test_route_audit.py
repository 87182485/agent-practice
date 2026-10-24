import re

import pytest

from main import app
from errors import ErrorDetail

PUBLIC = {("POST", "/users"), ("POST", "/token")}

PROTECTED = [
    (method.upper(), path)
    for path, operations in app.openapi()["paths"].items()
    for method in sorted(operations)
    if (method.upper(), path) not in PUBLIC
]


def test_audit_found_routes():
    assert len(PROTECTED) >= 10, PROTECTED      # bookmarks + collections

@pytest.mark.parametrize("method,path", PROTECTED)
def test_protected_routes_require_auth(client, method, path):
    url = re.sub(r"\{[^}]+\}", "1", path)       # fills any {param} with 1
    r = client.request(method, url)
    assert r.status_code == 401, f"{method} {path} returned {r.status_code}"

# Read routes from the OpenAPI schema — the same data as /openapi.json.
# (Don't walk app.routes: newer FastAPI wraps included routers in a single
# object, so their routes aren't listed there directly.)
BOOKMARK_ROUTES = [
    (method.upper(), path)
    for path, operations in app.openapi()["paths"].items()
    if path.startswith("/bookmarks")
    for method in sorted(operations)
]

def test_audit_found_routes():
    # Without this, an empty BOOKMARK_ROUTES makes the test below run zero
    # times — and pytest reports that as a pass.
    assert len(BOOKMARK_ROUTES) >= 5, BOOKMARK_ROUTES

@pytest.mark.parametrize("method,path", BOOKMARK_ROUTES)
def test_bookmark_routes_require_auth(client, method, path):
    """Regression test for a bug where some bookmark routes didn't require auth."""
    r = client.request(method, path)
    assert r.status_code == 401, f"{method} {path} returned {r.status_code} instead of 401"
    body = r.json()
    assert body["detail"] == ErrorDetail.NOT_AUTHENTICATED