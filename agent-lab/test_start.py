from pathlib import Path

import agent


def test_startup_failure_shows_the_cause_and_only_this_attempts_log(tmp_path):
    log = tmp_path / "mcp-server.log"
    log.write_text("an older session's noise\n")
    offset = log.stat().st_size                      # where this attempt's output begins
    with log.open("a") as f:
        f.write("bookmarks MCP server: missing environment variables BOOKMARK_USER, BOOKMARK_PASSWORD.\n")
    error = ExceptionGroup("unhandled errors in a TaskGroup", [ConnectionError("Connection closed")])

    message = agent.mcp_error_message(error, log, offset, started=False)

    assert message.startswith("Couldn't start the bookmark tools over MCP")
    assert "Connection closed" in message                       # the unwrapped cause
    assert "missing environment variables" in message           # what the server said
    assert "older session" not in message                       # earlier output excluded
    assert "TaskGroup" not in message                           # no wrapper noise


def test_failure_after_startup_is_worded_differently(tmp_path):
    error = ExceptionGroup("unhandled errors in a TaskGroup", [ConnectionError("Connection closed")])
    message = agent.mcp_error_message(error, tmp_path / "missing.log", 0, started=True)
    assert message.startswith("The MCP connection failed")
    assert "Connection closed" in message