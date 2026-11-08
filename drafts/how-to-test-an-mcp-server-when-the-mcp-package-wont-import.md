---
title: How to Test an MCP Tool Server When the MCP Package Won't Import
published: true
tags: mcp, python, debugging, devtools
---
My MCP server (`server.py` in the `my-git-manager` repo this comes from) has a `--selftest` block with 60 assertions covering duplicate-title checks, a confirm gate for live edits, staleness detection, and credential-leak prevention. It runs twice a day as part of a scheduled publishing pipeline. And in the sandbox that pipeline actually runs in, `import mcp` fails:

```
$ python3 -c "import mcp"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'mcp'
$ pip show mcp
Name: mcp
Version: 2.3.0
```

`pip` thinks it's installed. Python disagrees. I didn't chase down why the two disagree — a broken venv, a stale `.dist-info` left behind by a partial install, whatever. What matters operationally is that `server.py` opens with `from mcp.server.fastmcp import FastMCP` at module scope, so nothing in the file runs — not the tool functions, not the 60-assertion selftest block — until that import succeeds. No test harness, no CI, nothing, until that line resolves.

The fix I actually use is a stub package placed earlier on `PYTHONPATH` than the real one would be. It's not a mocking library, not `unittest.mock.patch`, just a directory tree that satisfies the import:

```
stub_mcp/
  mcp/__init__.py
  mcp/server/__init__.py
  mcp/server/fastmcp.py
```

And `fastmcp.py` is the whole stub:

```python
class FastMCP:
    def __init__(self, name):
        self.name = name
    def tool(self):
        def deco(fn):
            return fn
        return deco
```

That's it. `FastMCP("developer-presence")` returns an object with a `.tool()` method, and `.tool()` returns a decorator that hands the function straight back, unmodified. Every `@mcp.tool()` in `server.py` becomes a no-op decoration, and the plain Python functions underneath — `create_article`, `update_article`, `_dev`, all of it — are exactly as callable as they'd be without the decorator at all.

Running it:

```
PYTHONPATH=/path/to/stub_mcp python3 server.py --selftest
```

I ran this for real against the live file, not a cleaned-up reproduction. The import succeeded, and the selftest block got from line 630 straight through to line 1078 — 51 of the file's 60 top-level `assert` statements — with no failures. That's the duplicate-published-title guard, the confirm-gate-on-live-writes logic, the staleness check, the `GITHUB_TOKEN`/`DEV_TO_API` subprocess-environment exclusion, the article-update audit log — all genuine `server.py` business logic, exercised with zero network calls and zero dependency on whether `pip`'s metadata matches reality.

Then it broke, exactly where I expected it to:

```
await mcp.call_tool("update_article", {"article_id": 42, "title": None})
AttributeError: 'FastMCP' object has no attribute 'call_tool'
```

My stub's `FastMCP` only has `__init__` and `.tool()` — I never gave it `.call_tool()`, because `.call_tool()` isn't a convenience method, it's the thing that runs the real SDK's pydantic-based argument validation before your function body ever sees the call. That's the exact mechanism behind one of this repo's actual bugs: `title: str = None` (not `str | None = None`) gets schema'd by FastMCP as a required string field with a null default, so a real tool call with `title: None` gets rejected by pydantic before `update_article`'s own "treat None as unchanged" logic ever runs. I could extend my stub to fake `call_tool()` too, but at that point I'd be hand-rolling pydantic's validation semantics in a toy class — which is just a slower way of writing a bug, not a way of catching one. The 9 assertions past line 1078 test that specific validation path, and they need the real package, correctly, on purpose.

That split is the actual lesson, not "write a stub." A hand-rolled stub satisfying an import gets you everything that's genuinely your code's logic — which, by assertion count here, was 85% of this file's selftest coverage. It gets you nothing for behavior that originates in the framework itself: schema generation, validation error shapes, anything where the real dependency's behavior *is* the thing under test. If I'd skipped the real-package run entirely and trusted the stub for everything, that one pydantic-shaped bug would have stayed invisible — `server.py --selftest` would print `selftest ok` against logic that was never actually exercised.

The practical rule I apply now, in Python terms:

```python
# stub-safe: methods that are pure extensions of your own code
class FastMCP:
    def __init__(self, name): self.name = name
    def tool(self):
        def deco(fn): return fn
        return deco

# NOT stub-safe without real risk: anything that's actually the SDK
# doing SDK things — schema generation, call-time validation,
# transport framing. Faking call_tool() here means faking pydantic.
```

If a method on the thing you're stubbing is just structure (a registry, a decorator, a name), stub it and move on — you get fast, dependency-free coverage of your own code for free. If a method is where the framework's actual contract lives, don't stub it; either install the real thing for that one test, or write the assertion to explicitly skip when only the stub is available, so a half-covered selftest run can't quietly claim full coverage. `server.py`'s own selftest block already draws that line correctly — the stub gets you to line 1078, and the 9 assertions after it are flagged, in a comment right above them, as needing the real `mcp` package. The stub isn't wrong for stopping where it does; the only mistake would be not knowing where that is.
