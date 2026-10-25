# Eval baseline — agent-lab bookmark agent

Recorded 2026-10-25. Harness: `evals.py` (step 1, capability cases).

## Setup

- Agent: `agent.py` tool loop, MAX_STEPS=6, num_ctx=16384, Ollama default temperature
- Models: gemma4:26b (main), llama3.1:8b (stress tester), Ollama on Windows GPU, Z13 Flow
- Each run: fresh API subprocess on an empty SQLite DB (port 8001), seeded per case
- Scripted human approves every request (rubber stamp), so wrong writes really happen
- Grading on outcomes: API state before/after, approval prompts shown, final answer
  only for read-only questions

## Cases

| case | prompt | trap |
|---|---|---|
| count_bookmarks | How many bookmarks do I have? | 25 seeded, list returns 20 per page; must read `total` |
| note_via_lookup | What did I write in the note on my Postgres indexing bookmark? | note only via get_bookmark; a second Postgres bookmark has a different note |
| delete_by_name | Delete my bookmark about the Rust borrow checker. | decoy "Rust async book"; only the target may be removed |

## Results

### gemma4:26b

| version | count | note | delete | median s (c/n/d) |
|---|---|---|---|---|
| before Fix 1 | 10/10 | 10/10 | 10/10 | 9.3 / 4.6 / 5.9 |
| after Fix 1 | TODO | TODO | TODO | TODO |

Always the minimal tool path: 1 call for count, 2 for note and delete.

### llama3.1:8b (runs pooled by code version)

| version | runs | count | note | delete |
|---|---|---|---|---|
| before Fix 1 | 2 | 17/20 | 8/20 | 2/20 |
| after Fix 1 | 2 | 19/20 | 11/20 | 3/20 |

Median 1.0–3.6 s per run, roughly 3x faster than gemma.

Variance note: identical code scored 0/10 and 3/10 on delete in back-to-back runs.
Differences at N=10 under about 3/10 are noise, so runs are pooled by code version
before comparing.

## Failure analysis (llama, run 2026-10-25 15:33, 16 failures)

1. **Placeholder or invented ids (11).** First call is get_bookmark with an id like
   "the id of the Postgres indexing bookmark", "list_bookmarks", or 123. The model
   knows the plan (list, then get) but writes the plan into the argument.
   Bucket: model, made worse by agent code (raw Python `int()` errors with no next step).
2. **Stops after one successful step (5).** Delete: list returns exactly the target,
   then the model answers or asks for confirmation instead of calling delete.
   Note: after a helpful 404, it lists, then stops before get_bookmark.
   Bucket: model.
3. **Misreads `total` (2).** Result says total 25; answer says 20. Bucket: model.

No failures were grader errors (checked: every failing answer was actually wrong).

## Changes

### Fix 1: actionable errors for bad or missing ids

`_require_id()` in bookmark_tools.py, used by get_bookmark, delete_bookmark, and the
read-before-write guard in execute_tool; missing required args are reported before
Python raises TypeError.

- First attempt didn't load: logs still showed the raw `invalid literal for int()`
  error. Lesson: verify a change is live in the logs before measuring it.
- Effect on llama: note 8/20 → 11/20, delete 2/20 → 3/20. Not distinguishable from
  noise. Better errors get llama one step further, then it stops.
- Effect on gemma: TODO
- Kept: correct behavior for any model, and clearer logs.

## Harness validation

- Checker tests: each checker gutted to `return []`; its tests fail (3–5 per checker).
- Deliberate break: TODO (`total` set to `len(data["data"])`; expect count to fail)

## Decisions

- **gemma4:26b is the model for this agent.** Clears every case at 10/10.
- **Stop tuning llama.** Its limit is chaining two tool calls, which error messages
  can't fix. Kept as a stress tester: it exposed raw errors that gemma silently
  recovered from.

## Open questions

- Would a one-step tool (notes returned by list_bookmarks) fix llama's note case,
  and at what cost? It puts every planted note injection into the first result.
- Should delete be a multi-turn case, where the scripted user replies "yes" to a
  text confirmation?

## Reproduce

    export EVAL_API_DIR=... EVAL_API_PYTHON=...
    python evals.py -n 10 --model gemma4:26b
    python evals.py -n 10 --model llama3.1:8b
    # raw results: eval_results/*.jsonl