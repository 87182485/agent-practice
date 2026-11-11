# tests/test_vector_store.py   (in bookmark-api)
import numpy as np
import pytest
from sqlalchemy import text

from app.vector_store import delete_vector, nearest, upsert_vector   # adjust to your layout

DIMS = 768


def unit(v) -> list[float]:
    v = np.asarray(v, dtype=np.float64)
    return list(v / np.linalg.norm(v))


def basis(i: int) -> list[float]:
    """Unit vector pointing along axis i: easy to reason about in tests."""
    v = [0.0] * DIMS
    v[i] = 1.0
    return v


def test_extension_loaded(session):
    version = session.execute(text("select vec_version()")).scalar()
    assert version.startswith("v0.1")


def test_nearest_orders_by_distance(session):
    upsert_vector(session, 1, user_id=1, vec=basis(0))
    upsert_vector(session, 2, user_id=1, vec=basis(1))
    query = unit([1.0, 0.2] + [0.0] * (DIMS - 2))   # close to axis 0, a bit toward axis 1
    assert [bid for bid, _ in nearest(session, 1, query, k=2)] == [1, 2]


def test_nearest_filters_by_user(session):
    upsert_vector(session, 1, user_id=1, vec=basis(0))
    upsert_vector(session, 2, user_id=2, vec=basis(0))   # identical vector, other user
    assert [bid for bid, _ in nearest(session, 1, basis(0), k=5)] == [1]


def test_delete_removes_from_results(session):
    upsert_vector(session, 1, user_id=1, vec=basis(0))
    delete_vector(session, 1)
    assert nearest(session, 1, basis(0), k=5) == []


def test_upsert_replaces_existing_vector(session):
    upsert_vector(session, 1, user_id=1, vec=basis(0))
    upsert_vector(session, 1, user_id=1, vec=basis(1))   # would hit UNIQUE without delete-first
    [(bid, dist)] = nearest(session, 1, basis(1), k=5)
    assert bid == 1 and dist == pytest.approx(0.0, abs=1e-6)


def test_matches_numpy_oracle(session):
    rng = np.random.default_rng(0)                  # fixed seed: same vectors every run
    vecs = rng.normal(size=(50, DIMS))
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    for i, v in enumerate(vecs, start=1):
        upsert_vector(session, i, user_id=1, vec=list(v))

    for _ in range(10):
        q = rng.normal(size=DIMS)
        q /= np.linalg.norm(q)
        expected = (np.argsort(-(vecs @ q))[:5] + 1).tolist()   # +1: ids start at 1
        got = [bid for bid, _ in nearest(session, 1, list(q), k=5)]
        assert got == expected

def test_rollback_removes_uncommitted_vector(session):
    upsert_vector(session, 1, user_id=1, vec=basis(0))
    session.rollback()
    assert nearest(session, 1, basis(0), k=5) == []