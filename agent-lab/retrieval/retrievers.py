# retrieval/retrievers.py
from typing import Protocol


class Retriever(Protocol):
    name: str

    def search(self, user: str, query: str, limit: int) -> list[str]:
        """Return bookmark keys owned by `user`, best match first, at most `limit`."""
        ...

class KeywordRetriever:
    def __init__(self, corpus: list[dict], fields: tuple[str, ...], name: str):
        self.corpus = corpus
        self.fields = fields
        self.name = name

    def search(self, user: str, query: str, limit: int) -> list[str]:
        user_bookmarks = [b for b in self.corpus if b["owner"] == user]
        matches = [b for b in user_bookmarks if any(_matches(b.get(f) or "", query) for f in self.fields)]
        return [b["key"] for b in matches][:limit]


def _matches(text: str, query: str) -> bool:
    return query.lower() in text.lower()
