from enum import StrEnum

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

# ---- Error details ------------------------------------------------------------
# StrEnum members ARE strings: they serialize as plain text in the JSON body and
# compare equal to str, so tests can assert `body["detail"] == ErrorDetail.X`.
class ErrorDetail(StrEnum):
    USERNAME_TAKEN = "Username already exists"
    INVALID_LOGIN = "Invalid username or password"
    INVALID_TOKEN = "Invalid authentication credentials"
    # Raised by FastAPI's OAuth2PasswordBearer (not our code) when the
    # Authorization header is missing. Must match its text exactly.
    NOT_AUTHENTICATED = "Not authenticated"
    DUPLICATE_URL = "A bookmark with this URL already exists"
    BOOKMARK_NOT_FOUND = "Bookmark not found"
    GENERIC_CONFLICT = "Request conflicts with existing data"

class BookmarkNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorDetail.BOOKMARK_NOT_FOUND)

def integrity_error_detail(exc: IntegrityError) -> str:
    msg = str(exc.orig)
    if "bookmark.user_id, bookmark.url" in msg or "uq_bookmark_user_url" in msg:
        return ErrorDetail.DUPLICATE_URL
    if "user.username" in msg:
        return ErrorDetail.USERNAME_TAKEN
    return ErrorDetail.GENERIC_CONFLICT

async def handle_integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"detail": integrity_error_detail(exc)},
    )

async def handle_stale_data(request: Request, exc: StaleDataError):
    return JSONResponse(
        status_code=404,
        content={"detail": "Bookmark not found"},
    )

def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IntegrityError, handle_integrity_error)
    app.add_exception_handler(StaleDataError, handle_stale_data)