"""
Shared pytest fixtures. pytest finds this file automatically — you never import it.

A fixture is a function whose return/yield value gets INJECTED into any test
that names it as a parameter. If that sounds like FastAPI's Depends(), it is
the same idea: declare what you need by name, the framework builds it.
Closest Jest analogy: beforeEach + afterEach, but per-test and opt-in.
"""

import zlib

import pytest
from app.embeddings import EmbeddingError, get_embedder
from app.vector_store import (
    create_vec_table,
    install_sqlite_vec,
)
from database import get_session
from fastapi.testclient import TestClient
from main import app
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


FAKE_DIMS = 768

class FakeEmbedder:
    """Mimics Embedder: records every call, returns unit vectors."""
    model = "fake-model"

    def __init__(self):
        self.calls: list[list[tuple[str, str | None]]] = []
        self.fail = False

    def vector_for(self, title: str, note: str | None) -> list[float]:
        v: list[float] = [0] * FAKE_DIMS       # explicit annotation; ints are accepted as floats here
        v[zlib.crc32(f"{title}|{note}".encode()) % FAKE_DIMS] = 1.0
        return v

    def embed_documents(self, docs: list[tuple[str, str | None]]) -> list[list[float]]:
        self.calls.append(list(docs))
        if self.fail:
            raise EmbeddingError("fake: embedding unavailable")
        return [self.vector_for(title, note) for title, note in docs]

@pytest.fixture(name="fake_embedder")
def fake_embedder():
    return FakeEmbedder()

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
    install_sqlite_vec(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        create_vec_table(session, 768)
        yield session          # code after yield = teardown (like afterEach)


@pytest.fixture(name="client")
def client_fixture(session: Session, fake_embedder):
    def get_session_override():
        try:
            yield session
        except Exception:
            session.rollback()
            raise
    # The payoff of Depends: swap the real database for the test one.
    # Every endpoint that asks for get_session now receives `session`.
    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_embedder] = lambda: fake_embedder

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