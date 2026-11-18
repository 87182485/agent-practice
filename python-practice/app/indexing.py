# indexing.py
import logging

from models.bookmarks import Bookmark
from sqlmodel import Session

from app.embeddings import Embedder, EmbeddingError
from app.vector_store import delete_vector, upsert_vector

log = logging.getLogger(__name__)


def index_bookmark(session: Session, embedder: Embedder, bookmark: Bookmark) -> None:
    """Embed the bookmark and store its vector. Never raises EmbeddingError. Never commits."""
    if bookmark.id is None:
        raise ValueError("bookmark.id must not be None")
    try:
        [vec] = embedder.embed_documents([(bookmark.title, bookmark.note)])
    except EmbeddingError as e:
        delete_vector(session, bookmark.id)
        bookmark.embedding_model = None
        log.warning("bookmark %s not indexed: %s", bookmark.id, type(e).__name__)
    else:
        upsert_vector(session, bookmark.id, bookmark.user_id, vec)
        bookmark.embedding_model = embedder.model