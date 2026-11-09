# tests/test_escape_like.py
from app.search import escape_like  # adjust the import path to your layout


def test_underscore():
    assert escape_like("a_b") == r"a\_b"

def test_percent():
    assert escape_like("100%") == r"100\%"

def test_backslash():
    assert escape_like(r"a\b") == r"a\\b"

def test_backslash_escaped_first():
    # input is backslash + percent
    assert escape_like(r"\%") == r"\\\%"

def test_plain_text_unchanged():
    assert escape_like("Use The Index") == "Use The Index"