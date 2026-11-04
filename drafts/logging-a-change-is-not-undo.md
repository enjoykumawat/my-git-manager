---
title: Logging a Change Is Not the Same as Being Able to Undo It
published: true
tags: ai, agents, mcp, python
---

There's a draft spec going around for giving AI agents real undo — not a confirmation dialog before an action, a way to take back what already happened after it happened. I read it expecting to disagree with some implementation detail. Instead it made me go check whether my own MCP server, which I'd have told you has pretty solid write safety, actually has undo at all. It doesn't. It has something that looks like undo from a distance and isn't one when you get close.

The server in this repo exposes an `update_article` tool that edits live DEV.to posts. Overwriting a published article's title or body is about as close to "can't take it back" as a web API gets — DEV.to keeps no version history, so a bad PUT just replaces what was there. Knowing that, the tool fetches the article's current state before writing, logs the before/after, and requires an explicit `confirm=True` for any write that touches live content:

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
        "fingerprint": fingerprint,
        "diff": {field: {"before": before.get(field), "after": article.get(field)}
                 for field in article},
    }
```

That comment — "DEV.to has no version history to undo this" — has been sitting in my own code for weeks. I wrote it as a justification for why the confirm gate exists. I never once read it as an admission that I'd scoped the entire safety design around *preventing* a bad write, with nothing behind it for *reversing* one that got approved and still turned out to be wrong.

## What actually gets logged

After a confirmed write lands, a separate function appends an entry to a local JSONL file:

```python
def _log_article_update(article_id, before, fields_changed, after):
    os.makedirs(os.path.dirname(_ARTICLE_UPDATE_LOG), exist_ok=True)
    entry = {"article_id": article_id, "fields_changed": sorted(fields_changed), "url": after.get("url")}
    for field in fields_changed:
        entry[f"{field}_before"] = before.get(field)
        entry[f"{field}_after"] = after.get(field)
    with open(_ARTICLE_UPDATE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

This is a real audit trail. It has `title_before` and `title_after` sitting right next to each other in the same JSON object, for every write that's ever landed. The first time I looked at this, months ago, I believed that was enough — if something goes wrong, I can see exactly what changed. I can. What I can't do is act on it, because the log is read-only data about the past, not a callable operation.

Try to write the obvious "undo the last change" function on top of this log and the gap shows up immediately:

```python
def undo_last_update(article_id):
    entries = [json.loads(l) for l in open(_ARTICLE_UPDATE_LOG) if json.loads(l)["article_id"] == article_id]
    last = entries[-1]
    fields = {f: last[f"{f}_before"] for f in last["fields_changed"]}
    # now what? update_article(article_id, **fields, confirm=True) —
    # but only if nothing else has touched this article since `last` was written.
```

That last line is the whole problem. A log entry tells you what the article looked like before *that specific write*. It says nothing about whether the article has been touched again since — by a different tool call, a manual edit on the DEV.to site, or a second concurrent run of this exact pipeline. `update_article` already has machinery for exactly that staleness question, built for a different purpose: a `fingerprint` computed from the current title and body, which a caller can pass back as `expected_fingerprint` to make a write fail closed if the live article moved since the caller last looked at it.

```python
def _article_fingerprint(before):
    basis = "\x1f".join(f"{f}={before.get(f)!r}" for f in ("title", "body_markdown"))
    return hashlib.sha256(basis.encode()).hexdigest()[:16]
```

That check exists to protect a *forward* write — don't let me confirm a diff against content that's already moved. Undo needs the same guarantee running backward: don't let me restore a before-state onto an article that's since moved again, or I silently clobber whatever happened after the write I'm trying to reverse. The fingerprint machinery is already shaped right for this. Nobody's ever called it from the log side, because the log and the fingerprint check were built for two different problems eight weeks apart and never introduced to each other.

## Three things real undo needs that an audit log doesn't give you for free

Reading the trending spec against my own code, the gap breaks into three concrete pieces, none of which "log the before/after" buys you:

1. **A compensating write, not just a recorded one.** `_log_article_update` stores `title_before`/`title_after` as strings. Turning that back into a safe call means re-deriving the exact `update_article(article_id, title=..., body_markdown=..., confirm=True)` invocation from stored data written for humans to read in a JSONL file, not for a program to replay.

2. **A staleness check that runs in reverse.** `expected_fingerprint` already exists and already does the right check — it's just wired to only ever compare against the state the *current* caller previewed, not against a state recorded in a log entry from however many writes ago. Undo-after-the-fact needs the fingerprint comparison to run against history, not against "what you just fetched."

3. **A decision about what "undo" even means once more writes have happened since.** If article X was retitled at 2pm and its body was edited again at 3pm, "undo the 2pm retitle" either has to refuse (something changed since, same as the forward case) or has to define what a partial revert looks like. My log has no opinion on this because nothing ever asked it the question.

None of this is landed. I'm not going to ship a half-tested `undo_last_update` function into a tool that writes to a real, public blog the same day I thought of it — that's a worse version of exactly the blast-radius problem `update_article`'s own confirm gate was built to stop. What changed is smaller than a fix: I stopped believing "we log every change" was a safety property on its own. It's an input to one. The fingerprint check this server already has is most of the hard part of real undo, sitting three functions away from the log that would need it, and I'd never have noticed the distance without a spec for the feature I don't have forcing me to ask what my logging was actually buying me.
