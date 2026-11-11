# tests/test_embeddings.py   (in bookmark-api)
from types import SimpleNamespace

import httpx
import pytest
from app.embeddings import (  # adjust the import to where search.py went
    Embedder,
    EmbeddingError,
)

DIMS = 768
UNIT = [1.0] + [0.0] * (DIMS - 1)


class FakeOllama:
    """Mimics ollama.Client.embed: records every call, returns unit vectors."""

    def __init__(self, vector=UNIT):
        self.calls = []
        self.vector = vector

    def embed(self, model, input):
        self.calls.append((model, list(input)))
        return SimpleNamespace(embeddings=[self.vector for _ in input])

class BrokenOllama:
    """Mimics ollama.Client.embed: raises an exception."""

    def embed(self, model, input):
        raise httpx.ConnectTimeout("timed out")


def test_nomic_query_prefix():
    fake = FakeOllama()
    Embedder("nomic-embed-text", client=fake).embed_query("slow db")
    assert fake.calls == [("nomic-embed-text", ["search_query: slow db"])]


def test_gemma_document_format():
    fake = FakeOllama()
    Embedder("embeddinggemma", client=fake).embed_documents([("Use The Index", "B-tree basics")])
    assert fake.calls == [("embeddinggemma", ["title: Use The Index | text: B-tree basics"])]


def test_missing_note_becomes_empty_text():
    fake = FakeOllama()
    Embedder("embeddinggemma", client=fake).embed_documents([("CSS Grid", None)])
    assert fake.calls[0][1] == ["title: CSS Grid | text: "]


def test_documents_are_batched_in_one_call():
    fake = FakeOllama()
    vecs = Embedder("nomic-embed-text", client=fake).embed_documents([("a", None), ("b", None), ("c", None)])
    assert len(fake.calls) == 1 and len(vecs) == 3


def test_unknown_model_rejected():
    with pytest.raises(ValueError):
        Embedder("not-a-model", client=FakeOllama())


def test_wrong_dimensions_rejected():
    fake = FakeOllama(vector=[1.0, 0.0])
    with pytest.raises(ValueError):
        Embedder("nomic-embed-text", client=fake).embed_query("x")


def test_non_unit_vector_rejected():
    fake = FakeOllama(vector=[2.0] + [0.0] * (DIMS - 1))   # norm 2.0
    with pytest.raises(ValueError):
        Embedder("nomic-embed-text", client=fake).embed_query("x")

def test_connection_failure_becomes_embedding_error():
    with pytest.raises(EmbeddingError):
        Embedder("nomic-embed-text", client=BrokenOllama()).embed_query("x")

def test_validation_failure_is_embedding_error():
    fake = FakeOllama(vector=[1.0, 0.0])   # norm 2.0
    with pytest.raises(EmbeddingError):
        Embedder("nomic-embed-text", client=fake).embed_query("x")