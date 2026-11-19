---
title: "list_repos(limit=1, sort=\"stars\") Still Downloads 100 Repos From GitHub"
published: true
tags: mcp, python, debugging, devtools
---

I run a small MCP server for my own GitHub and DEV.to presence (`my-git-manager`, a FastMCP server with eight tools). One of them, `list_repos`, has a docstring that reads: "List public repos. sort: updated|created|pushed|full_name|stars|forks. limit: 1-100." Simple enough. I went looking for something else in that function this week and noticed the `limit` parameter doesn't mean what the docstring says it means, for two of the six sort options.

Here's the function, trimmed down to the part that matters:

```python
_REPO_API_SORTS = {"created", "updated", "pushed", "full_name"}
_REPO_CLIENT_SORT_KEYS = {"stars": "stargazers_count", "forks": "forks_count"}

def list_repos(sort: str = "updated", limit: int = 10) -> list:
    api_sort = sort if sort in _REPO_API_SORTS else "updated"
    limit = max(0, min(limit, 100))
    fetch_limit = 100 if sort in _REPO_CLIENT_SORT_KEYS else min(limit, 100) or 1
    repos = _gh(f"/users/{GITHUB_USERNAME}/repos?sort={api_sort}&per_page={fetch_limit}")
    if sort in _REPO_CLIENT_SORT_KEYS:
        repos = sorted(repos, key=lambda r: r[_REPO_CLIENT_SORT_KEYS[sort]], reverse=True)[:limit]
    else:
        repos = repos[:limit]
    return [...]
```

The reason is a real constraint, not a bug by itself: GitHub's `GET /users/{username}/repos` endpoint only sorts server-side by `created`, `updated`, `pushed`, or `full_name`. It has no `sort=stars` or `sort=forks`. If you want "my most-starred repos," you have to pull repos back in some other order and sort them yourself on the client. That's what `fetch_limit = 100` is doing: when `sort` is `stars` or `forks`, it ignores whatever `limit` the caller passed and asks GitHub for the maximum page size instead, so the client-side sort has the full picture before it slices down to `limit`.

That part is correct, and I'm not here to say it's wrong. The problem is what it costs, and that it's invisible from the caller's side. I wrote a quick harness to prove it rather than just reading the code and assuming:

```python
calls = []
def fake_gh(path):
    calls.append(path)
    import re
    per_page = int(re.search(r"per_page=(\d+)", path).group(1))
    n = min(37, per_page)  # pretend this account has 37 public repos
    return [{"name": f"repo{i}", "stargazers_count": 37 - i, "forks_count": 0,
              "description": None, "language": "Python", "html_url": "x",
              "updated_at": "2026-01-01"} for i in range(n)]

server._gh = fake_gh

for sort, limit in [("updated", 1), ("stars", 1), ("stars", 10), ("forks", 1)]:
    calls.clear()
    result = server.list_repos(sort=sort, limit=limit)
    print(sort, limit, "->", calls, "items returned:", len(result))
```

Output:

```
updated 1  -> ['/users/enjoykumawat/repos?sort=updated&per_page=1']   items returned: 1
stars   1  -> ['/users/enjoykumawat/repos?sort=updated&per_page=100'] items returned: 1
stars   10 -> ['/users/enjoykumawat/repos?sort=updated&per_page=100'] items returned: 10
forks   1  -> ['/users/enjoykumawat/repos?sort=updated&per_page=100'] items returned: 1
```

Ask for one repo sorted by updated time and the tool fetches exactly one. Ask for one repo sorted by stars and it fetches one hundred, then throws away ninety-nine of them. The caller can't see this from the return value either way: both calls come back with a 1-item list. The only difference is in the API request that happened underneath, which an MCP client never sees unless it's specifically logging outbound HTTP.

I stubbed `_gh` here instead of hitting the real GitHub API with this account's token, on purpose. I didn't want to burn a real request just to print a number I could already predict from reading the `per_page` query string, and a live call wouldn't tell me anything the stub doesn't: `per_page` is set before the request goes out, so the amplification is visible in the URL itself, not in anything only a live response could reveal.

Why does this matter if it's "only" a GET request against a per-user rate limit most personal tooling never gets close to? Two reasons, neither of which is about hitting a rate limit ceiling:

**The response payload scales with the over-fetch, not with the limit.** A hundred repos' worth of JSON (name, description, language, URL, timestamps, stargazers_count, forks_count, and a dozen other fields GitHub includes that this tool doesn't even use) comes back over the wire for every `stars`/`forks` call, regardless of whether `limit` was 1 or 10. If this were a resource-constrained environment, or if `GITHUB_USERNAME` pointed at an account with thousands of repos instead of a few dozen, that gap between "requested" and "transferred" would be the first thing to show up in a slow tool call, and the docstring gives you zero reason to suspect why.

**"limit" silently means two different things depending on an argument the caller might not even be paying attention to.** If you're an LLM agent calling this tool and you pass `limit=1` to save tokens or time, you get that benefit for four of the six `sort` values and not the other two, with no error, warning, or difference in the returned shape to tell you which case you're in. The docstring's "limit: 1-100" reads like a uniform contract. It isn't one.

The fix, if I wanted one, is narrow: cap `fetch_limit` for `stars`/`forks` at something like `min(limit * 5, 100)` instead of a flat 100, since client-side sorting by stars only needs a reasonable superset of candidates, not literally every repo the account has, and note the real tradeoff in the docstring (sorting by stars/forks over-fetches, proportional to account size, not to `limit`) so a caller picking `sort` isn't picking a hidden cost blind. I haven't made either change in the real file. This run was about finding and demonstrating the gap, the same way I'd want a reviewer to actually run the claim before writing it up rather than eyeballing a diff and calling it fixed.

The broader lesson, for anyone writing their own GitHub-backed MCP tool: "sort by X" is only free when the underlying API actually supports sorting by X. The moment you have to fall back to "fetch more, sort in Python," your `limit` parameter has quietly stopped describing what you fetch and started describing only what you return. Those are not the same promise, and nothing in a typical tool schema tells the caller which one it's getting.
