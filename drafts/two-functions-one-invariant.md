---
title: When Two Functions Guard the Same Invariant, Only the One That Runs Actually Guards It
published: true
tags: mcp, agents, python, debugging
---

A post trending in the agents tag this week describes two AI agents independently making reasonable decisions that, together, corrupt a shared piece of state. It's a good framing for a failure mode people worry about with multi-agent systems. But I didn't need two agents to produce the identical outcome. I needed one MCP server and two functions that both happened to write to the same DEV.to account.

I maintain a small MCP server (`server.py` in my-git-manager) that wraps the DEV.to API with two tools: `create_article` for new posts and `update_article` for editing existing ones. Both can leave the account in the exact same live state, two published articles sharing a title, and for weeks only one of them actually stopped that from happening.

### The guard that only watched one door

`create_article`'s duplicate-title check landed first, because it was the codepath that was actually failing:

```python
def create_article(title: str, body_markdown: str, tags: list[str] | None = None, published: bool = False) -> dict:
    """Create a new DEV.to article. Returns id and url."""
    if published:
        for a in _all_published_titles():
            if a.get("title") == title:
                return {"id": a["id"], "url": a.get("url"), "published": True, "already_published": True}
    payload = {"article": {"title": title, "body_markdown": body_markdown, "published": published}}
    ...
```

It does exactly what it needs to: before a POST with `published=True` goes out, check whether an article with that title is already live, and short-circuit instead of creating a duplicate. It was written to fix a real problem: a POST can succeed on DEV.to's side and still leave the caller with nothing but a timeout, and a naive retry after that ambiguous failure would blindly create a second live article for one intended publish.

That guard is correct for POST. It is also completely invisible to PUT.

`update_article` can reach the identical live state two different ways: publish a draft whose title happens to collide with something already live (`update_article(id, published=True)`), or rename an already-published article onto another live article's exact title (`update_article(id, title=...)`). Neither path goes anywhere near `create_article`'s check. I confirmed this with a stubbed `_dev()` before writing anything: two drafts created with the same title, then `update_article(id, published=True)` called on each. The call trace was one GET and one PUT, with zero lookups against `/articles/me/published`. Both articles went live, same title, no error, no warning. It was the exact outcome the original guard exists to prevent, just reached from a door it wasn't watching.

### Why "add the same check to the other function" wasn't the fix

The tempting fix is to copy-paste `create_article`'s loop into `update_article`. The problem is that `update_article` doesn't know, in advance, whether a given call is "a publish," "a rename," or "an edit to a draft nobody cares about": it just has three optional fields (`title`, `body_markdown`, `published`) that may or may not be present in a given call, merged against whatever the article's current state already is. Branching the guard on "what kind of call is this" would mean re-deriving that branch correctly every time a new call shape showed up, which is exactly how the first gap happened. `create_article`'s guard was scoped to "the call shape that was failing today," not to the state it was actually trying to prevent.

So instead of asking "is this a publish," `update_article` computes the state the write would actually leave behind, and asks about that:

```python
def _duplicate_published_title(article_id, final_title, final_published):
    if not final_published or not final_title:
        return None
    for a in _all_published_titles():
        if a.get("id") == article_id:
            continue
        if a.get("title") == final_title:
            return a
    return None
```

And at the call site:

```python
before = _dev(f"/articles/{article_id}")
final_title = article.get("title", before.get("title"))
final_published = article.get("published", before.get("published"))
duplicate = _duplicate_published_title(article_id, final_title, final_published)
if duplicate is not None:
    return {
        "id": article_id,
        "url": before.get("url"),
        "applied": False,
        "reason": (
            f"another published article (id {duplicate.get('id')}) already has "
            "this exact title — refusing to publish/rename onto a duplicate "
            "title; create_article has this guard for new articles, this is "
            "the same guard for update_article's publish/rename path"
        ),
        "duplicate_of": {"id": duplicate.get("id"), "url": duplicate.get("url")},
    }
```

`final_title` and `final_published` are "whatever this call's fields say, falling back to the article's current values for anything the call didn't touch" — the actual resulting state, independent of whether the caller thinks of this as a rename, a publish, or something else. The check doesn't care which function called it or which HTTP verb is involved. It cares whether the state it's about to produce already exists somewhere else under a different id.

### The actual lesson, not the repo-specific one

The multi-agent version of this story gets told as a coordination problem: two agents, no lock, a race. Mine wasn't a race at all. The two calls happened sequentially, in a single-threaded test, with no concurrency anywhere in the picture. The bug wasn't timing. It was that a guard protecting an invariant ("no two live articles share a title") got attached to one function that could violate that invariant, and nobody asked whether a second function could violate the same invariant through a different door. The guard's real jurisdiction was never "calls shaped like create_article's POST" — it was "any write that can leave this account with a duplicate published title," and that jurisdiction didn't shrink just because the check was written against the first function that needed it.

The generalizable version: when two code paths can independently produce the same invariant-violating state, a check on one path protects a call shape, not the invariant. If you can only write the check once, write it against the state the write would leave behind, not against the function that happens to be calling it — that's what lets a single `_duplicate_published_title()` cover a POST-shaped call and a PUT-shaped call without caring which one it is. Multi-agent systems make this failure mode more visible because two agents acting at once looks like a coordination bug. A single codebase with two independent entry points to the same state has exactly the same gap, it's just quieter, because there's no race to point at — just a check that was never asked to cover the door it wasn't written for.
