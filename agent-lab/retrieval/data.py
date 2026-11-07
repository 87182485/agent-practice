# retrieval/data.py
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Query:
    id: str
    user: str
    category: str
    query: str
    relevant: frozenset[str]


def load_queries(path: Path) -> list[Query]:
    raw = json.loads(path.read_text())
    return [Query(**{**item, "relevant": frozenset(item["relevant"])}) for item in raw]