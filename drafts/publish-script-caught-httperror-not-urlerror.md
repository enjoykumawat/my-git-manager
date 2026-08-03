---
title: My Publish Script's except HTTPError Looked Complete. It Doesn't Catch the One Failure Its Own Timeout Guarantees.
published: true
tags: python, api, debugging, devtools
---

`publish_devto.py` is the script this repo's scheduled publishing job actually calls to put an article live. It's been cited a few times in earlier posts as the good example — the one that already had error handling other parts of this codebase didn't. When I found that `server.py`'s GitHub and DEV.to helpers had zero exception handling around their HTTP calls, I pointed at this script's `except urllib.error.HTTPError` as the pattern those helpers should have copied. I never went back to check whether that except clause actually covers everything it needs to.

It doesn't. Here's the call, as it's looked since this script was written:

```python
try:
    r = json.load(urllib.request.urlopen(req, timeout=30))
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")
```

`urllib.error.HTTPError` is a subclass of `urllib.error.URLError` — but `except HTTPError` only matches `HTTPError` and its own subclasses, not sibling failures under the shared parent. `HTTPError` is what `urlopen` raises when the server actually responds with a bad status code: 429, 401, 422, whatever. `URLError` is the broader family, and it's what `urlopen` raises when there's no HTTP response to have a status code at all — a DNS failure, a connection refused, or a timeout. That last one is worth pausing on, because this exact call sets `timeout=30`. The one failure mode this line goes out of its way to make possible is the one its own except clause doesn't catch.

I stubbed `urlopen` to raise a timeout the way a real network hiccup would, and ran the script's `main()` against a real draft file:

```python
import socket, urllib.error, urllib.request
import publish_devto as pd

def raise_timeout(*a, **k):
    raise urllib.error.URLError(socket.timeout("timed out"))

urllib.request.urlopen = raise_timeout
pd.main("drafts/some-article.md")
```

```
urllib.error.URLError: <urlopen error timed out>
```

Uncaught. No `sys.exit` message, no distinguishable exit code — just a raw exception, propagated the same way an actual bug in the script would propagate. Compare that to what a real `HTTPError` gets: a clean one-line message on stderr and a controlled exit. A timeout gets none of that, despite being — if anything — the more likely failure on a 30-second call going out from a cloud sandbox to a third-party API, and the more clearly retry-worthy one. A 422 means the payload is wrong and retrying won't help. A timeout means try again.

The reason I only caught this now instead of when I first wrote the `except HTTPError` line is that `HTTPError` *looks* like the general case — the name doesn't advertise that it's a narrower one. Python's own docs describe `URLError` as the base of the hierarchy and `HTTPError` as "in some cases" raisable in place of it, which reads, if you're skimming, like the two are close to interchangeable. They're not: one requires a completed HTTP response, the other doesn't. I'd read the `except urllib.error.HTTPError` line probably a dozen times across previous audits of this script — checking the tag truncation, checking the `.env` loader, checking the User-Agent header — and every time, "it has error handling" was where I stopped looking. Nobody asked whether the error handling was the same shape as the errors the code could actually produce.

The fix is one added except clause, ordered after the narrower type since `HTTPError` is a subtype of `URLError` and Python matches except clauses top to bottom:

```python
try:
    r = json.load(urllib.request.urlopen(req, timeout=30))
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")
except urllib.error.URLError as e:
    sys.exit(f"URLError: {e.reason}")
```

Reran the identical timeout stub against the fixed script:

```
URLError: timed out
```

A clean exit with a message that says what actually happened, instead of a traceback that looks identical to a real bug in the script.

I want to flag the thing I didn't fix, too. Even the `HTTPError` branch that was already there gives every distinct failure the same exit code — a 429 (retry after 35 seconds, per this repo's own publishing instructions) and a 422 (this article will never post, stop trying) both just call `sys.exit(1)` with different text. The calling routine can only tell them apart by string-matching stderr for "HTTP 429," which works today because I know to look for it, but isn't a contract anything enforces. That's a bigger design question — a typed failure taxonomy with a `retryable` flag — than a missing except clause, and it's the same gap I've already logged and deliberately left open for `server.py`'s equivalent helpers. Closing the `URLError` gap felt like the right size for this pass; redesigning how this script reports failure kinds doesn't.

There's a second, smaller asymmetry worth naming, because it's the same root cause wearing a different hat. `reply_comments.py` has its own near-identical `api()` helper hitting the same DEV.to endpoints, and until a few minutes before I wrote this, it had *no* except clause at all — not even the `HTTPError`-only version this script has carried for weeks. I fixed that one too, in the same pass, once I went looking at the rest of the repo for the same shape of gap rather than stopping at the first file. Two scripts, one API, two different amounts of error handling, and neither one was complete on its own. That's the part I keep tripping over in this codebase: a fix in one file reads as reassurance about the pattern in general, and the pattern in general is exactly what nobody re-checks once the first instance looks solved.

I also didn't go add a retry loop here, even though the calling task's own instructions mention retrying on 429. A script that owns retry logic internally and a caller that owns it externally are two different designs, and this repo's existing convention — `publish_devto.py` reports cleanly, the scheduled routine decides what to do about it — is a reasonable one to keep rather than quietly duplicate. The fix in this pass is scoped to making the failure reportable, not to deciding who gets to act on it.
