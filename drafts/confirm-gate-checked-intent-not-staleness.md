---
title: My Confirm Gate for Overwriting a Live Article Checked That I Meant It. It Never Checked Whether What I Approved Was Still There.
published: true
tags: mcp, security, python, debugging
---

Earlier today I shipped a fix to `update_article`, one of the tools in the MCP server I run for my DEV.to account. The bug was straightforward: the tool would fetch an article, compute a diff, log it, and then fire the PUT — all in one call, no gate. If I passed the wrong `article_id`, or an LLM hallucinated one, a live published article got silently overwritten. DEV.to keeps no version history, so that overwrite is gone for good. The fix was a `confirm: bool = False` parameter. Call it without `confirm=True` and you get the proposed diff back with `applied: False` — nothing touches the network. Call it again with `confirm=True` and the write goes through. Simple, and it closed a real gap: a diff and an audit log tell you what happened after the fact, but neither one stops anything.

A few hours after that article went live, a reader left a comment that took the design apart in one sentence:

> "the preview is computed from version A, another editor changes the article to B, and the agent then sends the approved write... the diff a person reviewed is no longer necessarily the write that lands."

I read that and immediately knew it was right, because I could see exactly where in the code it would happen. `update_article` fetches `before` fresh on *every* call — including the confirmed one. That fetch already proves whether the article changed since I last looked at it. It just never got compared against anything. The confirm flag only proves I meant to write. It says nothing about whether the thing I approved still matches what's live.

Here's the shape of the problem, stripped down to a repro:

```python
# Call 1: preview
preview = update_article(article_id, title="Agent's New Title")
# -> {"applied": False, "diff": {"title": {"before": "Original Title", "after": "Agent's New Title"}}}

# ...time passes. Someone edits the article directly on dev.to,
# or a second tool call touches it. The live title is now something else.

# Call 2: the approved write
result = update_article(article_id, title="Agent's New Title", confirm=True)
# -> applies unconditionally, clobbering whatever the intervening edit set
```

Before the fix, I reproduced this against the real function with a stubbed `_dev()`: preview call, simulate an out-of-band edit, then fire the confirmed call. The PUT went through and silently discarded the intervening state. That's the actual bug, not a hypothetical — a human approving a diff isn't approving a write, they're approving a write *conditioned on the article still looking like what they reviewed*, and nothing enforced that condition.

The fix is a fingerprint, not a lock. `update_article` already has the article's current `title` and `body_markdown` in hand every time it fetches `before` — so it hashes them:

```python
def _article_fingerprint(before):
    basis = "\x1f".join(f"{f}={before.get(f)!r}" for f in ("title", "body_markdown"))
    return hashlib.sha256(basis.encode()).hexdigest()[:16]
```

The preview response now includes that fingerprint. A caller that wants staleness protection captures it and passes it back as `expected_fingerprint` on the confirmed call:

```python
before = _dev(f"/articles/{article_id}")
live_content_write = before.get("published") and ("title" in article or "body_markdown" in article)
fingerprint = _article_fingerprint(before)

if live_content_write and expected_fingerprint is not None and expected_fingerprint != fingerprint:
    return {
        "id": article_id,
        "applied": False,
        "reason": "stale — the live article changed since the diff you approved was "
                  "generated; re-preview and re-approve against the current content",
        "fingerprint": fingerprint,
        "diff": {...},
    }
```

I made `expected_fingerprint` optional on purpose. A caller that skips the preview entirely and calls `confirm=True` on the first shot — deliberately forcing a specific title regardless of what's currently live — is a real, different use case. Making the check mandatory would have broken that path for no benefit; making it opt-in means the exact behavior I shipped this morning still works unchanged for anyone who doesn't ask for staleness protection.

Verified live, same repro as before, now with the fingerprint wired through:

```
PREVIEW: {'applied': False, 'fingerprint': 'e100d7fa...', 'diff': {'title': {...}}}
LIVE STATE CHANGED IN BETWEEN: "Someone Else's Manual Edit In Between"
CONFIRMED (no fingerprint — old call shape): applied: True
  -> unchanged behavior for callers who don't opt in
CONFIRMED (stale fingerprint passed): applied: False, reason: "stale — ..."
  -> the in-between edit survives
```

The old, unprotected call shape still works exactly as it did this morning — nothing breaks for a caller that hasn't adopted the new parameter. The protected path now refuses to clobber a change it never saw. I added four cases to the existing `--selftest` block: preview, out-of-band edit, stale-confirm gets blocked with zero PUT calls reaching the network; re-preview picks up the new fingerprint and a matching confirm applies cleanly; and a backward-compat case pinning that `confirm=True` with no `expected_fingerprint` still behaves exactly like it did before this fix. All six `--selftest`-bearing scripts in the repo still pass after the change.

What actually got me here wasn't a deeper read of my own code — it was a stranger, on a public comment thread, pattern-matching the shape of TOCTOU in about thirty seconds from a description of the gate alone. I'd built the fetch that proves staleness and then just never asked the question the fetch could already answer. The lesson isn't "add fingerprints to your APIs." It's that a confirmation step and a validity check are two different guarantees, and a design that only implements the first one will look complete right up until someone points out it isn't.
