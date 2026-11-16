---
title: Scaling My Own DEV.to Tool Call to Its Max Page Size Lands Almost Exactly on the 8-Megabyte Crash Number
published: true
tags: mcp, python, devtools, debugging
---

A post titled ["How an 8MB MCP Tool Response Crashes Claude Code"](https://dev.to/framy2/how-an-8mb-mcp-tool-response-crashes-claude-code-and-how-to-debug-prompt-cache-misses-across-3kob) has been trending in the MCP tag, and the number in the title stuck with me because it's specific enough to actually test. I run a small FastMCP server (`server.py` in `my-git-manager`) with a `list_articles` tool that wraps the DEV.to API, and I'd never measured what that tool's response size actually looks like once it leaves my hands. So instead of arguing about whether 8MB is a realistic number for a tool response, I measured mine.

Here's the tool as it exists in `server.py` today:

```python
def list_articles(per_page: int = 10) -> list:
    """List your published DEV.to articles."""
    articles = _dev(f"/articles/me/published?per_page={min(per_page, 30)}")
    return [
        {
            "id": a["id"],
            "title": a["title"],
            "published": a.get("published"),
            "url": a.get("url"),
            "reactions": a.get("positive_reactions_count", 0),
            "comments": a.get("comments_count", 0),
            "page_views": a.get("page_views_count", 0),
        }
        for a in articles
    ]
```

Two guards are already baked in here that I didn't fully appreciate until I ran the numbers: `min(per_page, 30)` caps how many articles DEV.to will ever return in one call, and the dict comprehension only keeps 7 fields out of everything the API sends back. I wanted to know what happens if you strip both of those out, because that's effectively what a tool looks like when nobody's thought about response size yet.

I called the raw, unshaped `/articles/me/published?per_page=30` endpoint directly against my own account (174+ published articles at this point) and measured the actual bytes:

```python
raw = dev_get("/articles/me/published?per_page=30")
data = json.loads(raw)
avg = len(raw) / len(data)
# raw per_page=30: 243050 bytes for 30 articles, avg 8101.7 bytes/article
```

8.1KB per article, raw, unfiltered. DEV.to's article objects carry full HTML-rendered body previews, cover image URLs, full tag objects, user objects, organization objects, all of it, for every single item in the page. DEV.to's own API caps `per_page` at 1000. Running that average out to the actual ceiling:

```python
for pp in [100, 500, 1000]:
    print(f"{pp}: {avg*pp/1_000_000:.2f} MB")
# 100: 0.81 MB
# 500: 4.05 MB
# 1000: 8.10 MB
```

8.10MB at `per_page=1000`. The trending post's crash number is 8MB. I didn't pick my test account or my test endpoint to hit that figure, it just landed there, because an average content-heavy REST API object times a four-digit page size gets you into single-digit megabytes pretty reliably regardless of which SaaS you're calling. That's the actual lesson underneath the trending post's specific anecdote: 8MB isn't a magic crash threshold tied to one service, it's roughly what you get the first time nobody puts a ceiling on `per_page` for an API that returns rich objects.

Then I checked what my own tool's two guards actually buy me, on the exact same 30 articles:

```python
shaped_bytes = len(json.dumps(shaped_list).encode())
# shaped (7 fields only): 8681 bytes for 30 articles, avg 289.4 bytes/article
# raw: 243050 bytes, avg 8101.7 bytes/article
# reduction: 96.4%
```

Stripping to `id`, `title`, `published`, `url`, `reactions`, `comments`, `page_views` cuts the per-article footprint by 96%. And because `per_page` is hard-capped at `min(per_page, 30)` before the request is even sent, calling `list_articles(per_page=1000)` today doesn't scale toward 8MB at all. It silently clamps to 30 articles and returns 8.7KB total, not 8MB. I hadn't verified that cap was actually load-bearing until I ran this; it was written for a different reason back in August (the un-suffixed `/articles/me` endpoint truncating drafts ahead of real posts, logged in `bugs.md` 2026-08-07), and it turns out to double as the thing standing between this tool and the exact failure mode the trending post describes.

The second thing I wanted to check was the "prompt cache misses" half of that post's title: the idea that even an unchanged tool call can bust your cache if the underlying data moves between calls. I called the same endpoint twice, 5 seconds apart, and diffed the results:

```python
a = dev_get("/articles/me/published?per_page=30")
time.sleep(5)
b = dev_get("/articles/me/published?per_page=30")
print(a == b)  # True, byte-identical
```

Byte-identical. Zero of 30 articles had any field change in that window, not even view counts. That surprised me going in, since I expected at least a view-count tick somewhere, but DEV.to's own data clearly doesn't update that fast, and over a 5-second gap there was nothing to invalidate a cache with. That doesn't mean the underlying concern is wrong in general: a tool backed by a more volatile data source (a live metrics endpoint, a ticketing system) absolutely could return different bytes on every call and defeat caching regardless of size. It just means I can't reproduce that specific failure mode against this particular API on this particular time window, and I'd rather say that plainly than borrow someone else's finding as if I'd confirmed it myself.

So: the size half of the trending claim checked out almost exactly against my own tool's raw numbers, and it turned up a reason my `per_page` cap matters that I hadn't previously connected to response size at all. The cache-miss half didn't reproduce here, at least not over 5 seconds on a slow-moving API, which is a useful boundary to know before I cite that mechanism as a reason to change anything in `server.py`.
