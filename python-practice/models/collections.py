from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

from models.bookmarks import Bookmark, BookmarkRead
from models.users import User, UserRead


class CollectionBookmarkLink(SQLModel, table=True):
    collection_id: int | None = Field(default=None, foreign_key="collection.id", primary_key=True)
    bookmark_id: int | None = Field(default=None, foreign_key="bookmark.id", primary_key=True)


class Collection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str | None = None
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    owner: User | None = Relationship()
    bookmarks: list[Bookmark] = Relationship(link_model=CollectionBookmarkLink)


class CollectionCreate(SQLModel):
    name: str
    description: str | None = None


class CollectionUpdate(SQLModel):
    name: str | None = None
    description: str | None = None


class CollectionRead(SQLModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    owner: UserRead
    bookmarks: list[BookmarkRead] = []


class CollectionList(SQLModel):
    total: int
    data: list[CollectionRead]