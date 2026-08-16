---
title: The Permission Boundary My MCP Server Doesn't Actually Have
published: true
tags: mcp, agents, security, python
---

There's a theme showing up a lot in agent-tooling posts this week: agents holding tools they can misuse, and builders wiring some kind of gate in front of the dangerous ones — a signed capability, a policy layer, a human-in-the-loop check before the write actually lands. I built something that looks like that gate a while ago. Then I went and read my own code closely enough to notice it isn't one.

The tool in question is `update_article` in the MCP server I run for my DEV.to publishing pipeline. It edits a live article by id — title, body, published flag. Overwriting a *published* article's content is the dangerous case: DEV.to keeps no version history, so a bad write is gone the moment it lands. Back in July I added a gate for exactly that:

```python
live_content_write = before.get("published") and ("title" in article or "body_markdown" in article)
...
if live_content_write and not confirm:
    return {
        "id": article_id,
        "url": before.get("url"),
        "applied": False,
        "reason": "article is currently published — title/body_markdown changes "
                  "require confirm=True (DEV.to has no version history to undo this)",
        ...
    }
```

Call it without `confirm=True` against a live article and you get the proposed diff back, not a write. That felt like a permission boundary. It is not one, and the reason took me embarrassingly long to see: `confirm` is a keyword argument the caller supplies. There is no code path that *forces* an agent through the preview step before it can set `confirm=True`. An agent that has never seen the docstring, or that decided on its own the article needed fixing right now, can call `update_article(id, body_markdown=new_body, confirm=True)` as its very first move and the gate simply isn't there for that call. It only stops the caller who was already going to stop and ask.

I added a second layer a few weeks later, once I noticed the first one had its own gap: `confirm=True` alone doesn't prove the diff you approved still describes the live article. Someone could edit it on-site between your preview and your confirm. So `update_article` now also accepts `expected_fingerprint`, a hash of the article's state at preview time, and refuses a stale write even with `confirm=True`:

```python
if live_content_write and expected_fingerprint is not None and expected_fingerprint != fingerprint:
    return {
        "id": article_id,
        "applied": False,
        "reason": "stale — the live article changed since the diff you approved was "
                  "generated (expected_fingerprint doesn't match the current article); "
                  "re-preview and re-approve against the current content before writing",
        "fingerprint": fingerprint,
        ...
    }
```

This is a genuinely better check — it catches drift the first version couldn't. But it has the exact same shape of hole as `confirm` did: `expected_fingerprint` is `None` by default, and skipping it skips the check, not the write. Pass `confirm=True` with no fingerprint and the fix I shipped for staleness never runs. My own docstring says this outright: "this is opt-in, not mandatory." I wrote that sentence as a note to a future reader. I should have read it as a bug report against the design.

The pattern underneath both gaps is the same one keyword-argument safety checks always have: a check that fires *only when the caller supplies the evidence for it* is a check the caller can opt out of by omission, not just by an explicit bypass flag. `confirm=False` isn't the risky path — the risky path is a caller that never learned the parameter exists, and Python doesn't make that caller pass anything at all. Compare that to a boundary that can't be skipped by silence: the fingerprint could instead be *required* whenever `live_content_write` is true, full stop, no default. A caller with no fingerprint gets refused, not waved through. That's one line — `expected_fingerprint: str` instead of `expected_fingerprint: str = None`, plus dropping the `is not None` from the condition — and it turns "protects the caller who already knew to protect themselves" into "protects the article regardless of what the caller knew."

I haven't shipped that change yet, and I want to be honest about why: this specific tool is only ever invoked by me, through Claude Desktop, on my own machine. The realistic threat model for `update_article` right now is *my own mistake or a confused agent turn*, not an adversarial caller — which is exactly the case optional confirmation still mostly protects against, since I'm the one who wrote the docstring and mostly remember to preview first. But "mostly remember" is precisely the property a permission boundary isn't supposed to depend on, and the whole reason I built the gate in the first place was that I didn't trust myself or an agent to remember reliably. An optional gate that only helps when you remember to use it optionally has quietly demoted itself to a linting suggestion.

The generalizable version of this, if you're building any MCP tool with a `confirm` or `dry_run` or `force` parameter: ask what happens on the call that never mentions that parameter at all, not just the call that sets it to `False`. If the answer is "the check that's supposed to run doesn't run, silently, with no error," you don't have a permission boundary — you have a boundary-shaped piece of documentation that only binds the callers who were never going to test it. The fix isn't more documentation telling the caller to remember. It's making the unsafe path fail loudly by default, so the only way to skip the check is to say so explicitly, in the code, where you can grep for it later. I'm making that change to `update_article` this week and writing the `--selftest` case first, so "required, not opt-in" is the behavior a future edit can't quietly walk back.
