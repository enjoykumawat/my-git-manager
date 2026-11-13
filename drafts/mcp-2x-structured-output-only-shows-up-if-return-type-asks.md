---
title: MCP 2.x's Structured Output Only Shows Up If Your Return Type Asks for It
published: true
tags: mcp, python, devtools, debugging
---

"MCP Is Dead Simple. And That's Exactly the Problem" has been trending in the MCP tag this week, and it needled me into actually testing a claim I'd been resting on instead of checking: that my own MCP server's tool contracts are simple because the SDK is simple. `my-git-manager`'s `server.py` runs 8 tools through `FastMCP` from `mcp[cli]>=1.28.0,<2.0.0`, a version pin I added back in July specifically because `mcp` 2.x renamed `FastMCP` to `MCPServer` and I didn't want that migration landing on me mid-run. I'd never actually tried the migration. I only knew the reason to avoid it.

So I tried it for real, on one tool, to see what "simple" costs when the SDK grows up.

## What the pin was actually protecting me from

This container happens to have both interpreters: `python3` is 3.11 (no `mcp` on its path at all), and `/usr/local/bin/python3.13` has `mcp` 2.3.0 installed system-wide. Importing the old way under 2.3.0 fails with a message that's unusually direct about what changed:

```
$ /usr/local/bin/python3.13 -c "from mcp.server.fastmcp import FastMCP"
ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x,
where FastMCP was renamed to MCPServer (from mcp.server.mcpserver import
MCPServer) and other APIs changed; see the migration guide...
```

Fine — swap the import, keep the decorator. `get_repo_stats` is one of the simplest tools in `server.py`: one GitHub call, one dict back.

```python
# server.py, as it ships today
@mcp.tool()
def get_repo_stats(repo: str) -> dict:
    """Get stars, forks, watchers, open issues for enjoykumawat/<repo>."""
    r = _gh(f"/repos/{GITHUB_USERNAME}/{repo}")
    return {
        "name": r["name"],
        "stars": r["stargazers_count"],
        "forks": r["forks_count"],
        "watchers": r["watchers_count"],
        "open_issues": r["open_issues_count"],
        "language": r.get("language"),
        "description": r.get("description"),
    }
```

Ported straight across, same decorator name, same `-> dict` annotation:

```python
from mcp.server.mcpserver import MCPServer
mcp2 = MCPServer("developer-presence")

@mcp2.tool()
def get_repo_stats(repo: str) -> dict:
    """Get stars, forks, watchers, open issues for enjoykumawat/<repo>."""
    return {"name": repo, "stars": 42, "forks": 7, "watchers": 3,
            "open_issues": 1, "language": "Python", "description": "test"}
```

That part just works. No warning at registration, no error at call time. I called it in-process the way a real client would, through `await mcp2.call_tool(...)`, and got a clean result back. If I'd stopped there, I'd have written the article the pin's own comment already implied: "the rename is the whole migration cost." It isn't.

## The part that doesn't throw, so you don't notice it

I printed the full result object instead of just trusting that it returned something:

```
type: <class 'mcp_types._types.CallToolResult'>
repr: meta=None content=[TextContent(type='text', text='{\n  "name": "x",...}',
      annotations=None, meta=None)] structured_content=None is_error=False
      result_type='complete'
```

`structured_content=None`. The tool advertises a `dict` return type, the SDK's whole pitch for 2.x includes typed, machine-checkable tool output, and what the client actually gets is the same thing 1.x always gave it: a JSON string inside a `TextContent` block. A client written against the new structured-output contract — the one that reads `structured_content` instead of re-parsing `content[0].text` — gets `None` and has to fall back to string parsing anyway, silently, with nothing in the response telling it why.

I checked whether this was specific to my test fixture or a property of the annotation itself, by registering two versions of the same tool side by side — one with `-> dict`, one with a `TypedDict`:

```python
from typing import TypedDict

@mcp2.tool()
def get_repo_stats_dict(repo: str) -> dict:
    """bare dict annotation, same as every real tool in server.py"""
    return {"name": repo, "stars": 42}

class RepoStats(TypedDict):
    name: str
    stars: int

@mcp2.tool()
def get_repo_stats_typed(repo: str) -> RepoStats:
    """TypedDict annotation"""
    return {"name": repo, "stars": 42}
```

Listing both tools' schemas makes the gap visible before you even call anything:

```
TOOL: get_repo_stats_dict
  outputSchema: None
TOOL: get_repo_stats_typed
  outputSchema: {'properties': {'name': {...}, 'stars': {...}},
                 'required': ['name', 'stars'], 'title': 'RepoStats', ...}
```

And calling them confirms it end to end:

```
bare dict -> structured_content: None
TypedDict -> structured_content: {'name': 'x', 'stars': 42}
```

Same function body. Same decorator. The only difference is whether the return annotation is a shape the SDK can turn into a JSON Schema (`TypedDict`, a dataclass, a Pydantic model) versus a shape it can't (a bare `dict`, which could contain anything). `dict` isn't rejected, doesn't warn, doesn't degrade loudly — it just quietly opts the tool out of the feature the major version bump was largely about.

Every one of `server.py`'s 8 tools is annotated `-> dict` or `-> list`. Under 1.x that was a style choice with zero functional consequence — FastMCP never had structured output to opt into. Under 2.x, with nothing else changed, it becomes a silent decision: none of my tools would produce `structured_content`, and nothing in my own code or `server.py --selftest` would ever tell me that, because the tool still "works" by every test I had.

## A second thing I only found because I stopped assuming camelCase

While reading the schema dicts above, my first script crashed on `t.inputSchema`:

```
AttributeError: 'Tool' object has no attribute 'inputSchema'.
Did you mean: 'input_schema'?
```

The 1.x `Tool` model used the camelCase field names the MCP wire protocol itself uses (`inputSchema`). In 2.3.0 the Python-side model exposes `input_schema`/`output_schema` — snake_case, Pythonic, and a silent rename if anything in `server.py` or a client ever introspected a `Tool` object's attributes directly instead of going through `list_tools()`'s serialized output. Nothing in this repo does that today, so it's not a live bug — but it's a second migration cost the "FastMCP renamed to MCPServer" headline doesn't mention, and I'd never have hit it without actually constructing a `Tool` and reading its fields.

## What I'm doing with this

Not upgrading. The `<2.0.0` pin stays — `server.py`'s tools return `dict`/`list` throughout, and converting all 8 to `TypedDict`s just to get `structured_content` is a real, scoped piece of work, not a side effect of bumping a version number. But I'm no longer carrying the pin's comment as "FastMCP got renamed, that's why we're stuck on 1.x." The real reason is narrower and more useful: 1.x never offered structured output, so nothing here was ever built with a return-type contract in mind, and that gap would stay invisible under 2.x too — not as an error, as a field that's quietly `None`.

If you're holding a version pin for a reason you read in a bug note and never re-tested, the cheap move is the one I did here: port one function, call it the way a real client would, and read the whole response object instead of checking that it didn't throw.
