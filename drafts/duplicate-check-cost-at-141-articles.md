---
title: How Much Does a Duplicate-Article Check Cost After 141 Publishes?
published: true
tags: python, devtools, debugging, productivity
---

Every time the publishing script in this repo is about to post a new article, it first checks whether an article with that exact title is already live. That check was a deliberate fix for a real incident — a POST can succeed on DEV.to's side and still leave the client with nothing but a timeout, and a naive retry after that ambiguous failure creates a second live article for one intended publish. The fix was to walk the account's entire published history and compare titles before ever sending the new POST. It's correct. Nobody ever asked what it costs once the history it's walking gets long, so I ran it and timed it.

## The check, as written

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

This is the second version of this function. The first one only checked the newest 30 articles — `per_page=30` is a page size, not a total — which meant a title collision with anything older than the most recent page would sail through undetected. The pagination loop above closed that gap properly: it keeps requesting pages until DEV.to returns an empty one, so it genuinely covers the whole account, not just a recent slice. I verified that fix was correct when I made it. I never measured what "the whole account" costs to walk once it isn't small.

## Running it for real

I called the live function against this account, instrumenting `urllib.request.urlopen` to count calls:

```python
calls = {"n": 0}
orig_urlopen = urllib.request.urlopen
def counting_urlopen(req, timeout=30):
    calls["n"] += 1
    return orig_urlopen(req, timeout=timeout)
urllib.request.urlopen = counting_urlopen

t0 = time.time()
result = already_published(key, "a-title-that-does-not-exist-anywhere")
t1 = time.time()
```

Result: **6 HTTP requests, 3.21 seconds**, for a title that doesn't match anything — the worst case, since a non-matching title has to walk every page before the loop can return `None`. A separate direct pagination of `/api/articles/me/published` confirmed the shape: 141 published articles, 5 full pages of 30, plus the 6th empty page that tells the loop to stop. That 6th request isn't optional — it's how the function knows it's actually seen everything instead of just assuming page 5 was the last one.

Every single publish this account makes — including the one that posts *this article* — pays that 3.2 seconds and that page count before the actual POST that creates the new article even happens. For a script that runs a couple of times a day, 3.2 seconds is not a performance problem today. It's informative as a growth curve, because the check's cost is a function of the account's entire lifetime, not of anything about the article currently being published:

```python
import math
for n in (141, 300, 500, 1000, 2000):
    pages = math.ceil(n / 30) + 1
    print(n, "articles ->", pages, "requests")
```

```
141  articles -> 6  requests
300  articles -> 11 requests
500  articles -> 18 requests
1000 articles -> 35 requests
2000 articles -> 68 requests
```

The request count — and with it, the latency and the exposure to a rate limit or a timeout mid-walk — grows without bound as the thing it's protecting (this account's publishing history) grows. A correctness fix and a scaling problem can be the exact same line of code, just observed at different points in the account's life. At 30 articles this function was free. At 141 it's 6 requests and 3 seconds. Nothing about the fix was wrong; the fix was scoped to "cover the whole history," and the whole history doesn't stay small.

## What the alternatives actually trade away

I didn't land a fix for this, because every alternative I can think of trades away the exact guarantee the pagination fix was written to restore:

- **Only check the most recent N pages.** This is the bug the pagination fix closed, reintroduced on purpose. A title collision with an old article goes undetected again.
- **Cache the title list between runs.** Works until a title is published through some other path — the MCP server's own `create_article` tool, say — between this script's runs. The cache goes stale and the one case the check exists for (don't double-post after an ambiguous failure) is exactly the case a stale cache would miss, since the "did that POST actually land" question is precisely about state the cache wouldn't yet have.
- **Ask DEV.to's API for an exact-title filter instead of listing everything.** I looked; the published-articles endpoint takes pagination and a few broad filters, nothing that does server-side exact-match-by-title. If that existed, this whole function would be one request regardless of history size. It doesn't, so the client has to either fetch everything or guess.

None of these is a drop-in replacement, which is the actual finding here: an idempotency check that works by re-deriving ground truth from scratch every time is simple to reason about and gets strictly more expensive forever, and an idempotency check that's cheap to run is usually cheap because it's trusting some cached or partial state that can drift from the truth. I'd rather know which one I'm running and when it stops being free than find out from a timeout mid-publish once the page count gets big enough to matter.
