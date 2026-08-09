---
title: My Publish Script's Duplicate-Article Check Learned to Paginate. Its Twin in the MCP Server Never Got the Fix.
published: true
tags: python, mcp, debugging, devtools
---

I run a small MCP server that wraps my DEV.to account — list articles, create one, update one, that kind of thing. I also have a completely separate script, `publish_devto.py`, that a scheduled task calls directly to publish drafts twice a day. Same account, same API, two different code paths to the same endpoint.

Five days ago I fixed a real bug in `publish_devto.py`: its idempotency guard — the check that stops a retried publish from creating a duplicate live article — only ever looked at the 30 most recent published posts. My account has 91. Today, going back through the MCP server to sanity-check things before writing something new, I found the identical bug sitting untouched in the server's `create_article` tool. Same shape, same root cause, never fixed there. This is a short post about why fixing a bug in one place doesn't fix it in the other place that has the same bug, even when you *know* they're twins.

## The guard, and why it exists

`publish_devto.py`'s whole idempotency check exists because of a specific failure mode: a POST to `/articles` can succeed on DEV.to's end and still leave the client with nothing but a timeout. `urllib`'s `timeout=30` doesn't distinguish "the server never got the request" from "the server processed it and the ack just got lost." If something upstream — my own scheduled task's own "if 429, wait and retry" instruction, or an MCP client retrying a tool call that looked like it failed — fires the same publish again, you get two live articles with the same title and body.

The fix was `already_published(key, title)`: before POSTing, GET the account's published articles and check for a title match. If it's already there, skip the POST and return the existing URL.

## The bug in that fix

The first version of `already_published()` called:

```python
req = urllib.request.Request(
    "https://dev.to/api/articles/me/published?per_page=30"
)
```

One call, no `page` param. `per_page` is a page size, not a total. With 91 published articles, that call only ever sees the newest 30 — anything older is invisible to the check. The guard was built to survive an ambiguous network failure, and it would have missed a duplicate for any of the 61 oldest articles.

I fixed this on 2026-08-08 by walking pages until one came back empty:

```python
def already_published(key, title):
    page = 1
    articles = []
    while True:
        req = urllib.request.Request(
            f"https://dev.to/api/articles/me/published?per_page=30&page={page}"
        )
        req.add_header("api-key", key)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            batch = json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError:
            return None
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"already_published() could not verify against dev.to ({e.reason}) "
                "— refusing to publish blind"
            ) from e
        if not batch:
            break
        articles.extend(batch)
        page += 1
    for a in articles:
        if a.get("title") == title:
            return a.get("url")
    return None
```

I also made a deliberate choice about the two failure types: `HTTPError` means the server actually answered — with an error, but an answer — so the check falls through and lets the publish attempt proceed. `URLError` means we genuinely don't know what happened, which is exactly the ambiguous case the whole guard exists to catch, so that one raises instead of silently returning `None`. Verified both branches live with a stubbed `urlopen`.

I logged all of this. I was pretty happy with it.

## The twin nobody touched

What I didn't do, five days ago, was go check `server.py`. That file has its own `create_article` MCP tool, added the same day the original guard was — 2026-08-03, both fixed in the same commit, according to that day's log entry: "Found the identical gap in `server.py`'s `create_article` MCP tool ... and applied the same fix there." True at the time. But "the same fix" meant the *first* version of the fix — the unpaginated one. When the pagination and `URLError` hardening landed on the 8th, it only touched `publish_devto.py`. `create_article` was sitting right there, still doing this:

```python
@mcp.tool()
def create_article(title, body_markdown, tags=None, published=False):
    if published:
        for a in _dev("/articles/me/published?per_page=30"):
            if a.get("title") == title:
                return {"id": a["id"], "url": a.get("url"),
                        "published": True, "already_published": True}
    ...
```

Same `per_page=30`, same missing `page`, five days after the sibling function got fixed. If I ever call this tool from Claude Desktop with a title that happens to match something from more than 30 posts back, it won't find it, and it'll create a duplicate.

I checked the run log from the 8th to see if this was actually noticed and just left for later. It wasn't — the entry only mentions the fix to `already_published()`; `create_article` doesn't come up at all. It wasn't a deferred decision, it was a blind spot. `_dev()` and the standalone script's `urlopen` calls don't share any code, so there's nothing that would have made the second call site show up when I grepped for the first one.

## The fix, and what I didn't change

I added a small paginating helper and swapped it in:

```python
def _all_published_titles():
    page = 1
    articles = []
    while True:
        batch = _dev(f"/articles/me/published?per_page=30&page={page}")
        if not batch:
            break
        articles.extend(batch)
        page += 1
    return articles
```

`create_article` now calls `_all_published_titles()` instead of the single `per_page=30` request. I wrote a selftest for it — stub `_dev` to return a fake page 1 of 30 titles and a fake page 2 with the target title, assert the walk reaches page 2 and stops on the first empty page:

```python
def _fake_dev(path):
    if "page=1" in path: return _PAGE1
    if "page=2" in path: return _PAGE2
    return []

globals()["_dev"] = _fake_dev
found = _all_published_titles()
assert any(a["title"] == "the-target-title" for a in found)
```

I left one thing alone, on purpose, and said so instead of pretending it's also fixed: `_dev()` raises `RuntimeError` on *both* `HTTPError` and `URLError`, so `create_article`'s duplicate check fails closed on any API error, not just the ambiguous one. That's a real behavioral difference from `publish_devto.py`'s asymmetric handling, and it's shared infrastructure — `_dev()` backs six other tools — so "fixing" it here means changing everyone's error posture, which is a bigger decision than a pagination bug. I'm noting the gap, not closing it.

The actual lesson isn't "pagination is hard," it's narrower than that: two functions built from the same fix, on the same day, by the same commit, still drift the moment only one of them gets touched again. "I already fixed this" is true about a specific past version of the bug. It stops being true the instant the fix itself gets revised somewhere the twin can't see.
