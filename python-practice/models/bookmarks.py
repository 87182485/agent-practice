# ---- Models -----------------------------------------------------------------
# Fields shared by every variant, declared once.
from datetime import datetime, timezone

from pydantic import HttpUrl
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint
from settings import settings


class BookmarkBase(SQLModel):
    title: str
    note: str | None = None
    
class BookmarkTagLink(SQLModel, table=True):
    bookmark_id: int = Field(default=None, foreign_key="bookmark.id", primary_key=True)
    tag_id: int | None = Field(default=None, foreign_key="tag.id", primary_key=True)


# THIS one is the database table. Note `url` lives here as a plain `str`, not
# in the base: HttpUrl is a great validation type at the API edge but is not a
# SQL column type. Validate as HttpUrl on the way in, store as str.
class Bookmark(BookmarkBase, table=True):
    __table_args__ = (UniqueConstraint("user_id", "url", name="uq_bookmark_user_url"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # unique=True is the payoff: it replaces _url_taken AND closes the race,
    # because the database enforces it atomically.
    # index=True makes lookups on url fast.
    url: str = Field(index=True)
    # default_factory, NOT default: `default=datetime.now(...)` would evaluate
    # once at import and give every row the same timestamp.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list["Tag"] = Relationship(back_populates="bookmarks", link_model=BookmarkTagLink)

class BookmarkCreate(BookmarkBase):
    url: HttpUrl
    tags: list[str] = []

class TagRead(SQLModel):
    id: int
    name: str


class BookmarkRead(BookmarkBase):
    # `id` is `int | None` on the table (it doesn't exist until the DB assigns
    # it) but plain `int` here — by response time it definitely exists.
    id: int
    url: str
    created_at: datetime
    tags: list[TagRead] = []


class BookmarkUpdate(SQLModel):
    title: str | None = None
    url: HttpUrl | None = None
    note: str | None = None


class BookmarkList(SQLModel):
    limit: int
    offset: int
    total: int
    data: list[BookmarkRead]

class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    bookmarks: list[Bookmark] = Relationship(back_populates="tags", link_model=BookmarkTagLink)

