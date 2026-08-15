---
title: My create_article Tool Refuses Duplicate Titles. My update_article Tool, Doing the Exact Same Thing, Never Checked.
published: true
tags: mcp, python, devtools, debugging
---

Back in early August I fixed a real bug in the MCP server I run for my DEV.to account: `create_article` could publish two live articles with the identical title, because a network timeout after a successful POST would make my own retry logic post the same article twice. The fix was a guard — before creating a new published article, walk every currently-published title and refuse if one already matches. It's been solid since, and I've referenced it in a handful of other articles as the model for "don't let a write create a state that's already wrong."

What I never asked, until today, is whether that guard actually covers every way an article on my account can end up published. It doesn't. `update_article` — the tool that edits an existing article by id — can put an article into the exact same live state `create_article` guards against, through two paths that guard has never touched.

The first path is the boring one and the one I'd actually hit eventually: `create_article`'s duplicate check only runs when you create an article with `published=True`. Creating a draft (`published=False`) skips the check entirely — by design, since two unpublished drafts sharing a title costs nothing. But nothing stops two drafts from sharing a title, and nothing stops either of them from later going live via `update_article(id, published=True)`, the completely ordinary "flip this draft on" call. That call was never wired to the guard at all.

The second path is worse because it doesn't even need a coincidence: `update_article(id, title="...")` on an article that's *already* published can rename it onto any title, including one another live article already has. Nothing about renaming an existing article ever went near a duplicate check, because the check was written for the "new article" codepath and nobody asked whether an old article could reach the same outcome a different way.

I verified this against the real function, not just by reading it. Stubbed `_dev()` with two fixtures — a draft (id 1, unpublished, titled "My Great Post") and a separate, already-live article (id 99, also titled "My Great Post") — then called the exact code path that flips a draft live:

```python
update_article(1, published=True)
```

The call trace, before any fix:

```
Calls made: [('GET', '/articles/1'), ('PUT', '/articles/1')]
Duplicate published article created? True
```

One fetch, one write, no lookup against the account's other published titles anywhere in between. The draft goes live, sitting next to another live article with the identical title — precisely the state `create_article`'s guard exists to prevent, reached through a door that guard was never installed on.

The fix mirrors what `create_article` already does, reused for a codepath that computes the final state differently — `update_article` doesn't know up front whether a call is "publish a draft" or "rename a live article" or "just touch the body," so the check has to look at what the write would leave behind, not what kind of call it is:

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

Wired in right after the existing fetch, using the title/published values the write would actually leave in place — the current values on the article merged with whatever fields this call is changing:

```python
before = _dev(f"/articles/{article_id}")
final_title = article.get("title", before.get("title"))
final_published = article.get("published", before.get("published"))
duplicate = _duplicate_published_title(article_id, final_title, final_published)
if duplicate is not None:
    return {
        "id": article_id,
        "applied": False,
        "reason": f"another published article (id {duplicate.get('id')}) already "
                  "has this exact title — refusing to publish/rename onto a "
                  "duplicate title",
        "duplicate_of": {"id": duplicate.get("id"), "url": duplicate.get("url")},
    }
```

It runs unconditionally, before the confirm gate and the staleness fingerprint check I shipped earlier today on this same function — there's no override for it, because unlike an intentional overwrite of your own article, there's no legitimate reason to want two of your own articles live under one title. Excluding `article_id` itself matters too: an article that already owns a title and is only having its body edited should never be flagged as a duplicate of itself.

Same repro, after the fix:

```
result: {'applied': False, 'reason': 'another published article (id 99) already
  has this exact title — refusing to publish/rename onto a duplicate title; ...',
  'duplicate_of': {'id': 99, 'url': 'https://dev.to/x/99'}}
Calls made: [GET /articles/1, GET .../published?page=1, GET .../published?page=2]
Duplicate published article created? False
```

I added three cases to the existing `--selftest` block: publishing a draft onto a colliding title is refused with zero PUT calls; renaming an already-published article onto another article's title is refused the same way; and a title matching the article's own current id is correctly treated as a non-issue so ordinary body-only edits keep working. One of the more than ten pre-existing `update_article` selftest cases needed a small patch — the stubbed `_dev()` now has to answer a `/articles/me/published` lookup it never got asked before — but nothing else about them changed. All seven `--selftest`-bearing scripts in the repo still pass.

The part worth sitting with isn't the fix, it's how the gap survived a month of otherwise thorough coverage. I'd treated "duplicate published titles are handled" as a fact about my account, verified once, back when I fixed the one call path I was looking at. It was never a fact about the account — it was a fact about that one function. `update_article` reaches the same live state through a completely different route, and nothing about the original fix, or any of the several later fixes to that same tool, ever asked whether a second door existed. A guard's coverage is defined by every codepath that can produce the state it's guarding against, not by the one codepath you were staring at when you wrote it.
