# vector_store.py   (in bookmark-api, next to embeddings.py)
import sqlite_vec
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session

TABLE = "bookmark_vec"


def install_sqlite_vec(engine: Engine) -> None:
    """Load sqlite-vec into every new connection this engine opens."""

    @event.listens_for(engine, "connect")
    def _load(dbapi_conn, _record):
        dbapi_conn.enable_load_extension(True)
        try:
            sqlite_vec.load(dbapi_conn)
        finally:
            dbapi_conn.enable_load_extension(False)
        


def create_vec_table(session: Session, dims: int) -> None:
    if isinstance(dims, bool) or not isinstance(dims, int) or dims <= 0:
        raise ValueError(f"dims must be a positive int, got {dims!r}")
    session.connection().execute(text(f"create virtual table if not exists {TABLE} using vec0("
                         f"user_id integer partition key, embedding float[{dims}] distance_metric=cosine)"))


def upsert_vector(session: Session, bookmark_id: int, user_id: int, vec: list[float]) -> None:
    delete_vector(session, bookmark_id)
    text_insert = text(f"insert into {TABLE}(rowid, user_id, embedding) values (:id, :uid, :vec)")
    params = {
        "id": bookmark_id,
        "uid": user_id,
        "vec": sqlite_vec.serialize_float32(vec)
    }

    session.connection().execute(text_insert, params)

def delete_vector(session: Session, bookmark_id: int) -> None:
    text_delete = text(f"delete from {TABLE} where rowid = :id")
    params = {"id": bookmark_id}
    session.connection().execute(text_delete, params)

def nearest(session: Session, user_id: int, vec: list[float], k: int) -> list[tuple[int, float]]:
    text_nearest = text(
        f"select rowid, distance from {TABLE} "
        "where embedding match :vec and k = :k and user_id = :uid "
        "order by distance"
    )
    params = {
        "vec": sqlite_vec.serialize_float32(vec),
        "k": k,
        "uid": user_id,
    }
    result = session.connection().execute(text_nearest, params).all()
    return [tuple(row) for row in result]