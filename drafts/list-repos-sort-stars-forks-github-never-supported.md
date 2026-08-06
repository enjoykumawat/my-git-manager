---
title: My MCP Tool's Docstring Promised sort="stars". GitHub's API Was Never Going to Honor That Value.
published: true
tags: mcp, python, debugging, devtools
---

Every tool in my `developer-presence` MCP server has a one-line docstring, because that's the only documentation an agent calling the tool ever sees — no README, no OpenAPI spec, just whatever string sits under the `@mcp.tool()` decorator. I've already found and fixed real bugs where that docstring drifted from what the code actually did. This one's different: the docstring and the code agreed with each other perfectly. They were both wrong about what a third system — GitHub's own REST API — actually accepts.

## The tool in question

```python
@mcp.tool()
def list_repos(sort: str = "updated", limit: int = 10) -> list:
    """List public repos. sort: updated|stars|forks. limit: 1-100."""
    repos = _gh(f"/users/{GITHUB_USERNAME}/repos?sort={sort}&per_page={min(limit, 100)}")
    return [...]
```

`sort` gets interpolated straight into the query string and sent to `GET /users/{username}/repos`. No validation, no mapping — whatever string the caller passes is whatever string GitHub receives. The docstring says `updated|stars|forks` are the three options. The README repeated the same claim in its tools table. I wrote both of those, at the same time, clearly believing it.

## What GitHub's endpoint actually accepts

I checked GitHub's own REST API reference for "List repositories for a user" rather than trust memory or the code that was already agreeing with itself. The `sort` parameter's enum for this specific endpoint is `created`, `updated`, `pushed`, `full_name` — nothing else. `stars` and `forks` are real sort values, just not here; they belong to the separate repository *search* endpoint (`GET /search/repositories`), which this tool doesn't call.

GitHub's API doesn't error on an unrecognized query value. It just ignores it and falls back to its own default sort. So `list_repos(sort="stars")` was never going to fail loudly — it was going to silently return repos in whatever order GitHub feels like using instead, with nothing in the response telling the caller their sort request was dropped on the floor.

```python
# what the docstring promises
list_repos(sort="stars", limit=5)   # "top 5 most-starred repos"

# what GitHub actually does with sort=stars on /users/{username}/repos
# -> ignores it, uses its own default, no error, no warning
```

That's a worse failure mode than a crash. A crash tells you immediately that something's wrong. This one returns a plausible-looking list of five repos, in some order, and every signal available to the caller — the tool succeeded, the shape is right, no exception — says the request was honored.

## Why nothing caught it sooner

This tool has existed since the server's first version. Nothing in this repo's automated checks would ever catch it, because the failure isn't a Python exception or a malformed response — it's a semantic mismatch between what a docstring promises and what an external API's documented parameter enum actually supports. `scripts/check_key_facts.py` checks that referenced files exist. Nothing checks that a tool's own claims about a third-party API match that API's real contract. And because I hadn't tried calling this tool with `sort="stars"` myself recently — I mostly use `updated` — there was no moment where the mismatch would surface as a visibly wrong result instead of a quietly wrong one.

## The fix

The honest options were: narrow the docstring to only the values GitHub actually supports, or make `stars`/`forks` actually work the way the docstring always promised. I went with the second — GitHub not supporting a server-side sort doesn't mean the feature has to not exist, it just means the sort has to happen after the fetch, not in the query string:

```python
_REPO_API_SORTS = {"created", "updated", "pushed", "full_name"}
_REPO_CLIENT_SORT_KEYS = {"stars": "stargazers_count", "forks": "forks_count"}


@mcp.tool()
def list_repos(sort: str = "updated", limit: int = 10) -> list:
    """List public repos. sort: updated|created|pushed|full_name|stars|forks. limit: 1-100."""
    api_sort = sort if sort in _REPO_API_SORTS else "updated"
    fetch_limit = 100 if sort in _REPO_CLIENT_SORT_KEYS else min(limit, 100)
    repos = _gh(f"/users/{GITHUB_USERNAME}/repos?sort={api_sort}&per_page={fetch_limit}")
    if sort in _REPO_CLIENT_SORT_KEYS:
        repos = sorted(repos, key=lambda r: r[_REPO_CLIENT_SORT_KEYS[sort]], reverse=True)[:limit]
    else:
        repos = repos[:limit]
    return [...]
```

The `fetch_limit` line is the part that's easy to get wrong even once you know client-side sorting is needed. If `limit=5` and someone asks for `sort="stars"`, requesting only 5 repos from GitHub *before* ranking them means you're picking the top 5 by stars out of whichever 5 repos happened to come back first — not the top 5 out of the whole account. The sort has to run against everything, and only then get cut down to `limit`. I fetch up to GitHub's own `per_page` ceiling of 100 when a client-side sort is requested, rank the full set, and slice after.

I couldn't verify this end-to-end against the live GitHub API — this sandbox's egress to GitHub is proxy-intercepted for anything outside this session's own repo scope, the same restriction earlier audits in this project have hit. So I proved the part that was actually wrong — the ranking logic — against a stub instead of trusting that "it looks right" was enough:

```python
def fake_gh(per_page):
    repos = [
        {"name": "a", "stargazers_count": 3},
        {"name": "b", "stargazers_count": 50},
        {"name": "c", "stargazers_count": 10},
        {"name": "d", "stargazers_count": 1},
        {"name": "e", "stargazers_count": 25},
    ]
    return repos[:per_page]

# limit=2, sort=stars must fetch all 5 first, then rank, not rank whatever 2 came back
repos = fake_gh(100)
top2 = sorted(repos, key=lambda r: r["stargazers_count"], reverse=True)[:2]
assert [r["name"] for r in top2] == ["b", "e"]
```

That passed. What it can't verify is the query-string half — that GitHub really does accept `created|updated|pushed|full_name` and really does ignore anything else the way the docs describe, since I have no live path to call the endpoint from here and confirm. The API-parameter fact came from GitHub's own published reference, not a request I ran myself; that's a real, separate layer of trust the fix still depends on, and it's the one thing about this fix I can't close out from inside this sandbox.

## The actual lesson

A docstring that matches the code isn't the same claim as a docstring that matches reality. I'd already learned to distrust docstrings that drift from the function underneath them — that's a bug I've caught in this exact server before. I hadn't yet learned to distrust docstrings whose only fault is describing a *third* system's behavior with total confidence and zero verification. The code and the docs told the same story here. The story itself was never checked against the one place that actually decides whether it's true.
