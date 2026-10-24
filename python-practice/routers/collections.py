"""
Collections: group bookmarks into named folders.

Production-ready implementation with full CRUD, pagination, and search.

Endpoints:
    POST   /collections                                     create a collection
    GET    /collections                                     list my collections (paginated)
    GET    /collections/{collection_id}                     get one collection with its bookmarks
    PATCH  /collections/{collection_id}                     update name / description
    DELETE /collections/{collection_id}                     delete a collection
    POST   /collections/{collection_id}/bookmarks/{bookmark_id}   add a bookmark to a collection
    GET    /collections/search?q=...                        search collections by name
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import selectinload
from sqlmodel import col, func, select

from auth import CurrentUserDep, get_current_user
from database import SessionDep
from models.bookmarks import Bookmark
from models.collections import Collection, CollectionCreate, CollectionList, CollectionRead, CollectionUpdate
from routers.bookmarks import OwnedBookmarkDep

# ---- Routes ------------------------------------------------------------------

router = APIRouter(prefix="/collections", dependencies=[Depends(get_current_user)], tags=["collections"])

def get_owned_collection(collection_id: int, session: SessionDep, user: CurrentUserDep) -> Collection:
    """Get a collection by ID and ensure it belongs to the current user."""
    collection = session.get(Collection, collection_id)
    if collection is None or collection.user_id != user.id:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection

OwnedCollectionDep = Annotated[Collection, Depends(get_owned_collection)]

# Follows the shape of CollectionRead: collection -> bookmarks -> tags
COLLECTION_WITH_BOOKMARKS = selectinload(Collection.bookmarks).selectinload(Bookmark.tags)

@router.post("", response_model=CollectionRead, status_code=201)
def create_collection(payload: CollectionCreate, session: SessionDep, user: CurrentUserDep):
    collection = Collection(**payload.model_dump(), user_id=user.id)
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection


@router.get("", response_model=CollectionList)
def list_collections(
    session: SessionDep, 
    user: CurrentUserDep, 
    limit: Annotated[int, Query(ge=1, le=100)] = 20, 
    offset: Annotated[int, Query(ge=0)] = 0
):
    owned = Collection.user_id == user.id
    total = session.exec(select(func.count()).select_from(Collection).where(owned)).one()
    statement = (
        select(Collection)
        .where(owned)
        .options(COLLECTION_WITH_BOOKMARKS)
        .order_by(Collection.id)
        .offset(offset)
        .limit(limit)
    )

    collections = session.exec(statement).all()
    return {"total": total, "data": collections}


@router.get("/search", response_model=list[CollectionRead])
def search_collections(q: str, session: SessionDep, user: CurrentUserDep):
    statement = (
        select(Collection)
        .where(Collection.user_id == user.id, col(Collection.name).ilike(f"%{q}%"))
        .options(COLLECTION_WITH_BOOKMARKS)
        .order_by(Collection.id))  
    return session.exec(statement).all()

@router.get("/{collection_id}", response_model=CollectionRead)
def get_collection(collection: OwnedCollectionDep):
    return collection

@router.patch("/{collection_id}", response_model=CollectionRead)
def update_collection(
    collection: OwnedCollectionDep, payload: CollectionUpdate, session: SessionDep, user: CurrentUserDep
):
    collection.sqlmodel_update(payload.model_dump(exclude_unset=True))
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection: OwnedCollectionDep, session: SessionDep):
    session.delete(collection)
    session.commit()


@router.post("/{collection_id}/bookmarks/{bookmark_id}", response_model=CollectionRead)
def add_bookmark_to_collection(
    collection: OwnedCollectionDep, bookmark: OwnedBookmarkDep, session: SessionDep):
    collection.bookmarks.append(bookmark)
    session.commit()
    session.refresh(collection)
    return collection