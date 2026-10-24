"""Tools that let the agent use the bookmark API as a logged-in user.

Credentials come from the environment and never enter the model's context:
the model sees tool names, arguments and results, nothing else.

    export BOOKMARK_USER=agent-user
    export BOOKMARK_PASSWORD=...
    export BOOKMARK_API=http://127.0.0.1:8000   # optional, this is the default
"""
import json
import os

import httpx

API = os.environ.get("BOOKMARK_API", "http://127.0.0.1:8000")
_client = httpx.Client(base_url=API, timeout=10)
_token: str | None = None


# ---- HTTP plumbing (never visible to the model) ------------------------------

def _login() -> None:
    global _token                       # assign the MODULE-level _token, not a new local
    r = _client.post("/token", data={
        "username": os.environ["BOOKMARK_USER"],
        "password": os.environ["BOOKMARK_PASSWORD"],
    })
    r.raise_for_status()
    _token = r.json()["access_token"]


def _request(method: str, path: str, **kwargs):
    """One authenticated request. Turns API errors into messages written for the model."""
    if _token is None:
        _login()
    r = _client.request(method, path, headers={"Authorization": f"Bearer {_token}"}, **kwargs)
    if r.status_code == 401:            # token expired: log in again, retry once
        _login()
        r = _client.request(method, path, headers={"Authorization": f"Bearer {_token}"}, **kwargs)

    if r.status_code == 404:
        raise ValueError("Not found. Bookmark ids come from list_bookmarks: "
                         "look the bookmark up there instead of guessing an id.")
    if r.status_code == 409:
        raise ValueError(r.json().get("detail", "That conflicts with an existing bookmark."))
    if r.status_code == 422:
        raise ValueError(f"The API rejected the input: {r.json().get('detail')}")
    r.raise_for_status()
    return r.json() if r.content else None


def _summarize(b: dict) -> dict:
    """Only the fields the model needs: fewer tokens, less noise."""
    return {"id": b["id"], "title": b["title"], "url": b["url"],
            "tags": [t["name"] for t in b.get("tags", [])]}


# ---- Read tools ----------------------------------------------------------------

def list_bookmarks(query: str | None = None, limit: int | None = None) -> str:
    """List the user's saved bookmarks, optionally filtered by a search term.

    Args:
        query: Optional text to search for in bookmark titles. Omit it to list all bookmarks.
        limit: Optional maximum number of bookmarks to return, from 1 to 100. Defaults to 20.

    Returns:
        JSON with the total number of matches and a list of bookmarks (id, title, url, tags).
    """
    params = {"limit": max(1, min(int(limit or 20), 100))}   # models sometimes send "20" or 500
    if query:
        params["q"] = query
    data = _request("GET", "/bookmarks", params=params)
    return json.dumps({"total": data["total"], "bookmarks": [_summarize(b) for b in data["data"]]})


def get_bookmark(bookmark_id: int) -> str:
    """Get one bookmark by its id, including its note.

    Args:
        bookmark_id: The numeric id of the bookmark, as returned by list_bookmarks.

    Returns:
        JSON with the bookmark's id, title, url, tags and note.
    """
    b = _request("GET", f"/bookmarks/{int(bookmark_id)}")
    return json.dumps({**_summarize(b), "note": b.get("note")})


# ---- Write tools ---------------------------------------------------------------

def _normalize_tags(tags) -> list[str]:
    """Models send tags as a list, a JSON string '["a", "b"]', or "a, b"; accept all three."""
    if isinstance(tags, str):
        try:
            parsed = json.loads(tags)                 # '["python"]' -> ["python"]
            tags = parsed if isinstance(parsed, list) else [tags]
        except ValueError:
            tags = tags.split(",")                    # "python, docs" -> ["python", " docs"]
    return [str(t).strip() for t in (tags or []) if str(t).strip()]


def create_bookmark(title: str, url: str, tags: list[str] | None = None, note: str | None = None) -> str:
    """Save a new bookmark for the user.

    Args:
        title: Short title for the bookmark.
        url: The full URL, starting with http:// or https://.
        tags: Optional list of tag names, e.g. ["python", "docs"].
        note: Optional free-text note. Omit it unless the user gave one.

    Returns:
        JSON with the saved bookmark (id, title, url, tags).
    """
    tags = _normalize_tags(tags)
    b = _request("POST", "/bookmarks", json={"title": title, "url": url, "tags": tags or [], "note": note})
    return json.dumps(_summarize(b))


def delete_bookmark(bookmark_id: int) -> str:
    """Permanently delete one of the user's bookmarks. The user will be asked to approve this.

    Args:
        bookmark_id: The numeric id of the bookmark to delete. Always get it from
            list_bookmarks first; never guess an id.

    Returns:
        A confirmation message.
    """
    _request("DELETE", f"/bookmarks/{int(bookmark_id)}")
    return f"Deleted bookmark {int(bookmark_id)}."