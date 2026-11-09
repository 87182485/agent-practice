# app/search.py
def escape_like(q: str) -> str:
    """Make q match literally inside a LIKE pattern that uses ESCAPE '\\'."""
    # TODO: three .replace() calls, chained.
    # Hint: order matters. Escape the backslash FIRST.
    #   If you escape % first ("%" -> "\%") and the backslash second,
    #   the backslash you just added gets doubled ("\\%"), which turns the
    #   % back into a wildcard. test_backslash_escaped_first catches this.
    # Hint: .replace works like JS replaceAll, replacing every occurrence.
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")