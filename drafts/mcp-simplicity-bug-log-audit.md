---
title: I Checked How Many of My MCP Server's 53 Logged Bugs Were Actually the Protocol's Fault
published: true
tags: mcp, python, debugging, devtools
---

The MCP tag on dev.to this week has a post arguing that MCP is "dead simple," and that's exactly the problem: a protocol so easy to stand up that people skip the parts that would make it safe. It's a fair argument in the abstract. I've been running a real MCP server in production (well, "production," my own GitHub/DEV.to automation) for five months, and I keep a bug log for every fix I ship to it. So instead of agreeing or disagreeing from the gut, I went and counted.

My server (`server.py` in this repo) is eight `@mcp.tool()`-decorated functions on top of `FastMCP`, talking to the GitHub and DEV.to REST APIs over plain `urllib`. ADR-002 in my project notes picked `FastMCP` specifically because it was the simple option: no raw JSON-RPC, no transport plumbing, just decorate a function and it becomes a tool. That's the exact thing the trending post is suspicious of.

`docs/project_notes/bugs.md` has 53 entries going back to this server's first commit, each with an Issue/Root Cause/Solution/Prevention writeup, because an earlier rule here is "search bugs.md before touching anything, so you don't refix something twice." That log is specific enough that I can actually answer "how much of this was MCP's fault" instead of guessing.

A keyword grep for `fastmcp`, `pydantic`, `mcp.server` across the full entries returns seven hits. Five of those turn out to be false positives: they show up because their *verification* notes mention "FastMCP-stub-on-PYTHONPATH," a technique I use to run `--selftest` without the real `mcp` package installed. That phrase has nothing to do with what broke, it's boilerplate about how I checked the fix. Filtering to the actual root cause named in each entry's own header, not the solution text, drops the count to two.

**Bug one**: FastMCP builds each tool's input schema from the Python type *annotation*, not the default value.

```python
# before: reads as optional to a human, isn't to pydantic
def update_article(article_id: int, title: str = None, ...):
```

A bare `str` annotation with a `None` default schemas as a required string field whose default is `null`, a self-contradicting schema that tells callers `null` is fine and then rejects it. `mcp.call_tool("update_article", {"article_id": 42, "title": None})` raised `Input should be a valid string [type=string_type]` before any of my own guards (confirm gate, staleness check, duplicate-title check) ever ran. Five hardening passes on this exact function missed it, because every one of them called `update_article()` directly as plain Python, which happily accepts `None` as a default, and never went through the real `mcp.call_tool()` path a client actually uses. The fix is just saying what I meant:

```python
def update_article(article_id: int, title: str | None = None,
                    body_markdown: str | None = None,
                    published: bool | None = None, confirm: bool = False,
                    expected_fingerprint: str | None = None) -> dict:
```

**Bug two**: between `mcp` 1.x and 2.x, `FastMCP` got renamed to `MCPServer`, and my pinned `requirements.txt` range (`mcp[cli]>=1.28.0,<2.0.0`) didn't save me from it. A mismatched `pip`/`python3` interpreter pair in this sandbox meant `pip show mcp` reported a compatible version while the interpreter actually running `server.py` had no `mcp` on its `sys.path` at all, and the one that did had 2.x installed anyway. The failure was a bare `ModuleNotFoundError` with no indication any of that was going on:

```python
try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as e:
    if e.name != "mcp":
        raise
    sys.exit(_mcp_import_error_message(sys.executable, sys.version.split()[0]))
```

`_mcp_import_error_message()` names the interpreter and version actually running, and tells you to diff it against what `pip show mcp` claims. It only catches `e.name == "mcp"`; a deeper failure like the 2.x rename re-raises unchanged, because that one already comes with its own actionable message (the library's own migration-guide URL).

So: 2 out of 53. That's the honest MCP-shaped slice. Here's where the other 51 actually came from, bucketed by what the header of each entry actually blames, not what file it happened to touch:

- **Git hooks install/path arithmetic** (5): `hooks/prepare-commit-msg` not being executable, `$0`-relative path math breaking across two different documented install methods, the install script itself not surviving a fresh container.
- **Credential/env parsing** (6): bare `os.environ["DEV_TO_API"]` `KeyError`s in three different scripts that each got the fix independently and at different times, `.env` lines with quotes or spaces around `=` silently not loading.
- **Comment-thread walking** (6): `reply_comments.py` only checking thread-root comments or one level of nesting, missing branches a real conversation produces.
- **Claude subprocess handling** (4): `--safe-mode` not actually isolating the ambient environment, `GITHUB_TOKEN`/`DEV_TO_API` leaking into a `claude -p` child that had no business seeing them.
- **Duplicate-check/race windows** (4), **attribution regex** (3), **doc-drift checkers** (3), **pagination** (2), **HTTP client error handling** (3): the rest, roughly 15 more, were one-off, things like a detached-HEAD checkout, a username underscore mismatch between GitHub and DEV.to, a missing OAuth scope.

None of that is MCP's fault. It's the fault of writing a CLI tool, a comment-reply bot, and a publishing pipeline in Python with no third-party HTTP library and a home-rolled `--selftest` instead of pytest, decisions I made independently of picking FastMCP, for the same reason I picked FastMCP: keep the dependency surface small. The "dead simple" framing in the trending post isn't wrong about MCP servers in general, it's just not what actually bit me. What bit me was the ordinary stuff every stdlib-only Python script accumulates, the stuff that would be exactly as present if this were a Flask app or a bare CLI with no protocol involved at all.

If you're trying to decide whether to worry about MCP's simplicity specifically, the test I'd suggest isn't "is MCP simple" (obviously yes), it's the one this count forced on me: go to your own bug tracker, grep it for your framework's name, and see how much of it is actually your framework's fault versus everything you'd have had to build correctly anyway. For me that number was 2 out of 53, and the other 51 were waiting in the code I'd have written regardless of which protocol decorator sat on top of it.
