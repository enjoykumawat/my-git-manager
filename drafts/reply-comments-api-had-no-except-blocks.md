---
title: My Comment-Reply Script's Only Network Call Had Zero except Blocks. I'd Already Fixed This Exact Bug in a Different File.
published: true
tags: python, debugging, devtools, ai
---

This repo runs a small unattended pipeline for replying to comments on my DEV.to articles. DEV.to's API won't let a normal account key post comments or reactions programmatically (`POST /api/comments` is a 404, `POST /api/reactions` is a 401 — I confirmed both a while back), so the pipeline drafts replies into a markdown file and I paste them by hand. Everything upstream of that manual step — `pending()` to find comments that need a draft, `audit()` to check whether a drafted reply actually made it onto the live thread — runs twice a day with nobody watching.

Both of those functions sit on top of one helper, `api()`, in `reply_comments.py`:

```python
def api(path):
    req = urllib.request.Request("https://dev.to/api" + path)
    req.add_header("api-key", os.environ.get("DEV_TO_API", ""))
    req.add_header("User-Agent", "Mozilla/5.0")
    return json.load(urllib.request.urlopen(req, timeout=30))
```

No `try`, no `except`. Just a request, a header, and `urlopen`.

I found this while going back through the repo looking for anything that hadn't already been picked over — this file in particular has had three separate rounds of fixes, all in the tree-walking logic that decides *which* comment needs a reply: a recency bug in `needs_reply()`, a one-level-deep bug in `audit()`, a dedup key that pointed at the wrong node in `pending()`. Three fixes, three different functions, all downstream of `api()`. Nobody had ever looked at `api()` itself.

And the reason that stung a little is that I'd already fixed this exact shape of bug once, in a completely different file. A few weeks back I found that `server.py` — the MCP server this repo also runs — had two HTTP helpers, `_gh()` for GitHub and `_dev()` for DEV.to, with the identical problem: no exception handling around `urlopen()`, so any `HTTPError` (a bad id, an expired token, a 429 rate limit) crashed straight through as a raw, unlabeled traceback. I fixed both, wrapping them so a bad call turns into a clean `RuntimeError` with the status code and response body instead of an opaque stack trace.

What I didn't do at the time was ask whether anything else in the repo made the same kind of call the same way. `reply_comments.py`'s `api()` talks to the exact same DEV.to API, over the exact same `urlopen()`, and I wrote it back before any of that hardening happened. It just never came up again, because every time I opened this file afterward I was looking at the tree-walking bugs, not the network call underneath them.

I checked the failure was real instead of assuming the shape transferred. Stubbed `urlopen` to raise a 429:

```python
import urllib.error, urllib.request
import reply_comments as rc

def raise_429(*a, **k):
    raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)

urllib.request.urlopen = raise_429
rc.api("/comments?a_id=1")
```

```
urllib.error.HTTPError: HTTP Error 429: Too Many Requests
```

Uncaught, straight out of `api()`, straight out of `pending()`, straight out of the whole run. The scheduled task that calls this script has a documented retry rule for 429s elsewhere in its instructions — wait 35 seconds and retry — but that rule only helps if something catches the error to retry on. Here, a rate limit or a flaky 5xx during the comment-check run doesn't degrade into "try again next time." It kills the run with a raw traceback, no different from a bug in the code itself.

The fix mirrors exactly what I did in `server.py`, because there was no reason to invent something new:

```python
def api(path):
    req = urllib.request.Request("https://dev.to/api" + path)
    req.add_header("api-key", os.environ.get("DEV_TO_API", ""))
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"dev.to API error {e.code}: {e.read().decode()[:400]}") from e
```

Reran the same stub against the fixed function:

```
RuntimeError: dev.to API error 429:
```

A clean, typed exception with the status code attached, instead of a bare `HTTPError` object with no context about what call produced it or why.

What I keep relearning from this repo is that fixing a bug in one place doesn't inventory the rest of the codebase for the same shape — it just makes the code you *did* touch look more trustworthy, which is precisely what makes the sibling copy easy to walk past. `_gh()` and `_dev()` live in `server.py`, get imported by an MCP client, and get exercised every time a tool call goes out. `api()` lives in a standalone script two files over, gets called by a cron-triggered Python process with nobody reading its stderr, and does the identical job with the identical library call. The second one is arguably the one that needed the fix more, since a crash here has no human in the loop to notice and retry manually — and it's also the one I forgot to check.

I still haven't gone looking for a fourth copy of this pattern anywhere else in the repo. Past experience with this codebase says I probably should.
