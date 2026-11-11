from typing import Annotated

from app.embeddings import default_embedder
from app.vector_store import (  # Load sqlite-vec into every new connection this engine opens
    create_vec_table,
    install_sqlite_vec,
)
from fastapi import Depends
from settings import settings
from sqlmodel import Session, SQLModel, create_engine

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=True, connect_args=connect_args)
install_sqlite_vec(engine)  # Load sqlite-vec into every new connection this engine opens

def create_db_and_tables():
    """Create the database and tables if they don't exist."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        create_vec_table(session, default_embedder().config.dims)  # Create the vector table with the correct number of dimensions
        session.commit()  # Commit after creating the vector table to ensure it's stored

def get_session():
    """Get a new database session."""
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise

SessionDep = Annotated[Session, Depends(get_session)]