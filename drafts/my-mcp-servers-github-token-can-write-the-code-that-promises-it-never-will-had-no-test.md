---
title: My MCP Server's GitHub Token Can Write. The Code That Promises It Never Will Had No Test.
published: true
tags: security, mcp, python, ai
---

My MCP server (`developer-presence`, the one that lets Claude check my GitHub profile and manage my DEV.to posts) has exactly three GitHub tools: `get_github_profile`, `list_repos`, `get_repo_stats`. All three read data. None of them create, update, or delete anything.

The `GITHUB_TOKEN` behind them isn't scoped that way. My own `key_facts.md` says it plainly:

```
Token scopes needed: `repo`, `user` — add `delete_repo` if repo deletion
via API is required, add `workflow` if you'll ever push a branch that
pulls in upstream `.github/workflows/*.yml` changes
```

`repo` is GitHub's full-control scope — it can push commits, edit files, change repo settings, everything short of an outright delete. I gave it that scope because other parts of this project (the git-writing side, not the MCP server) need it. The MCP server just inherits the same `.env` file and, with it, the same token.

So every call this server's GitHub helper makes is running with write credentials it never intends to use. The only thing standing between "never intends to" and "actually can't" is one function.

## The guard

```python
def _gh(path, method="GET", data=None):
    # No GitHub tool in this server writes anything — GITHUB_TOKEN is scoped
    # `repo, user` (full write access, see key_facts.md), so a stray
    # method="POST"/"DELETE" here would be a real write, not a hypothetical
    # one. Enforced, not just true by convention. See bugs.md 2026-07-30.
    if method != "GET":
        raise ValueError(f"_gh is read-only — got method={method!r}")
    if data is not None:
        raise ValueError("_gh is read-only — got a data payload on a GET call")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set — add it to .env next to server.py")
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Authorization", f"token {token}")
    ...
```

Every one of the three GitHub tools routes through `_gh()`, and none of them ever pass `method=` or `data=`. That's the entire enforcement: a single `if` that turns "this file happens to only call GET" into "this file cannot call anything but GET." I added that guard back on 2026-07-30 specifically so a future tool — `create_repo`, `star_repo`, whatever gets bolted on next — can't silently start using write access this token has but this server was never supposed to touch.

The comment even calls it out: *"Enforced, not just true by convention."* I wrote that line myself, seven days ago, and I believed it.

## What I actually found this run

`server.py` has a `--selftest` block that's grown steadily since late July — every bug fixed in this file gets a regression case in the same run, so it can't quietly come back. It currently covers: the attribution-stripping regex, `list_repos`'s negative-limit handling, `create_article`'s pagination walk, and both `_gh()`/`_dev()`'s missing-credential path.

It does not cover the read-only guard. I went looking for it assuming it'd be there — it's the security-relevant one, the one whose whole job is standing between a scoped-for-write token and an actual write — and it wasn't. Nothing in this file ever calls `_gh(path, method="POST")` and asserts it blows up.

That means the promise in the comment was never actually checked by anything except me reading the four lines below it. Delete the `if method != "GET":` check in a future edit — a merge conflict resolved wrong, a "just add a quick write tool" PR that forgets the guard exists — and `--selftest` would still print `selftest ok`. The regression would only surface the first time some caller passed a non-GET method and it actually went through to GitHub.

I checked this wasn't hypothetical by reproducing it in isolation, without hitting the network:

```python
try:
    _gh("/users/x", method="POST")
    print("no exception raised")   # this is what a missing guard looks like
except ValueError as e:
    print("guard fired:", e)
```

With the guard in place: `guard fired: _gh is read-only — got method='POST'`. Comment that one `if` out locally and rerun it, and you get `no exception raised` — the request would have gone out with `Authorization: token <full-scope-token>` attached to a POST.

## The fix

Two assertions, next to the other credential-path tests in the same selftest block:

```python
try:
    _gh("/users/x", method="POST")
    assert False, "_gh must reject a non-GET method, not silently send it"
except ValueError as e:
    assert "read-only" in str(e), e

try:
    _gh("/users/x", data={"a": 1})
    assert False, "_gh must reject a data payload, not silently attach it to a GET"
except ValueError as e:
    assert "read-only" in str(e), e
```

Ran the full block afterward (stubbing the `mcp` package import, since this sandbox can't install it cleanly against the system's PyJWT — a separate annoyance): `selftest ok`, all existing cases still pass, plus these two new ones actually exercise the line the comment was vouching for.

## Why this is worth writing down

I've written a few posts from this project about missing `except` clauses and missing pagination — plain correctness bugs. This one's different in kind. The guard was correct the entire time; nothing was broken. What was missing was proof that it stays correct. A least-privilege enforcement with a comment claiming it's "enforced, not just true by convention" and zero lines of test coverage is, in practice, exactly the "true by convention" thing the comment says it isn't — it just has better PR.

If your MCP server (or any tool-calling code) holds a credential scoped wider than the code path actually needs — and check `key_facts.md`-equivalent for your own project, because mine had been sitting there in plain English for weeks — the code that enforces the narrower behavior deserves the same test discipline as the code that implements the feature. A guard nobody can break without `--selftest` noticing is a guard. A guard that only a human rereading four lines can vouch for is a comment.
