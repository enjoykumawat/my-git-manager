---
title: My MCP Tool Logged Every Overwrite of a Live Article. Nothing Ever Stopped the Overwrite.
published: true
tags: mcp, security, python, debugging
---

I keep seeing the same shape of post on here lately: someone built a "gatekeeper" in front of their AI agent's tools, or asked who's actually authorizing an agent plugin's capabilities at runtime. It made me go back and check something I'd been assuming was fine in my own MCP server — the DEV.to tools I use to manage this exact blog.

`server.py` has two write tools: `create_article` and `update_article`. I've hardened `update_article` twice already. The first time (`bugs.md`, 2026-07-27) was because it took a bare integer `article_id`, sent whatever fields you gave it straight through as a PUT, and if the id was wrong or hallucinated it silently overwrote whatever article that id happened to point at, with nothing left behind to show it had happened. I fixed that by fetching the article first and computing a diff:

```python
before = _dev(f"/articles/{article_id}")
result = _dev(f"/articles/{article_id}", method="PUT", data={"article": article})
_log_article_update(article_id, before, article.keys(), result)
return {
    "id": result["id"],
    "diff": {field: {"before": before.get(field), "after": result.get(field)}
             for field in article},
}
```

That felt like real progress at the time, and in one sense it was — a wrong write now leaves a trace instead of vanishing silently. But rereading it next to this week's trending "who authorizes an agent's tool calls" posts, I noticed what it actually does: it computes the diff, then writes, then logs. The authorization step — the part where something decides whether this write should happen — doesn't exist anywhere in that sequence. `before` gets fetched, the PUT fires unconditionally, and the diff gets reported after the fact. A "gate" that only ever opens isn't a gate. It's a receipt printer.

Compare that to the other write-capable credential in this same file. `_gh()`, the GitHub API helper, has an actual hard block:

```python
def _gh(path, method="GET", data=None):
    if method != "GET" or data is not None:
        raise ValueError("_gh is read-only — no tool in this file should ever write to GitHub")
    ...
```

`GITHUB_TOKEN` is scoped `repo, user` — full write access — but every GitHub tool in this server only ever needs to read, so `_gh()` refuses to be anything else, unconditionally, regardless of what any caller asks for. That's a real authorization boundary: no argument, no flag, no confirm — writes to GitHub are categorically off. `_dev()`, the DEV.to equivalent, has no such thing, because `create_article` and `update_article` legitimately need to write. Fair enough — but "legitimately needs to write sometimes" got treated as "should write whenever asked, no questions," and those aren't the same claim.

The part that actually worried me: DEV.to keeps no version history for an article. There's no revision log, no undo, nothing server-side to recover a previous `body_markdown` once a PUT overwrites it. My diff-and-log fix tells me exactly what changed — after a live post I can't get back is already gone. For a brand-new draft that's a non-issue; you can always PUT again. For something already published and read, it isn't.

## The fix

I added a `confirm` parameter that only matters when both things are true: the article is currently published, and the write would actually change `title` or `body_markdown` — the parts a reader sees, not just the `published` flag itself.

```python
before = _dev(f"/articles/{article_id}")
live_content_write = before.get("published") and ("title" in article or "body_markdown" in article)
if live_content_write and not confirm:
    return {
        "id": article_id,
        "url": before.get("url"),
        "applied": False,
        "reason": "article is currently published — title/body_markdown changes "
                  "require confirm=True (DEV.to has no version history to undo this)",
        "diff": {field: {"before": before.get(field), "after": article.get(field)}
                 for field in article},
    }
result = _dev(f"/articles/{article_id}", method="PUT", data={"article": article})
```

Unconfirmed, the tool now returns the exact diff it would have applied — same shape as a real write's return value, minus `applied: True` — without touching the network. The caller (me, or whatever agent is driving this session) sees precisely what would change, and has to ask again with `confirm=True` to make it real. A draft never hits this branch at all, since there's nothing live to lose. Neither does toggling `published` on its own with no content change — that's reversible, so it doesn't need the same friction.

I tested it against a stubbed `_dev()` rather than a real article, three cases: unconfirmed write to a published article must return the diff and never call PUT; the same call with `confirm=True` must actually PUT; and a draft (`published: False`) must apply immediately with no confirm required at all, since gating something that was never live protects nothing.

```python
def _fake_dev_update(path, method="GET", data=None):
    if method == "GET":
        return dict(_live_article)
    _put_calls["n"] += 1
    return {"id": 42, "url": "https://x/42", "published": True, **data["article"]}

unconfirmed = update_article(42, title="new title")
assert unconfirmed["applied"] is False
assert _put_calls["n"] == 0

confirmed = update_article(42, title="new title", confirm=True)
assert confirmed["applied"] is True
assert _put_calls["n"] == 1
```

All three pass, and the rest of this file's existing `--selftest` suite — the pagination fix, the credential-missing checks, the `_gh` read-only guard — still passes too, since none of them touch `update_article`'s write path.

## What I'm not claiming

This isn't a general authorization framework, and I didn't build one. It's one narrow gate on one tool, scoped to the one failure mode that's actually irreversible here — overwriting live, already-read content with no way to get it back. The trending "gatekeeper" posts this week describe something broader: a policy layer deciding, per call, whether an agent's requested action is allowed at all. What I have is much smaller — a single boolean that turns "execute immediately" into "propose, then execute only if asked twice." But it's the difference between a log that tells you what already broke and a check that has a chance to stop it before it does. My `update_article` only had the first one. Now it has both.
