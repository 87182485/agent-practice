

from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import create_db_and_tables
from errors import register_exception_handlers
from routers import bookmarks, collections, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Everything before `yield` runs once at STARTUP; everything after runs
    # once at SHUTDOWN. Same yield-splits-setup-from-teardown shape as
    # get_session below, just at application scope instead of request scope.
    # `app` is unused here — it exists because FastAPI passes it in.
    create_db_and_tables()
    yield
    # (nothing to tear down: the engine's pool cleans itself up)

app = FastAPI(title="Bookmarks", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(users.router)
app.include_router(bookmarks.router)
app.include_router(collections.router)