"""The bookmark tools as an MCP server. API credentials stay in this process.

    mcp run server.py          # stdio, for a host or the Inspector

Error contract (verified against mcp 2.3.0):
- Only ToolError messages reach the client. Any other exception is treated as a
  crash: the client sees just "Error executing tool <name>", and the traceback
  goes to this server's log.
- bookmark_tools raises ValueError for messages written FOR THE MODEL (404
  guidance, conflicts, bad ids), so those, and only those, become ToolError.
  Anything else (API down, missing credentials) stays a masked crash: internal
  details don't belong in the model's context.
- Arguments that fail the input schema (e.g. a string for bookmark_id) are
  rejected by the SDK before the tool runs, with a pydantic validation message.
- Unknown extra arguments are silently ignored, so reporting them is the host's job.

Tool definitions: by default the SDK puts the whole raw docstring in the description and
leaves parameters undescribed. Direct mode (ollama) gives the summary as the description
and each "Args:" line to its parameter, so describe_tool() does the same here: the model
reads the same definitions in both modes. test_mcp.py checks this.
"""
import functools
import inspect
import os
import sys
from typing import Annotated

from pydantic import Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from bookmark_tools import create_bookmark, delete_bookmark, get_bookmark, list_bookmarks

missing = [v for v in ("BOOKMARK_USER", "BOOKMARK_PASSWORD") if not os.environ.get(v)]
if missing:
    sys.exit(f"bookmarks MCP server: missing environment variables {', '.join(missing)}. "
             "The host must pass them to this process explicitly.")

mcp = MCPServer("bookmarks")


def model_facing_errors(fn):
    """Let bookmark_tools' ValueError messages reach the model as ToolError."""
    @functools.wraps(fn)                 # keeps name, docstring and signature, so the schema is unchanged
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            raise ToolError(str(e)) from e
    return wrapper


def parse_docstring(fn) -> tuple[str, dict[str, str]]:
    """Google-style docstring -> (summary, {param: description}); continuation lines joined."""
    summary, params, section, current = [], {}, None, None
    for line in (inspect.getdoc(fn) or "").splitlines():
        stripped = line.strip()
        if stripped.endswith(":") and not line.startswith(" "):       # "Args:", "Returns:"
            section, current = stripped[:-1], None
        elif section is None:
            if stripped:
                summary.append(stripped)
        elif section == "Args" and stripped:
            name, sep, text = stripped.partition(":")
            if sep and line.startswith("    ") and not line.startswith("     ") and name.isidentifier():
                current, params[name] = name, text.strip()
            elif current:
                params[current] += " " + stripped
    return " ".join(summary), params


def describe_tool(fn):
    """The tool as the model should see it: summary as description, Args on their parameters."""
    summary, arg_docs = parse_docstring(fn)
    wrapper = model_facing_errors(fn)
    sig = inspect.signature(fn)
    params = [p.replace(annotation=Annotated[p.annotation, Field(description=arg_docs[p.name])])
              if p.name in arg_docs else p for p in sig.parameters.values()]
    wrapper.__signature__ = sig.replace(parameters=params)
    wrapper.__annotations__ = {p.name: p.annotation for p in params} | {"return": sig.return_annotation}
    return summary, wrapper


for tool in (list_bookmarks, get_bookmark, create_bookmark, delete_bookmark):
    description, wrapped = describe_tool(tool)
    mcp.tool(description=description)(wrapped)