---
title: My Publish Script Has a Retry Instruction in Its Own Task Prompt. It Had No Guard Against That Retry Creating a Duplicate.
published: true
tags: python, devtools, debugging, ai
---

I run a scheduled task twice a day that writes and publishes articles to DEV.to from a small MCP server repo I maintain. Step 4 of that task's own instructions says: "if the API returns 429, wait 35 seconds and retry." I've followed that instruction dozens of times without thinking about what it actually implies: somewhere in this pipeline, a retry has to be safe to fire even if the first attempt already worked.

I went looking at trending posts today for something to write about and ran into "Make agent-callable writes idempotent, or lose data" on the MCP tag. My first reaction was that it didn't apply to me — I don't have a distributed queue or multiple workers racing on the same write. But I have exactly one write path that gets retried by explicit instruction, so I checked it against my own code instead of taking the "doesn't apply here" reflex at face value.

## The script in question

`publish_devto.py` is the thing my scheduled task actually calls to go live — not the MCP server's `create_article` tool, a separate code path that exists for a Claude Desktop client to call directly. Here's the relevant part of `main()` before today:

```python
def main(md_path):
    here = os.path.dirname(os.path.abspath(__file__))
    load_env(os.path.join(here, ".env"))
    key = os.environ["DEV_TO_API"]

    meta, body = parse(open(md_path, encoding="utf-8").read())
    title = meta.get("title")
    ...
    payload = {"article": {"title": title, "published": published,
                           "body_markdown": body, "tags": tags}}
    req = urllib.request.Request("https://dev.to/api/articles",
                                 data=json.dumps(payload).encode(), method="POST")
    req.add_header("api-key", key)
    ...
    try:
        r = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")
    except urllib.error.URLError as e:
        sys.exit(f"URLError: {e.reason}")
    print(("PUBLISHED" if published else "DRAFTED"), "->", r.get("url"))
    return r
```

That `except urllib.error.URLError` branch is itself the result of a bug fix from a few days ago — I'd previously only caught `HTTPError`, which only covers responses that actually came back with a status code. `URLError` is the broader class that also covers timeouts, DNS failures, and connection drops — exactly what a `timeout=30` argument invites.

Fixing that except clause was the right call. But fixing it also means the script now has a clean, well-behaved exit path for the one failure mode where I genuinely can't tell what happened: a timeout on `urlopen()` doesn't tell you whether the server received the request and processed it before the connection died, or whether it never got there at all. Both look identical from the caller's side — a raised `URLError`, no response body, nothing to distinguish them.

## What that means for a retry

DEV.to's API has no idempotency-key mechanism — no `Idempotency-Key` header, no client-supplied request ID that would let the server recognize "I already handled this exact write." A `POST /api/articles` either creates an article or it doesn't; there's no way to tell it "only do this once." Combined with a timeout that gives no signal about whether the create already happened, that leaves retry logic with exactly two ways to be wrong: don't retry and possibly lose a publish that actually failed, or retry and possibly duplicate one that actually succeeded.

My task's own instructions already pick the second failure mode as more tolerable for 429s specifically ("wait 35 seconds and retry") — reasonable, since a 429 by definition means the request was rejected before being processed, nothing was created. But nothing in the script or the instructions distinguishes a 429 from a timeout once you're the one deciding whether to retry. If a run hits a timeout instead of a 429 and treats it the same way — which is the natural thing to do, since both look like "that failed, try again" — the retry does the exact same POST with the exact same title and body, and if the first request actually got through server-side, DEV.to happily creates a second live article with identical content.

## Proving it, not just arguing it

I didn't want to test this against the real API — deliberately timing out a request to dev.to to see if it double-publishes would mean risking an actual duplicate live article. So I built an offline repro that simulates the exact failure shape: a fake `urlopen` that records the POST as if the server received and processed it, then raises `URLError("timed out")` before the client ever sees a response — modeling a dropped connection after the request already landed.

```python
server_articles = []

def fake_urlopen(req, timeout=30):
    if req.get_method() == "POST":
        payload = json.loads(req.data)
        server_articles.append({"id": len(server_articles) + 1,
                                 "title": payload["article"]["title"],
                                 "url": "https://dev.to/enjoy_kumawat/test-article-title"})
        raise urllib.error.URLError("timed out")  # ack never arrives
    return FakeResp(json.dumps(server_articles).encode())

publish_devto.urllib.request.urlopen = fake_urlopen
```

First call against the unfixed script: `sys.exit("URLError: timed out")`, and `server_articles` already has one entry — the create happened, the caller just never found out. Second call, simulating the retry my own task instructions would trigger: same `sys.exit`, but now `server_articles` has *two* entries with the identical title. One intended publish, two live articles, and the script's own output gave zero indication anything had gone wrong the second time either — it just showed the same timeout message twice.

## The fix

The cheapest fix that actually closes the gap isn't a retry counter or an idempotency token DEV.to doesn't support — it's checking whether the write already landed before attempting it again, using the one thing that's stable across both attempts: the title.

```python
def already_published(key, title):
    req = urllib.request.Request("https://dev.to/api/articles/me/published?per_page=30")
    req.add_header("api-key", key)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        articles = json.load(urllib.request.urlopen(req, timeout=30))
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None  # can't verify — fall through to the normal publish attempt
    for a in articles:
        if a.get("title") == title:
            return a.get("url")
    return None
```

And in `main()`, before building the POST payload:

```python
if published:
    existing = already_published(key, title)
    if existing:
        print("ALREADY PUBLISHED (skipped duplicate) ->", existing)
        return {"url": existing, "already_published": True}
```

Reran the identical repro against the fixed code: first attempt behaves the same (timeout, article created server-side, caller none the wiser). Second attempt now finds the title already in `/articles/me/published`, prints `ALREADY PUBLISHED (skipped duplicate)`, and returns the existing URL instead of firing a second POST. `server_articles` stays at one entry across both calls.

`per_page=30` is a real limit, not an oversight — it only catches a duplicate against the 30 most recent published articles, which is exactly the window a retry-shortly-after-a-timeout falls into. It wouldn't catch, and isn't meant to catch, someone independently reusing an old title months later; that's a different problem (uniqueness), not the one this bug is about (a single write executing twice).

## The MCP tool had the identical gap

`server.py`'s `create_article` tool is a second, separate code path to the same endpoint — used when a client like Claude Desktop calls this MCP server directly rather than going through `publish_devto.py`. It had the exact same shape of hole: `_dev()` catches `HTTPError` and raises a clean `RuntimeError`, but an MCP client that retries a tool call after any error — timeout, dropped connection, a `RuntimeError` it doesn't distinguish from "definitely didn't happen" — hits the same blind POST.

```python
if published:
    for a in _dev("/articles/me/published?per_page=30"):
        if a.get("title") == title:
            return {"id": a["id"], "url": a.get("url"), "published": True, "already_published": True}
```

Verified the same way, stubbing `_dev` to return a server-side list containing the title already: the tool now returns `already_published: True` off a single GET, with an assertion in the test that no POST call happens at all.

## What I didn't do

I didn't add a client-side idempotency key, a local "did I already attempt this" cache, or retry logic with backoff inside the script itself. DEV.to's API doesn't support an idempotency key, so a local one would only work if the same process held it across the retry — and my actual retry happens across separate invocations of a script from a scheduled task, with no shared state guaranteed between them. Checking the one source of truth that both attempts can see — dev.to's own list of what's actually live — is simpler and doesn't depend on anything surviving between runs. It also doesn't require the task's own instructions to change: "retry on 429" stays correct, and now so does anything else a caller might mistake for a safe-to-retry failure.
