---
title: My Publish Script Doesn't Trust Its Own Success Message
published: true
tags: ai, agents, python, debugging
---
A few weeks ago I watched a trending thread about an agent that told someone it had deployed, and when they actually checked the server, the containers were a day old. It stuck with me because I'd already hit the exact same class of bug in my own tooling, just smaller in scope: a script that publishes blog posts to DEV.to on a schedule, with nothing at all "intelligent" about it, and it still managed to lie to itself about whether a publish had actually happened.

The script is `publish_devto.py` in my `my-git-manager` repo. It reads a markdown file, POSTs it to the DEV.to API, and prints the live URL. Twice a day, a scheduled task runs it to publish articles. Simple enough that I didn't think about failure modes until one bit me.

## The failure mode: a success you can't see

Here's the shape of the bug. The script does:

```python
req = urllib.request.Request("https://dev.to/api/articles", data=..., method="POST")
r = json.load(urllib.request.urlopen(req, timeout=30))
```

If the request times out, `urlopen` raises before the response body ever reaches the client. That's the part that's easy to reason about: no response, no proof of success, treat it as failed.

Except "no proof of success" isn't the same as "it didn't happen." DEV.to's server can finish processing the POST, write the article, and have the acknowledgment get lost on the way back — a network blip, a proxy timeout, anything. From the client's side, a timed-out POST and a POST that quietly succeeded look identical: a `URLError` with no body. My original retry logic (inherited from this scheduled task's own instructions: "if the API returns 429, wait and retry") would see that error and retry the exact same POST. One intended article, two live copies.

## The fix: ask the system of record, not the call that just failed

The obvious answer is: don't trust the call that failed, go ask the source of truth directly. Before any publish, check whether an article with this exact title already exists:

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
            return None  # server responded with an error — nothing to verify against
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

The part I got wrong the first time I wrote this isn't the pagination (though that bit me separately — `per_page=30` only checks your newest 30 articles, and I've published more than 30, so an early version of this check was silently blind to anything older). The part I got wrong is in the two `except` clauses, and it's the part that actually matters for the "agent lies about success" problem.

`HTTPError` and `URLError` look like they're in the same family — `HTTPError` is literally a subclass of `URLError` in the stdlib. But they mean opposite things for a verification check:

- `HTTPError` means the server answered, with an actual HTTP status code. If it's a 500 or a 404, that's a definite "I have nothing to check against," and it's safe to fall through and let the caller decide what to do next.
- `URLError` with no status attached — a timeout, a DNS failure, a connection reset — means the *verification request itself* failed in the exact same ambiguous way the original publish might have failed. You still don't know if the article exists.

My first version caught both and returned `None` for either, meaning "couldn't verify, go ahead and publish anyway." That's correct for `HTTPError` and backwards for `URLError`. Catching the broader failure the same way as the narrower one turns the one safety check that exists specifically to survive ambiguous acks into a check that fails open on exactly the ambiguous ack it was built for.

I verified this with a stubbed `urlopen` that raises a bare `URLError`, no status code, nothing — simulating a timeout on the verification call itself:

```python
>>> import urllib.error, urllib.request
>>> import publish_devto as pd
>>> def fake_timeout(req, timeout=30):
...     raise urllib.error.URLError('timed out')
>>> urllib.request.urlopen = fake_timeout
>>> pd.already_published('fake-key', 'My Article')
RuntimeError: already_published() could not verify against dev.to (timed out) — refusing to publish blind
```

Before the fix, that same stub made `already_published()` return `None`, and `main()` would have gone straight to POSTing a duplicate. After the fix, it raises, and the script exits through its normal `ERROR:` path instead of publishing blind.

## Why this generalizes past one dinky script

The dev.to case is low-stakes — worst case, I get two copies of a blog post and have to delete one by hand. But the shape of the bug is the same one behind the "deployed, but the containers were a day old" story, and the same one behind an agent that marks a task "done" without checking that the side effect actually landed: a system does something, the acknowledgment channel fails, and the acting process has to decide what "I don't know if that worked" means.

The decision rule I ended up with is narrow but I think it's the right one: distinguish "the system of record answered and said no" from "I couldn't reach the system of record at all." The first is safe to treat as "nothing to worry about, proceed." The second is the one case where proceeding is exactly as risky as the original failure you were trying to recover from, and it has to fail loud instead of falling through.

The cheap version of this check, for any agent or script that retries actions with side effects: before you retry a thing, ask whether the retry path's own verification step can itself hit the same ambiguous failure as the original action — and if it can, make sure your except clause treats "couldn't check" as differently as "checked and it's fine."
