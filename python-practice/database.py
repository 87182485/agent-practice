from settings import settings
from sqlmodel import SQLModel, Session, create_engine

from typing import Annotated
from fastapi import Depends

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=True, connect_args=connect_args)

def create_db_and_tables():
    """Create the database and tables if they don't exist."""
    SQLModel.metadata.create_all(engine)

def get_session():
    """Get a new database session."""
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise

SessionDep = Annotated[Session, Depends(get_session)]