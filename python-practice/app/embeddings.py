# embeddings.py   (in bookmark-api, next to search.py)
import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import httpx
import ollama
from fastapi import Depends


@dataclass(frozen=True)
class ModelConfig:
    dims: int
    query: str   # format string with {q}
    doc: str     # format string with {title} and {note}

class EmbeddingError(ValueError):
    """Raised when embedding fails due to connection issues or validation errors."""


MODELS = {
    # VERIFY these strings against each model card before relying on them
    "nomic-embed-text": ModelConfig(768, "search_query: {q}", "search_document: {title}\n{note}"),
    "embeddinggemma":   ModelConfig(768, "task: search result | query: {q}", "title: {title} | text: {note}"),
}

NORM_TOLERANCE = 1e-3
EMBED_TIMEOUT_SECONDS = 5


class Embedder:
    def __init__(self, model: str, client=None):
        if model not in MODELS:
            raise ValueError(f"Unknown model: {model}")
        self.model = model
        self.config = MODELS[model]
        self.client = client or ollama.Client(timeout=EMBED_TIMEOUT_SECONDS)

    def embed_query(self, q: str) -> list[float]:
        query_text = self.config.query.format(q=q)
        return self._embed([query_text])[0]

    def embed_documents(self, docs: list[tuple[str, str | None]]) -> list[list[float]]:
        formatted_docs = [self.config.doc.format(title=title, note=note or "") for title, note in docs]
        return self._embed(formatted_docs)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            r = self.client.embed(model=self.model, input=texts)
        except (ConnectionError, httpx.HTTPError, ollama.ResponseError) as e:
            raise EmbeddingError(f"{self.model}: embedding call failed: {e}") from e
        for v in r.embeddings:
            self._validate(v)
        return [list(v) for v in r.embeddings]
        
    def _validate(self, v: Sequence[float]) -> None:
        if len(v) != self.config.dims:
            raise EmbeddingError(f"Vector has wrong dimensions: expected {self.config.dims}, got {len(v)}")
        if abs(math.sqrt(sum(x * x for x in v)) - 1.0) > NORM_TOLERANCE:
            raise EmbeddingError(f"Vector norm is not close to 1.0: {math.sqrt(sum(x * x for x in v))}")
@lru_cache
def get_embedder() -> Embedder:
    return default_embedder()  # The embedder the API uses, chosen by the EMBED_MODEL env var

EmbedderDep = Annotated[Embedder, Depends(get_embedder)]

def default_embedder() -> Embedder:
    """The embedder the API uses, chosen by the EMBED_MODEL env var."""
    return Embedder(os.environ.get("EMBED_MODEL", "nomic-embed-text"))