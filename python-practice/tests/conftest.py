"""
Shared pytest fixtures. pytest finds this file automatically — you never import it.

A fixture is a function whose return/yield value gets INJECTED into any test
that names it as a parameter. If that sounds like FastAPI's Depends(), it is
the same idea: declare what you need by name, the framework builds it.
Closest Jest analogy: beforeEach + afterEach, but per-test and opt-in.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from database import get_session
from main import app



@pytest.fixture(name="session")
def session_fixture():
    # "sqlite://" with no path = an IN-MEMORY database. Gone when the test ends,
    # so every test starts empty. No more `rm bookmarks.db`.
    #
    # StaticPool: an in-memory SQLite DB exists per CONNECTION. Without this,
    # the test's connection and the app's connection would each see their own
    # empty database. StaticPool makes everything share one connection.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session          # code after yield = teardown (like afterEach)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        try:
            yield session
        except Exception:
            session.rollback()
            raise
    # The payoff of Depends: swap the real database for the test one.
    # Every endpoint that asks for get_session now receives `session`.
    app.dependency_overrides[get_session] = get_session_override

    # Deliberately NOT `with TestClient(app)`: the context-manager form runs
    # your lifespan, which would create tables in the REAL bookmarks.db.
    # The session fixture already created tables in the in-memory engine.
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()   # don't leak the override into other tests


@pytest.fixture
def auth_headers(client: TestClient):
    """Factory fixture: returns a FUNCTION that registers + logs in a user.

    Usage in a test:  alice = auth_headers("alice")
    JS analogy: a test helper like `const login = async (name) => {...}`,
    except pytest hands it to you already wired to this test's client.
    """
    def _make(username: str, password: str = "test-pw") -> dict[str, str]:
        r = client.post("/users", json={"username": username, "password": password})
        assert r.status_code == 201, r.text
        r = client.post("/token", data={"username": username, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make