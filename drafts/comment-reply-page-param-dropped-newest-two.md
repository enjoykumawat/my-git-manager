---
title: "My Comment-Reply Script Asked DEV.to for 'My Articles.' Leaving Off One Query Param Silently Dropped the Newest Two."
published: true
tags: python, api, debugging, devtools
---

I've written before about this exact publishing pipeline under-listing its own history — the scheduled task's Step 1 hits `/api/articles/me/published?per_page=30` and treats that single page as "the full list," silently missing every article past the most recent thirty. That bug lived in a different script (`publish_devto.py`'s caller) and had an obvious cause: `per_page` is a page size, not a total, and nobody had ever added a `page` loop. I fixed it three days ago with `scripts/list_all_published_titles.py`, which walks pages until one comes back empty.

Today I found the same *symptom* — the newest articles missing from a "list all my articles" call — in a completely different script, with a cause I didn't expect: this time `per_page` wasn't the problem. The call already asked for the max page size in one shot. It just never said which page.

`reply_comments.py` is the script behind the separate comment-reply-drafting routine. Two functions, `pending()` and `audit()`, both start the same way:

```python
for a in api(f"/articles?username={ME}&per_page=100"):
    if not a["comments_count"]:
        continue
    for c in api(f"/comments?a_id={a['id']}"):
        ...
```

`per_page=100` is DEV.to's actual page-size ceiling, and this account has exactly 100 published articles as of today — on paper, one call should return everything, no pagination needed at all. I went looking at this file for an unrelated reason (checking whether the pagination fix from three days ago had a sibling bug anywhere else in the codebase) and decided to actually verify that assumption against the live API instead of trusting the arithmetic:

```python
>>> len(get(f"/articles?username={ME}&per_page=100"))
98
>>> len(get(f"/articles?username={ME}&per_page=100&page=1"))
100
```

Same account, same query, same `per_page`. The only difference between those two calls is that the second one explicitly says `page=1` — which should be the default when `page` is omitted, and normally is, for every other DEV.to endpoint this codebase touches. Here it isn't. Diffing the two title sets showed exactly which two articles the no-page call was missing: the two published earlier today.

That's not a coincidence of timing — it's the failure mode. Whatever's serving the omitted-`page` response for this particular endpoint isn't recomputing "give me everything, freshest first, up to per_page items" on each request; it's serving something that lags behind the account's actual current article count, and the gap is exactly the account's newest entries. `page=1` on the same endpoint isn't lagging at all. I don't have visibility into DEV.to's backend to say definitively whether that's a cache layer, an index that only gets rebuilt on the numbered-page code path, or something else — I can only report what two live, otherwise-identical requests actually returned, minutes apart, repeatedly. But the practical effect doesn't depend on knowing the mechanism: any code on this account that calls `/articles?username=...` without a `page` param is silently working from a view of "my articles" that's missing whatever was published most recently.

For `pending()` and `audit()` specifically, that means a fresh comment on a just-published article can't be found — not "found late," not "found next run" — genuinely invisible, because the loop that walks every article's comments never even considers that article in the first place. I confirmed this wasn't hypothetical: one of today's two newly-published articles already had a live comment sitting on it. Run against the unfixed code, `pending()` returned nothing for that article. Same call, same comment, with the fix applied — it showed up.

The fix mirrors the shape of the earlier pagination fix almost exactly, which is itself worth noting:

```python
def my_articles():
    articles = []
    page = 1
    while True:
        batch = api(f"/articles?username={ME}&per_page=100&page={page}")
        if not batch:
            break
        articles.extend(batch)
        page += 1
    return articles
```

Walk `page` explicitly, starting at 1, stop on the first empty page. `pending()` and `audit()` both now call `my_articles()` instead of the bare unpaginated request. For an account still under 100 articles this makes exactly two requests — page 1 (the real 100), page 2 (empty) — a negligible cost for closing a real, live gap. It also means this stops depending on the account staying under one `per_page=100` page at all, which was already flagged three days ago as a near-miss worth watching (this account gains roughly 2-3 published articles a day; the ceiling was maybe a week out). That part wasn't the goal of today's fix, but it falls out of it for free.

What makes this distinct from the earlier pagination bug isn't just the file — it's the actual mechanism. That one was a straightforward "you asked for a subset and treated it as the whole" arithmetic error, the kind you can spot by reading the code and doing the math: 30 per page, 91 articles, therefore incomplete. This one required treating the *identical* endpoint call as suspect even though the size arithmetic checked out cleanly (100 requested, 100 that should exist), and the only way to catch it was refusing to trust that "the numbers add up" meant the API was actually returning what it claimed. Two calls that look interchangeable on paper — one with an implicit default, one with that default spelled out — turned out not to be interchangeable at all. The lesson isn't "always paginate," which I'd already internalized from the first bug. It's that an endpoint behaving inconsistently for two requests that *should* be identical is a failure mode pagination logic alone doesn't protect against — you only catch it by actually diffing what came back, not by trusting that the request you sent matches the response you should get.

Added a `--selftest` case that stubs `api()` with two full pages and an empty one, asserting `my_articles()` walks `page=1,2,3` explicitly and stops only once a page comes back empty — the same contract `scripts/list_all_published_titles.py` already tests for its own endpoint. Logged the root cause in `docs/project_notes/bugs.md`.
