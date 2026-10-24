# agent-practice

A learning project in two parts. First a bookmark manager API built with
FastAPI, then an LLM agent that uses that API through tool calls, running on a
local model with [Ollama](https://ollama.com).

```
agent-practice/
├── python-practice/   FastAPI + SQLModel bookmark API with JWT auth
└── agent-lab/         a tool-calling agent that drives the API, plus prompt-injection experiments
```

## python-practice: the bookmark API

A REST API for saving bookmarks, tagging them and grouping them into
collections. Each user only sees their own data.

- **FastAPI** for routing, validation and the interactive docs at `/docs`
- **SQLModel** on SQLite (`bookmarks.db`, created on first start)
- **Auth:** registration, then an OAuth2 password login that returns a JWT. Passwords are hashed with Argon2 via `pwdlib`, and tokens are signed with `PyJWT`.
- **Tests** with pytest, each one running against a fresh in-memory database

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/users` | Register |
| `POST` | `/token` | Log in, get a bearer token |
| `GET` `POST` | `/bookmarks` | List (with `q`, `limit`, `offset`) or create |
| `GET` `PUT` `PATCH` `DELETE` | `/bookmarks/{id}` | Read, replace, update or delete one |
| `GET` `POST` | `/collections` | List or create collections |
| `GET` | `/collections/search?q=` | Search collections |
| `GET` `PATCH` `DELETE` | `/collections/{id}` | Read, update or delete one |
| `POST` | `/collections/{id}/bookmarks/{bookmark_id}` | Add a bookmark to a collection |

Every route except `/users` and `/token` needs a token.
`tests/test_route_audit.py` checks that this stays true.

### Run it

```bash
cd python-practice
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# The app won't start without a signing key. .env is git-ignored.
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" > .env

uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/docs. Register a user with `POST /users`,
click **Authorize**, and log in.

Optional extras:

```bash
python seed.py       # fill the API with sample users and bookmarks (server must be running)
./smoke_test.sh      # end-to-end auth and ownership checks with curl; needs jq and an empty database
pytest               # unit tests, no server needed
```

`python-practice/README.md` has the milestone-by-milestone notes behind the API.
The milestone file names it mentions have since been merged into `main.py`.

## agent-lab: an agent that uses the API

A command-line chat agent that manages your bookmarks by calling the API on your
behalf. It runs entirely on your machine using `llama3.1:8b` through Ollama.

| File | What it is |
|---|---|
| `hello.py` | First contact with the Ollama API: two chat calls and their token counts |
| `interactive_agent.py` | A plain chat loop with history and `/reset`, no tools |
| `bookmark_tools.py` | The tools: `list_bookmarks`, `get_bookmark`, `create_bookmark`, `delete_bookmark`. They log in with credentials from environment variables, which never reach the model. |
| `agent.py` | The agent loop: tool calling, guardrails and prompt-injection defenses |
| `plant_injections.py` | Plants test bookmarks containing prompt-injection attacks, and removes them with `--cleanup` |

### How the agent stays safe

The model is treated as untrusted. The checks live in code, not in the prompt:

- **Human approval for deletes.** The approval prompt describes the bookmark
  by fetching it from the API, so the model can't misdescribe what it's deleting.
- **No guessed ids.** A bookmark can only be deleted after it has appeared in a
  lookup result in the same conversation.
- **Argument hygiene.** Unknown arguments are dropped and the model is told so.
  A call that already failed with the same arguments isn't retried.
  The agent stops after 6 steps.
- **Prompt-injection detection.** Tool results are checked for text that looks
  like instructions to an AI. If any is found, the result is prefixed with a
  warning, and every write (create or delete) needs your approval until `/reset`.
- **Recovering text tool calls.** Small models sometimes write a tool call as
  JSON text instead of making one. These are recovered and still go through all
  the checks above.

The keyword detection is a tripwire, not a wall. `plant_injections.py` includes
a deliberately subtle attack (`SUBTLE_INJECTIONS`) that it can't catch, which is
why the approval and lookup rules don't depend on it.

### Run it

You need [Ollama](https://ollama.com/download) installed, and the bookmark API
running as described above.

```bash
ollama pull llama3.1:8b

cd agent-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# A user for the agent. Create it once with POST /users in the API docs.
export BOOKMARK_USER=agent-user
export BOOKMARK_PASSWORD=choose-a-password
# Optional: BOOKMARK_API (default http://127.0.0.1:8000), AGENT_MODEL (default llama3.1:8b)

python agent.py
```

Try asking `what python bookmarks do I have?` or `save https://docs.python.org as "Python docs"`.
Type `/reset` to clear the conversation, or press Enter on an empty line to quit.

To try the injection tests, run `python plant_injections.py`, then ask the agent
about your bookmarks. Run `python plant_injections.py --cleanup` afterwards.
The planted text is fake attack content aimed at the model. It uses the
reserved `.example` domain and points nowhere.

## Status

This is a personal learning repo, not a maintained product. `agent-lab` has no
tests yet: `test_agent.py` is currently a copy of `agent.py`.
