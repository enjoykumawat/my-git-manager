---
title: One Function in My MCP Server Enforces Read-Only in Code, Not Just Token Scope
published: true
tags: mcp, security, python, devtools
---

There's a question going around dev.to right now about MCP servers and trust: once you've approved a tool, what's actually stopping it from doing more than you think it does? Most of the answers I've seen focus on the install step, vetting a server before you ever run it. I wanted to check something narrower and more boring: inside a server I already wrote myself, is "it can't write" actually enforced, or is it just true by convention because none of the tools happen to call a write method today?

I run a small MCP server called `developer-presence`: eight tools, two upstream APIs (GitHub and DEV.to). Three GitHub tools (`get_github_profile`, `list_repos`, `get_repo_stats`) are read-only by intent. Two DEV.to tools (`create_article`, `update_article`) have to write, that's the whole point of them. So I went and read the two helper functions both sides route through, `_gh()` and `_dev()`, and compared what actually stops a bad call.

Here's `_gh()`, trimmed to the part that matters:

```python
def _gh(path, method="GET", data=None):
    if method != "GET":
        raise ValueError(f"_gh is read-only — got method={method!r}")
    if data is not None:
        raise ValueError("_gh is read-only — got a data payload on a GET call")
    token = os.environ.get("GITHUB_TOKEN")
    ...
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Authorization", f"token {token}")
```

That first `if` is the whole security story for the GitHub side of this server. `GITHUB_TOKEN` is scoped `repo, user` in the actual GitHub settings, full write access, because I also use that same token for other scripts in this repo that do need to push commits. If I relied on token scope alone to express "these three tools are read-only," that claim would be false the instant someone (a future me, an agent editing this file, a bad merge) changed one call site from `method="GET"` to `method="POST"`. Instead, `_gh()` itself raises before the request ever leaves the process, regardless of what the token could do. I verified this is live, not aspirational, by grepping every call site:

```
$ grep -n '_gh(' server.py
_gh(f"/users/{GITHUB_USERNAME}")
_gh(f"/repos/{GITHUB_USERNAME}/{repo}")
```

Two call sites, both default `method="GET"`, no path anywhere passes a different verb. The guard has nothing to catch today, which is exactly why it's worth having. It's not protecting against a bug that exists; it's there so that the bug can't exist later without a loud, immediate `ValueError` instead of a silent write nobody meant to allow.

Now the other helper, `_dev()`:

```python
def _dev(path, method="GET", data=None):
    key = os.environ.get("DEV_TO_API")
    ...
    req = urllib.request.Request(f"https://dev.to/api{path}", method=method)
    req.add_header("api-key", key)
    if data:
        req.data = json.dumps(data).encode()
```

No method check. No denylist. Whatever verb a caller passes goes straight to the request. That's not an oversight: `create_article` and `update_article` have to be able to POST and PUT, so a hard "no writes" gate here would just break the server. But it means the write boundary for the DEV.to side can't live in `_dev()` the way it does in `_gh()`. It has to live somewhere narrower: in each tool that calls `_dev()` with a non-GET verb.

That's where `update_article` earns its keep. It's not just "PUT the new fields," it requires an explicit `confirm=True` flag, fetches the current article first to check a caller-supplied fingerprint against what's actually live (so you can't blindly overwrite something that changed since you last read it), and refuses a payload with no fields set. None of that is enforced by `_dev()`. `_dev()` would happily PUT whatever it's handed. The guard rail is one layer up, hand-written per tool, which means it's exactly as strong as whoever wrote that tool remembered to make it, and no stronger.

There's a second kind of boundary I didn't write at all: DEV.to's own API just doesn't let a normal account create comments (`POST /api/comments` returns 404) or create reactions (`POST /api/reactions` returns 401 even with a valid key). I only know this because I tried it and logged the response, not because I read it anywhere. That's an external limit, not something `_dev()` or any tool in my server enforces. If DEV.to changed that behavior tomorrow, nothing here would notice or object.

Putting the three together gives a more honest answer to "what can this MCP server actually do" than the tool list does by itself:

1. **Enforced in code, independent of credentials**: the three GitHub tools, blocked by `_gh()`'s method check regardless of what `GITHUB_TOKEN` is scoped to.
2. **Enforced per-tool, dependent on whoever wrote that tool**: `create_article`/`update_article`'s confirm flag and staleness check. `_dev()` itself places no ceiling on what these tools could do if a future edit skipped the guard.
3. **Enforced by the upstream API, not by me at all**: comments and reactions, a limit I discovered empirically and that could change without my code changing.

If you're auditing your own MCP server against the same question, the useful exercise isn't reading the tool list, it's reading every function that actually forms a request and asking which of these three buckets it falls into. A read-only tool with no code-level denylist is one `method=` typo away from becoming a write tool, and you won't find that by looking at what the server currently does, only by looking at what would stop it from doing something else. The tools that write deserve the opposite scrutiny: don't ask whether the HTTP helper blocks bad calls, ask whether the specific function calling it with a mutating verb has its own gate, because the helper underneath has already told you it won't.
