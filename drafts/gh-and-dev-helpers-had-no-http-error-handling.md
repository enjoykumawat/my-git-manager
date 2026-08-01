---
title: My MCP Server's Two API Helpers Had Zero except Blocks. Every Bad Call Crashed With a Raw urllib Traceback.
published: true
tags: mcp, python, debugging, devtools
---

I've spent the last few weeks hardening one function in my MCP server's `claude -p` wrapper. First a timeout fix. Then it turned out the timeout fix didn't cover a non-zero exit code. Then it turned out *that* fix still didn't cover a missing binary. Three separate posts, three separate `except` clauses, all on the same six-line `try` block, until `_claude()` finally had a clean, consistent failure path: catch everything plausible, return a string prefixed `ERROR:`, never let a raw exception reach the MCP client.

While going back through the rest of `server.py` to see if that pattern had actually spread anywhere else, I found the two functions that call an external API on almost every tool invocation — `_gh()` for GitHub, `_dev()` for DEV.to — had never gotten it at all. Zero `try`, zero `except`, in either one.

## What was actually there

```python
def _gh(path, method="GET", data=None):
    if method != "GET":
        raise ValueError(f"_gh is read-only — got method={method!r}")
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Authorization", f"token {os.environ['GITHUB_TOKEN']}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _dev(path, method="GET", data=None):
    req = urllib.request.Request(f"https://dev.to/api{path}", method=method)
    req.add_header("api-key", os.environ["DEV_TO_API"])
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", _DEV_UA)
    if data:
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())
```

Every one of this server's tools except `generate_commit_message` goes through one of these two functions: `list_articles`, `create_article`, `update_article`, `get_article_stats`, `get_github_profile`, `list_repos`, `get_repo_stats`. Seven tools, one shared blind spot. A wrong `article_id` on `update_article` gets a 404. An expired `GITHUB_TOKEN` gets a 401. Too many tags on `create_article` gets a 422. A burst of calls gets a 429. `urllib.request.urlopen` turns every one of those into an `HTTPError` exception, and with no `except` anywhere in either function, it just propagates straight out.

I checked what that actually looks like on the wire, since "propagates out" undersells it if you haven't watched an MCP client eat a stack trace. Stubbed `urlopen` to always raise a 404 and called the tools directly:

```
=== calling update_article(article_id=999999) ===
UNCAUGHT HTTPError propagated to caller: <HTTPError 404: 'Not Found'>
=== calling get_repo_stats('doesnotexist') ===
UNCAUGHT HTTPError propagated to caller: <HTTPError 404: 'Not Found'>
```

Compare that to what `_claude()`'s failure path already looks like for the exact same category of problem — an external process/service saying no:

```
'ERROR: claude -p exited 1: boom'
```

One is a string a client can read, log, and maybe retry on. The other is an unhandled exception with a Python traceback in it, which — depending on how forgiving the MCP client's error surface is — an agent calling this tool has to interpret from a stack frame instead of a message.

## Why I hadn't caught this already

The honest answer is that `_claude()` got audited three separate times because it kept visibly failing in ways I could reproduce by hand — run the commit hook, watch it silently produce nothing, dig in. `_gh` and `_dev` never did that, because in normal use they mostly succeed: valid tokens, real article IDs, no rate limiting. The absence of a crash isn't the same as the absence of a bug; it just means nobody happened to pass a bad ID yet. `publish_devto.py`, the standalone script this same repo uses for the actual scheduled publishing runs, already wraps the identical `urlopen()` call in `except urllib.error.HTTPError as e: sys.exit(f"HTTP {e.code}: ...")`. That script gets exercised twice a day by an unattended job that has to produce a clean failure message if something goes wrong, so it earned the error handling early. The MCP tools, invoked interactively from Claude Desktop, never got the same pressure — until a client actually hits one of these paths and the model has to make sense of a traceback instead of a sentence.

## The fix

Same shape as `_claude()`'s convention, adapted to the failure type that's actually possible here — an `HTTPError`, not a timeout or missing binary — and raising instead of returning a string, since these are plain Python functions, not MCP tool endpoints themselves:

```python
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())
except urllib.error.HTTPError as e:
    raise RuntimeError(f"GitHub API error {e.code}: {e.read().decode()[:400]}") from e
```

Same pattern in `_dev()`, with the DEV.to-specific message. Reran the stubbed-404 repro against the fixed code:

```
RuntimeError('DEV.to API error 404: {"error":"not found"}')
RuntimeError('GitHub API error 404: {"message":"Not Found",...}')
```

Still an exception — MCP's own tool-call machinery already turns an unhandled exception into a structured error response back to the client, so I didn't need to reinvent that part. What changed is *what's in it*: an HTTP status code and the actual response body, truncated to 400 characters, instead of a bare `HTTPError` repr with no message payload attached. `e.read()` only works once per response, so I made sure it's read exactly there and nowhere else in the call path.

## What I didn't do

I didn't add retry logic for 429s — `publish_devto.py`'s scheduled-run instructions already handle that at the caller level ("wait 35 seconds and retry"), and duplicating a retry loop inside a helper two callers rely on risks silently doubling wait times if both layers ever retry the same request. I also didn't touch connection-level failures (`URLError` for DNS/timeout-before-response) — those are a different exception class with a different message shape, and I don't have a live repro for them yet, so extending the `except` clause to cover them is a future finding, not something I want to guess the right message format for today.

The bigger lesson, for me, is narrower than "always wrap network calls" — I already knew that in the abstract. It's that a hardening pass on one function doesn't tell you anything about its neighbors just because they look similar. `_claude()` got three fixes because it kept failing loudly. `_gh`/`_dev` needed the same fix and got zero, because nothing had forced the question yet.
