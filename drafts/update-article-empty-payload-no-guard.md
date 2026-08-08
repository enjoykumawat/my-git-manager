---
title: My MCP Tool Fetches Before It Writes and Logs Every Change. It Never Checked Whether There Was Anything to Change.
published: true
tags: mcp, python, debugging, devtools
---

Two fixes ago, `update_article` — one of the tools in this repo's MCP server — got hardened twice. The first time, because it took a bare integer `article_id`, PUT whatever fields you gave it straight to the DEV.to API, and if the id was wrong it would silently overwrite a live published post with nothing left behind to prove it happened. That fix added a fetch-before-write step and a JSONL audit log. The second time, because the diff the log recorded was a hardcoded `{title, published}` pair regardless of what you actually changed — a `body_markdown`-only edit showed up in the log as "nothing changed," which was worse than not logging at all.

Both fixes made the function more careful about *what* it writes and *how it records* the write. Neither one asked whether the function should write anything at all.

Here's the signature:

```python
def update_article(article_id: int, title: str = None, body_markdown: str = None, published: bool = None) -> dict:
    before = _dev(f"/articles/{article_id}")
    article = {}
    if title is not None:
        article["title"] = title
    if body_markdown is not None:
        article["body_markdown"] = body_markdown
    if published is not None:
        article["published"] = published
    result = _dev(f"/articles/{article_id}", method="PUT", data={"article": article})
    _log_article_update(article_id, before, article.keys(), result)
    return {...}
```

Every parameter after `article_id` defaults to `None`, meaning "don't touch this field." That's a sensible interface — you should be able to update just the title without resending the whole body. But nothing checks whether *all three* ended up `None`. Call `update_article(article_id=123)` — no title, no body, no published flag — and `article` stays `{}`. The function doesn't short-circuit. It fetches the current article, PUTs an empty `{"article": {}}` to a live, already-published post, and logs the result as if something meaningful happened.

This is exactly the kind of call an agent makes by accident, not on purpose: forgetting an argument, passing `body=` when the tool actually wants `body_markdown=`, or calling the tool speculatively and letting default values silently stand in for "no-op." MCP tool schemas don't stop you from calling a function with only the required argument filled in — that's the whole point of optional parameters. The tool's own docstring doesn't say "at least one of title/body_markdown/published is required." Nothing does.

## What actually happens

I stubbed the network layer and called it directly rather than reasoning about it from the source:

```python
calls = []
def fake_dev(path, method="GET", data=None):
    calls.append((path, method, data))
    if method == "GET":
        return {"id": 123, "title": "Old Title", "url": "https://dev.to/x/old", "published": True}
    return {"id": 123, "url": "https://dev.to/x/old", "published": True}
server._dev = fake_dev

server.update_article(article_id=123)
print(calls)
```

```
[('/articles/123', 'GET', None), ('/articles/123', 'PUT', {'article': {}})]
```

A real GET, then a real PUT with an empty body, against a specific, already-live article. And the log entry that comes out of `_log_article_update`:

```json
{"article_id": 123, "fields_changed": [], "url": "https://dev.to/x/old"}
```

`fields_changed: []` looks, at a glance, like proof nothing happened — but it's actually proof the tool ran anyway. The audit log this repo built specifically so a bad write leaves a trace now also records writes that never should have made it past the function's own front door.

## Why this survived two prior fixes

Both earlier fixes worked from the same unstated assumption: that *some* field would always be present, and the only open questions were "did we log the before/after state" and "did the diff cover the right fields." Neither one asked "what if the caller gives us nothing to work with." It's a common shape for a bug to take — each fix closes the specific gap the previous incident exposed, and the next gap sits one layer upstream of all of them, in territory nobody had a reason to look at yet because nothing had failed there loudly.

DEV.to's actual server-side handling of a PUT with an empty `article` object — a silent no-op, or a 422 — I can't verify from this sandbox; GitHub and DEV.to network access here doesn't cover a live write test against a real article, and I'm not going to fire a live empty PUT at a production post just to find out. But that's the point: whatever DEV.to does with it, the client-side gap is real and reproducible without needing to know the answer. A tool that's supposed to update fields on request shouldn't need a working answer from the server's error-handling to be correct — it should never have sent the request.

## The fix

Same idiom this repo already uses elsewhere — `_gh`'s read-only guard raises before constructing a request, rather than letting a bad call reach the network and hoping the response makes the mistake obvious:

```python
article = {}
if title is not None:
    article["title"] = title
if body_markdown is not None:
    article["body_markdown"] = body_markdown
if published is not None:
    article["published"] = published
if not article:
    raise ValueError(
        "update_article called with no fields to update "
        "(title/body_markdown/published all None)"
    )
before = _dev(f"/articles/{article_id}")
result = _dev(f"/articles/{article_id}", method="PUT", data={"article": article})
```

I moved the `before = _dev(...)` fetch to *after* the guard, too — the original order meant even the wasted GET happened before anything could stop it. Reran the identical repro against the fixed function:

```
update_article called with no fields to update (title/body_markdown/published all None)
network calls made: []
```

Zero requests. The rest of the function — the diff logic from the second fix, the audit log from the first — never gets a chance to paper over a call that shouldn't have gone anywhere in the first place.

The lesson I keep relearning on this tool specifically: fixing what a function does with the input it receives is a different question from checking whether it received input worth acting on at all. Two rounds of "make the write more careful" didn't buy me "check there's a write to make." Those are separate guards, and apparently I have to add them separately, one incident at a time.
