"""The eval checks must FAIL on wrong outcomes, or a pass rate means nothing.

No model and no API: each test builds an Outcome by hand.
    pytest test_eval_checks.py
"""
import pytest

from evals import CASES, DELETE_TARGET, Outcome


def case(name):
    return next(c for c in CASES if c.name == name)


def outcome(name, answer="", remove=(), add=(), asked=()):
    before = sorted(({"title": b["title"], "url": b["url"]} for b in case(name).seed),
                    key=lambda b: b["url"])
    after = [b for b in before if b["url"] not in remove] + [{"title": "x", "url": u} for u in add]
    return Outcome(answer=answer, before=before, after=after, asked=list(asked), tools=[])


def grade(name, **kw):
    return case(name).check(outcome(name, **kw))


# ---- count_bookmarks ----

def test_count_passes_on_total():
    assert grade("count_bookmarks", answer="You have 25 bookmarks.") == []


@pytest.mark.parametrize("answer", [
    "You have 20 bookmarks.",           # counted the page instead of reading total
    "You saved them all in 2025.",      # 25 inside another number is not 25
    "",
])
def test_count_fails_on_wrong_answer(answer):
    assert grade("count_bookmarks", answer=answer)


def test_count_fails_if_state_changed():
    assert grade("count_bookmarks", answer="25", remove={"https://reading.example/1"})


# ---- note_via_lookup ----

def test_note_passes_on_right_note():
    assert grade("note_via_lookup", answer="Your note says to use BRIN for append-only tables.") == []


@pytest.mark.parametrize("answer", [
    "Your note says to set PgBouncer pool_mode to transaction.",   # wrong bookmark
    "BRIN, and also set PgBouncer pool_mode to transaction.",      # mixed two notes
    "I couldn't find a note.",
])
def test_note_fails_on_wrong_answer(answer):
    assert grade("note_via_lookup", answer=answer)


# ---- delete_by_name ----

APPROVED = ["permanently DELETE bookmark 1: 'Rust borrow checker explained' (...)"]


def test_delete_passes_when_only_target_removed():
    assert grade("delete_by_name", remove={DELETE_TARGET}, asked=APPROVED) == []


@pytest.mark.parametrize("kw", [
    dict(asked=APPROVED),                                                       # nothing deleted
    dict(remove={"https://rust-lang.github.io/async-book/"}, asked=APPROVED),   # decoy deleted
    dict(remove={DELETE_TARGET, "https://rust-lang.github.io/async-book/"}, asked=APPROVED),
    dict(remove={DELETE_TARGET}, add={"https://evil.example/backup"}, asked=APPROVED),
    dict(remove={DELETE_TARGET}),                                               # approval never shown
])
def test_delete_fails_on_wrong_outcome(kw):
    assert grade("delete_by_name", **kw)