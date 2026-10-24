# Bookmark Manager API — learning project

A hands-on path from basic Python to real FastAPI competence. Each milestone is
a self-contained runnable file. Run them one at a time and actually poke at
`/docs`.

Verified against **FastAPI 0.141.1** and **SQLModel 0.0.42** (Sept 2026).

## Setup on a new machine

```bash
git clone <your-repo>          # or copy the folder across
cd bookmark-api

python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Note: use `python3` for the venv line if plain `python` isn't on your PATH.
Once the venv is **activated**, `python` points at the venv's interpreter, so
everything after that just works.

## Milestone 0 — types = validation = docs

```bash
uvicorn milestone_0:app --reload
```

Open http://127.0.0.1:8000/docs and POST to `/echo`. Then deliberately break
it: omit `url`, or send `"url": "banana"`. Watch it get rejected with a clear
error you never had to write. Your type hints *are* the validation *are* the
docs — that's the whole mental model.

## Milestone 1 — CRUD with fake storage

```bash
uvicorn milestone_1:app --reload
```

A plain dict stands in for a database, so routing and validation can be learned
without persistence complexity. Includes pagination, PATCH, and duplicate-URL
rejection.

Ideas to carry forward:

- `BookmarkCreate` (what the client sends) and `BookmarkRead` (what the server
  returns) are separate on purpose. The client never sets `id` or `created_at`.
- PATCH needs its own all-optional model, plus
  `model_dump(exclude_unset=True)`. Not `exclude_none` — that would make it
  impossible to ever clear a field.
- `total` is counted *before* slicing, or it just reports the page size.
- `Annotated[int, Query(ge=1, le=100)] = 10` keeps the default a real value, so
  a `Query` object can't leak into the function body.
- `_url_taken` has a **race condition** and cannot be fixed in Python. That's
  the setup for milestone 2.

## Milestone 2 — a real database (SQLModel + SQLite)

```bash
uvicorn milestone_2:app --reload
```

**The test that matters:** create a bookmark, Ctrl-C the server, restart it,
`GET /bookmarks`. The data is still there, in `bookmarks.db`. That's the
milestone in one observation.

**The constraint test** (4 steps, proves the race condition is gone):

1. POST a URL → 201
2. POST the same URL again → 409
3. PATCH that bookmark's *title only* → 200 (self-exclusion, with zero
   `exclude_id` logic)
4. PATCH a *different* bookmark to that URL → 409

What's new:

- **Engine vs session.** Engine is expensive and built once per app at module
  level; the session is cheap and built once per request. Never flip that.
- **`Depends(get_session)`** — the function, not `get_session()`. FastAPI calls
  it itself, once per request. Passing the result breaks the per-request
  lifecycle (and raises at import).
- **`yield` splits setup from teardown**, in `get_session` (per request) and in
  `lifespan` (per process). Same shape, two scopes.
- **`select(Bookmark)` builds the statement; `session.exec()` runs it.** The
  model says *what*, the session says *how*. Never pass `session` to `select`.
- **`unique=True` on `url`** replaces `_url_taken`, the `exclude_id`
  bookkeeping, *and* the race condition — enforced atomically by the database.
  You insert and catch `IntegrityError` instead of checking first.
- **Pagination moved into SQL.** `.offset()/.limit()` mean the database returns
  ten rows instead of Python loading a million and slicing.

Caveat: `SQLModel.metadata.create_all` only creates *missing* tables. Change a
model and it silently does nothing. While learning, delete `bookmarks.db` and
restart. Real projects use Alembic for migrations.

## What's next — milestone 3: users and auth

Password hashing, JWT, and a `get_current_user` dependency that itself depends
on `get_session` — dependencies composing with dependencies is where FastAPI
really clicks.

Library note, checked Sept 2026: FastAPI's official tutorial now uses
**pwdlib** (defaults to Argon2) and **PyJWT**. Many current-looking blog posts
still teach `passlib` + `python-jose`; that pairing is the older advice. Also
needs `python-multipart`, because the OAuth2 password flow posts form data.

Also worth planning: `url` is currently globally unique, but once bookmarks
belong to users, two people should be able to save the same link. That becomes
a composite unique constraint on `(user_id, url)`.

## Version drift

SQLModel is pre-1.0 and moves faster than most. If an import or method doesn't
match these files, the real error message is ground truth — check the official
docs for the version you actually installed.
