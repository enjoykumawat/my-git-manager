---
title: "The Real Security Boundary in My MCP Server Isn't the Tools — It's What They're Allowed to Write"
published: true
tags: mcp, security, python, agents
---

I've got a small FastMCP server in this repo — `server.py` — that gives Claude Desktop eight tools: three read GitHub, four touch DEV.to, one shells out to `claude -p` to write a commit message. When I actually sat down and sorted them by what they can do to the outside world instead of what they're named, the split surprised me: six of the eight are pure reads. Exactly two can change anything that persists past the call.

That's `create_article` and `update_article`. Everything else — `get_github_profile`, `list_repos`, `get_repo_stats`, `list_articles`, `get_article_stats`, `generate_commit_message` — returns data or text and leaves the world exactly as it found it. I didn't design it that way on purpose from day one. It fell out that way because the server started as "let me see my own stuff from inside Claude Desktop" and only grew write tools later, for one specific job: publishing drafts. But once I noticed the ratio, it became a question worth checking on purpose instead of by accident, because an MCP tool list reads like an API surface to the model calling it, and a model doesn't know "this one's basically a getter" unless the boundary is real, not just a naming convention.

### What "can write" actually means here

Neither write tool can touch GitHub. There's no `create_repo`, no `delete_repo`, no `update_repo_settings` — the GitHub side of this server is read-only by omission, not by a permission check, because I never wrote those tools. That's worth saying plainly: the strongest boundary in this codebase isn't a guard clause, it's a missing function. You can't call what doesn't exist.

The two tools that *do* write only ever write to one thing: a DEV.to article, identified by an id the caller passes in or that `create_article` hands back. There's no tool that deletes an article, no tool that touches another user's content, no tool that writes to this repo's own git history or filesystem. The entire footprint of "an agent using this server could mess something up" is bounded to "my own DEV.to posts, created or edited through these two functions."

### The part that's actually interesting: what guards those two

Having a small write surface doesn't matter much if the two functions on it have no guardrails. So here's what `create_article` actually checks before it POSTs anything, straight from the code:

```python
def create_article(title: str, body_markdown: str, tags: list[str] | None = None, published: bool = False) -> dict:
    if published:
        for a in _all_published_titles():
            if a.get("title") == title:
                return {"id": a["id"], "url": a.get("url"), "published": True, "already_published": True}
    payload = {"article": {"title": title, "body_markdown": body_markdown, "published": published}}
    if tags:
        payload["article"]["tags"] = tags[:4]
    result = _dev("/articles", method="POST", data=payload)
    return {"id": result["id"], "url": result.get("url"), "published": result.get("published")}
```

The duplicate-title check exists because of a very specific failure mode logged in this repo's own history: a POST can succeed server-side and still hand the caller back nothing but a timeout. An MCP client that retries the same "publish this" call after an ambiguous network error doesn't know it already worked — without that loop over already-published titles, a retry creates a second live article for one intended publish. That's not a hypothetical; it's the same class of bug `publish_devto.py`, the separate script the scheduled publishing task calls directly, had to be hardened against too.

`update_article` carries more weight, because editing an existing live post is a riskier operation than creating a new one — you can clobber something that was fine. It fetches the article's current state before doing anything else:

```python
def update_article(article_id: int, title: str | None = None, body_markdown: str | None = None,
                    published: bool | None = None, confirm: bool = False,
                    expected_fingerprint: str | None = None) -> dict:
```

`confirm` defaults to `False`. Calling this without it returns a preview — the diff, not the write. The model (or whoever's driving Claude Desktop) has to see what's about to change and explicitly ask for it a second time with `confirm=True`. That two-step shape is deliberate: a wrong or hallucinated `article_id` used to silently overwrite whatever it pointed at with no trace, before the before/after logging existed. Now every write that changes a published article's content lands in `logs/article_updates.jsonl` with the specific fields that changed and their before/after values — not a fixed title/published pair that tells you nothing when `body_markdown` was the actual field that moved.

`expected_fingerprint` closes a narrower gap a real reader found in a comment on the article where this exact mechanism first shipped: the preview is computed from version A of the article, someone edits it to version B in between, and the originally-approved `confirm=True` call still fires against the now-stale diff. Passing the fingerprint from the preview call back into the confirm call proves nothing moved underneath it in the meantime. It's optional on purpose — a caller that never previewed at all, and is knowingly forcing a specific title regardless of current content, is a legitimate and different use case that this shouldn't block.

### Where the boundary still has a hole

I'm not going to pretend this is airtight, because it isn't, and the honest version of this post says so. `create_article`'s duplicate-title guard only runs when `published=True` is passed on that same call — by design, drafts skip it entirely, since a draft isn't live yet and isn't the thing the guard exists to protect. But `update_article` is a completely separate code path to that exact same end state (published, with a title, with a body), and it never inherited either version of the check. Create two drafts with the identical title through `create_article(published=False)`, then publish each one separately through `update_article(article_id, published=True)` — nothing compares the two titles across tools, and both go live with the same title, the exact outcome the create-side guard exists to prevent. I verified this live against a stubbed `_dev`: one GET, one PUT, zero calls to the published-titles list anywhere in the trace.

That's the actual lesson, more than "two tools write and six don't." A write boundary measured at the tool level — "only these two functions can touch the outside world" — doesn't tell you the boundary is consistent. The same end state is reachable two different ways, and only one of those ways got the check. Counting which tools can write is the easy audit. Checking whether every path *into* those tools carries the same guard is the one that actually matters, and it's the one I'd skipped until writing this forced me to trace both paths side by side instead of trusting that the code I remembered writing for `create_article` also covered `update_article` just because they end up at the same place.
