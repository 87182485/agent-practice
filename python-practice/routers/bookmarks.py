from typing import Annotated

from app.embeddings import EmbedderDep
from app.vector_store import delete_vector
from app.indexing import index_bookmark
from app.search import escape_like
from auth import CurrentUserDep, get_current_user
from database import SessionDep
from errors import BookmarkNotFound
from fastapi import APIRouter, Depends, Query, status
from models.bookmarks import (
    Bookmark,
    BookmarkCreate,
    BookmarkList,
    BookmarkRead,
    BookmarkUpdate,
    Tag,
)
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, select

router = APIRouter(prefix="/bookmarks", dependencies=[Depends(get_current_user)])

def get_or_create_tags(session: Session, names: list[str]) -> list[Tag]:
    """Get an existing tag by name or create a new one if it doesn't exist."""
    cleaned = list(dict.fromkeys(n.strip().lower() for n in names if n.strip()))  # Remove duplicates and whitespace
    tags = []
    for name in cleaned:
        tag = session.exec(select(Tag).where(Tag.name == name)).first()
        tags.append(tag or Tag(name=name))
    return tags

def get_owned_bookmark(bookmark_id: int, session: SessionDep, user: CurrentUserDep) -> Bookmark:
    """Get a bookmark by ID and ensure it belongs to the current user."""
    bookmark = session.get(Bookmark, bookmark_id)
    if bookmark is None or bookmark.user_id != user.id:
        raise BookmarkNotFound()
    return bookmark

OwnedBookmarkDep = Annotated[Bookmark, Depends(get_owned_bookmark)]

@router.post("", response_model=BookmarkRead, status_code=status.HTTP_201_CREATED)
def create_bookmark(payload: BookmarkCreate, session: SessionDep, user: CurrentUserDep, embedder: EmbedderDep):
    bookmark = Bookmark(
        title=payload.title,
        note=payload.note,
        url=str(payload.url),   # HttpUrl -> str for storage
        user_id=user.id,  # Assign the current user to the bookmark
        tags=get_or_create_tags(session, payload.tags),
    )
    session.add(bookmark)
    session.flush()  # Flush to get the bookmark ID for indexing
    index_bookmark(session, embedder, bookmark)  # Index the bookmark after it has an ID
    session.commit()
    session.refresh(bookmark)
    return bookmark


@router.get("", response_model=BookmarkList)
def list_bookmarks(
    session: SessionDep,
    user: CurrentUserDep,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    # select() takes the MODEL (what to fetch) and builds a statement — it does
    # not touch the database. session.exec() is what actually runs it.
    statement = select(Bookmark).where(Bookmark.user_id == user.id).options(selectinload(Bookmark.tags)).order_by(Bookmark.id)  # Filter bookmarks by the current user
    count_statement = select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user.id)  # Count bookmarks for the current user

    if q is not None:
        # ilike = case-insensitive LIKE, done BY THE DATABASE.
        # `q` is passed as a parameter, not concatenated — not injectable.
        condition = col(Bookmark.title).ilike(f"%{escape_like(q)}%", escape="\\")  # Escape special characters for LIKE
        statement = statement.where(condition)
        # The count must get the SAME filter, or `total` describes a different
        # set than `data`.
        count_statement = count_statement.where(condition)

    total = session.exec(count_statement).one()
    # .offset()/.limit() become SQL OFFSET/LIMIT, so the DB returns only the
    # rows you asked for. The milestone-1 version loaded EVERY row into Python
    # and then sliced — fine at 100 rows, fatal at a million.
    page = session.exec(statement.offset(offset).limit(limit)).all()

    return {"limit": limit, "offset": offset, "total": total, "data": page}


@router.get("/{bookmark_id}", response_model=BookmarkRead)
def get_bookmark(bookmark: OwnedBookmarkDep):
    return bookmark

@router.put("/{bookmark_id}", response_model=BookmarkRead)
def update_bookmark(bookmark: OwnedBookmarkDep, payload: BookmarkCreate, session: SessionDep, embedder: EmbedderDep):
    data = payload.model_dump(exclude={"tags"})
    data["url"] = str(data["url"])
    before = (bookmark.title, bookmark.note)
    bookmark.sqlmodel_update(data)   # replaces milestone 1's dict .update()
    bookmark.tags = get_or_create_tags(session, payload.tags)  # replace the tags with the new ones
    session.add(bookmark)
    if (bookmark.title, bookmark.note) != before:
        index_bookmark(session, embedder, bookmark)  # re-index if title or note changed
    session.commit()
    session.refresh(bookmark)
    return bookmark


@router.patch("/{bookmark_id}", response_model=BookmarkRead)
def patch_bookmark(bookmark: OwnedBookmarkDep, payload: BookmarkUpdate, session: SessionDep, embedder: EmbedderDep):
    # Same exclude_unset trick as milestone 1 — it carries over unchanged.
    data = payload.model_dump(exclude_unset=True)
    if "url" in data:
        data["url"] = str(data["url"])
    before = (bookmark.title, bookmark.note)
    bookmark.sqlmodel_update(data)
 # re-index if title or note changed
    session.add(bookmark)
    if (bookmark.title, bookmark.note) != before or bookmark.embedding_model != embedder.model:
        index_bookmark(session, embedder, bookmark)
    session.commit()
    session.refresh(bookmark)
    return bookmark

@router.delete("/{bookmark_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(bookmark: OwnedBookmarkDep, session: SessionDep):
    delete_vector(session, bookmark.id)  # Remove the vector from the vector store
    session.delete(bookmark)
    session.commit()