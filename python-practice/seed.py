"""
Seed the bookmark API with realistic data — THROUGH THE API, not the database.

Going through HTTP means the seed exercises your real code paths (password
hashing, tag lookup-or-create, ownership stamping) and only depends on your
endpoint contract, not on what your models are called internally.

Usage (server running in another terminal):
    rm bookmarks.db            # optional: start clean
    uvicorn milestone_4:app --reload
    python seed.py

Needs httpx (you'll want it for milestone 5's TestClient anyway):
    pip install httpx

Safe to re-run: existing users are logged into rather than recreated, and
duplicate bookmarks come back 409 and are counted as "skipped".

If your API differs from what this assumes, edit the CONTRACT section below.
"""

import sys

import httpx

# ---- CONTRACT: adjust if your endpoints differ -------------------------------
API = "http://127.0.0.1:8000"
REGISTER = "/users"          # POST json {"username", "password"}
LOGIN = "/token"             # POST form {"username", "password"}
BOOKMARKS = "/bookmarks"     # POST json {"title", "url", "note", "tags": [str]}

# ---- DATA ---------------------------------------------------------------------
# Throwaway dev passwords — never reuse a real one here.
USERS = {
    "alice": "alice-dev-pw",
    "bob": "bob-dev-pw",
    "carol": "carol-dev-pw",
}

# Real, recognisable links so the data is readable in /docs.
CURATED = [
    ("FastAPI docs", "https://fastapi.tiangolo.com", ["python", "fastapi", "docs"]),
    ("SQLModel docs", "https://sqlmodel.tiangolo.com", ["python", "database", "docs"]),
    ("SQLAlchemy ORM", "https://docs.sqlalchemy.org", ["python", "database", "reference"]),
    ("Pydantic", "https://docs.pydantic.dev", ["python", "docs"]),
    ("Python stdlib", "https://docs.python.org/3/library/", ["python", "reference"]),
    ("Real Python", "https://realpython.com", ["python", "tutorial"]),
    ("OWASP Top Ten", "https://owasp.org/www-project-top-ten/", ["security", "reading-list"]),
    ("jwt.io", "https://jwt.io", ["security", "reference"]),
    ("MDN Web Docs", "https://developer.mozilla.org", ["frontend", "javascript", "reference"]),
    ("React docs", "https://react.dev", ["frontend", "javascript", "docs"]),
    ("TypeScript handbook", "https://www.typescriptlang.org/docs/", ["frontend", "typescript", "docs"]),
    ("PostgreSQL docs", "https://www.postgresql.org/docs/", ["database", "reference"]),
    ("SQLite docs", "https://www.sqlite.org/docs.html", ["database", "reference"]),
    ("Hacker News", "https://news.ycombinator.com", ["reading-list"]),
]

TAG_POOL = ["python", "fastapi", "database", "security", "frontend",
            "tutorial", "reference", "reading-list", "javascript", "docs"]


def filler(n: int, prefix: str):
    """Generated bookmarks for VOLUME — enough rows that N+1 is visible in logs."""
    for i in range(n):
        tags = [TAG_POOL[i % len(TAG_POOL)], TAG_POOL[(i * 3 + 1) % len(TAG_POOL)]]
        yield (f"{prefix} article {i}", f"https://example.com/{prefix}/{i}", tags)


# Per-user plan. Bob deliberately shares several URLs with Alice: that must
# SUCCEED, because uniqueness is per user (user_id, url), not global.
# Everyone shares tag names, which shows whether your tags are global or per-user.
PLAN = {
    "alice": CURATED + list(filler(30, "alice")),   # ~44 rows: big enough for N+1
    "bob": CURATED[:5] + list(filler(5, "bob")),    # overlaps alice's URLs
    "carol": CURATED[6:9],                          # a small set
}


# ---- RUN ----------------------------------------------------------------------
def ensure_user(client: httpx.Client, username: str, password: str) -> str:
    r = client.post(REGISTER, json={"username": username, "password": password})
    if r.status_code == 201:
        status = "created"
    elif r.status_code == 409:
        status = "already existed"
    else:
        sys.exit(f"register {username}: unexpected {r.status_code} {r.text}")

    # Form-encoded, NOT json — OAuth2's password flow.
    r = client.post(LOGIN, data={"username": username, "password": password})
    if r.status_code != 200:
        sys.exit(f"login {username}: {r.status_code} {r.text}")
    print(f"  {username:6} {status}, logged in")
    return r.json()["access_token"]


def seed_bookmarks(client: httpx.Client, username: str, token: str, rows) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    created = skipped = 0
    no_tags_field = tags_lost = 0
    for title, url, tags in rows:
        r = client.post(BOOKMARKS, headers=headers,
                        json={"title": title, "url": url, "note": None, "tags": tags})
        if r.status_code == 201:
            created += 1
            # A 201 only proves the bookmark was created — not that the tags
            # survived. Pydantic silently drops fields a model doesn't declare,
            # so check what actually came back.
            returned = r.json().get("tags")
            if returned is None:
                no_tags_field += 1
            else:
                got = {(t["name"] if isinstance(t, dict) else t).lower() for t in returned}
                if not {t.lower() for t in tags} <= got:
                    tags_lost += 1
        elif r.status_code == 409:
            skipped += 1
        else:
            sys.exit(f"{username} POST {url}: unexpected {r.status_code} {r.text}")

    total = client.get(BOOKMARKS, headers=headers, params={"limit": 1}).json().get("total")
    print(f"  {username:6} created {created:3d}, skipped {skipped:3d}  -> API reports total={total}")
    if no_tags_field:
        print(f"         WARNING: {no_tags_field} responses had no 'tags' field. Can't confirm tags "
              f"were stored — add `tags: list[TagRead]` to BookmarkRead.")
    if tags_lost:
        print(f"         WARNING: {tags_lost} bookmarks came back without the tags that were sent. "
              f"Check BookmarkCreate declares `tags` and the create endpoint attaches them.")


def main() -> None:
    try:
        with httpx.Client(base_url=API, timeout=10) as client:
            print("Users:")
            tokens = {u: ensure_user(client, u, pw) for u, pw in USERS.items()}
            print("Bookmarks:")
            for user, rows in PLAN.items():
                seed_bookmarks(client, user, tokens[user], rows)
    except httpx.ConnectError:
        sys.exit(f"Can't reach {API} — is uvicorn running?")
    print("\nDone. Log in as alice / alice-dev-pw in /docs to explore.")


if __name__ == "__main__":
    main()