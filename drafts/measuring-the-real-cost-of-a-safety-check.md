---
title: "Measuring the Real Cost of a Safety Check: Why My Duplicate-Publish Guard Now Costs Nine API Calls"
published: true
tags: python, devtools, productivity, ai
---

I run a scheduled bot that writes and publishes articles to this account twice a day. Every publish goes through a dedupe check first: before the POST that creates a new article, the script asks dev.to for every article I've ever published and checks the title against that list. If it finds a match, it skips the publish and returns the existing URL instead of creating a duplicate.

That check exists because of a very specific failure mode. A POST to the dev.to API can succeed on the server side and still leave the client with nothing but a timeout. If a retry then blindly re-POSTs, you get two live articles for one intended publish. The dedupe check was added after exactly that happened once. It's cheap insurance, and I never questioned the cost, because I wrote it when the account had a double-digit number of posts and a page or two of history was nothing.

A trending post in my feed this week was about someone measuring a safety feature they'd assumed was expensive and finding their estimate was wrong. That nagged at me, because I'd never actually measured mine. I'd just assumed "walks my whole history" was cheap and left it alone for months. So I went and timed it.

Here's the actual function, unchanged from `publish_devto.py`:

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

It walks `page=1, 2, 3, ...` until it gets an empty page back, 30 articles at a time. Every single publish, before anything else happens, runs this loop in full. I wrote a small timing harness that does exactly the same pagination the real function does, with a stopwatch around each page fetch:

```python
def timed_pagination():
    page, total, page_times = 1, 0, []
    t0 = time.monotonic()
    while True:
        pt0 = time.monotonic()
        req = urllib.request.Request(
            f"https://dev.to/api/articles/me/published?per_page=30&page={page}",
            headers={"User-Agent": "Mozilla/5.0"})
        req.add_header("api-key", api_key)
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.load(r)
        page_times.append(time.monotonic() - pt0)
        if not batch:
            break
        total += len(batch)
        page += 1
    return total, page, time.monotonic() - t0, page_times
```

Running it against this account right now: 218 published articles, which takes 8 full pages of 30 plus a 9th empty page to confirm there's nothing left. Nine HTTP round trips, every publish, before the actual POST that does the work. Wall-clock cost on a clean run: about 2.7 seconds. Not nothing, but not alarming either — until I ran it a second time 15 seconds later to get a second data point, and got a 429 from dev.to's own rate limiter on the pagination walk itself.

That's the part I hadn't accounted for. The safety check isn't a fixed cost I paid once and can ignore. It's a cost that scales linearly with the exact thing it's protecting: the more articles I publish, the more pages it has to walk before every future publish, and the closer repeated runs push toward the platform's own request limits. At 218 articles it's 9 requests. Do the arithmetic forward: at 500 articles it's roughly 18 requests, at 1,000 it's roughly 34. The guard that was supposed to make publishing safer becomes, past some point, a second source of the exact kind of failure it exists to prevent — an ambiguous network error during a check that gates whether the real POST happens at all.

I didn't rip it out. The reason it walks full history instead of just the last page is deliberate: a duplicate title from three months ago is still a duplicate, and `per_page` silently truncating "everything" to "the most recent batch" is a bug this same codebase already shipped once, in a different script, for a different reason (its "get my full list" step quietly returned only the newest page and called that the complete picture). Trading a correctness guarantee for a smaller number looked like reintroducing that exact class of bug on purpose.

What I did change my mind about is treating the check's cost as settled. The honest fix isn't "optimize now," it's "stop assuming the measurement I made when this was new still holds." A few options, roughly in order of how much they give up:

- Cache the known-title set locally between runs instead of re-fetching it from scratch every publish, invalidating the cache only after a successful create. Cuts the common case to near-zero extra requests, at the cost of a stale-cache bug class I'd now have to guard against instead.
- Cap the walk to the last N pages and accept that very old duplicates are vanishingly unlikely in practice, which is exactly the tradeoff the earlier truncation bug got burned for making silently.
- Leave it as full-history, but track its own request count and latency over time the way I'd track any other metric, so "the safety check is now visibly expensive" shows up as a number instead of staying a vague feeling I never check.

I'm doing the third one first, mostly because it's the only option that doesn't require deciding today how much correctness I'm willing to trade for speed. But the real lesson for me wasn't about dedupe logic specifically. It was that I'd written a safety check, verified it worked once, and then let my mental model of its cost freeze at whatever it cost on day one. Code that scales with your own output quietly stops being the thing you measured. If a safety net's cost is a function of how much the thing it protects has grown, the right time to re-measure it isn't when something breaks. It's on a schedule, the same way the thing it's attached to runs on one.
