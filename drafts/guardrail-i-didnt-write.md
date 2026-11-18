---
title: The Only Reliable Guardrail Around My DEV.to Publishing Script Is One I Didn't Write
published: true
tags: mcp, security, python, devtools
---

I maintain a small MCP server that gives an AI agent direct write access to my DEV.to account and GitHub profile. One of its tools, `update_article`, can rewrite the title and body of a post that's already live. Over the last few months I've added four separate safety checks to that one function, and every single one of them exists because I found, after the fact, a way the previous version could have silently wrecked a published article. Meanwhile the one guardrail that has never once failed me is a wall I had no hand in building at all: DEV.to's own API simply refuses to let this account post comments or react to posts, full stop, no matter what my code does.

That asymmetry is the whole point of this post.

### The guardrails I built, and why each one exists

`update_article` originally looked like what you'd expect: take an `article_id`, PUT whatever fields were given. The first gap I found was the obvious one — a wrong or hallucinated `article_id` would overwrite whatever article it pointed at with zero trace. The fix was to fetch the article's current state before writing, so there's always a diff:

```python
before = _dev(f"/articles/{article_id}")
...
result = _dev(f"/articles/{article_id}", method="PUT", data={"article": article})
_log_article_update(article_id, before, article.keys(), result)
```

That felt like enough, for about three weeks. Then I noticed that `confirm=True` only proves the *caller* meant to write — it says nothing about whether the article is still in the state that write decision was actually made about. Someone editing the post on-site, or a second concurrent tool call, could land in between a preview and a confirm, and the write would clobber it without knowing. So the preview response now returns a fingerprint of the current title/body, and a confirm call has to pass that fingerprint back:

```python
if live_content_write and expected_fingerprint is not None and expected_fingerprint != fingerprint:
    return {
        "applied": False,
        "reason": "stale — the live article changed since the diff you approved "
                  "was generated; re-preview and re-approve against the current content",
        ...
    }
```

Then a third gap: `create_article` already refused to publish a new article with a title that duplicates one already live, but that guard only ever ran on the create path. `update_article` could publish a *draft* straight into a duplicate title with no check at all, because it's a completely different code path to the same live state. Fourth fix, same shape as the first three: find the gap, bolt on a guard, write a regression test so it can't come back silently.

Every one of these is a real improvement. I'd make all four again. But notice the pattern: each one is also a thing I personally had to think of, write correctly, and could still get wrong in some fifth way I haven't found yet. `confirm` could be dropped by a future refactor that doesn't realize it's load-bearing. The fingerprint comparison could be broken by a change to what `_article_fingerprint` hashes. Nothing stops me from introducing guard-shaped bugs into my own guards — I've already done it once, when the optional parameters on this exact function were typed as `str = None` instead of `str | None = None`, which made FastMCP's generated schema advertise `null` as the default while the validator rejected it as a value. The guard that was supposed to make the tool safer made it uncallable in a specific case, and nobody noticed until a call with an explicit `null` hit it directly.

### The guardrail I never had to write

Compare that to what happens when the same agent tries to make this account post a comment or leave a reaction. `POST /api/comments` returns 404. `POST /api/reactions` returns 401, even with a valid API key and the right Forem `Accept` header — I verified this live back in July and it hasn't needed re-checking since, because there's nothing on my side that could regress it. DEV.to doesn't expose a write path for a normal API key to do either of those things. I don't have a confirm flag for it. I don't have a fingerprint check for it. I don't have anything, because there's no code of mine in the loop to have a bug in.

I ran into a trending post this week about an AI coding assistant wired up to Postgres with row-level security locking it to exactly one table — the author's point was that the database enforced the boundary, not the application code calling it. That's the same shape as my comments/reactions situation, just one layer down the stack: an API surface that doesn't exist at all is a stronger guarantee than any amount of validation logic sitting in front of an API surface that does.

### Where this actually changes what I build next

The lesson isn't "stop writing guardrails," because `update_article` needs the flexibility — I genuinely want an agent to be able to retitle or rewrite a live post, which means there has to be *some* code deciding when that's allowed. The lesson is to be honest about which operations actually need that flexibility and which ones don't, because every operation that needs it is a standing liability I have to keep re-auditing, and every operation that doesn't is one less thing on that list.

`create_article` turns out not to share `update_article`'s risk shape at all — a bad call there just produces an extra draft, which is cheap to notice and cheap to delete. That's not a guardrail I added on purpose; it's just true of the operation. `update_article` is the one tool in this server where a plausible call and a wrong call take the identical code path, which is exactly why it accumulated four separate fixes and `create_article` accumulated zero.

So the actual audit I'm doing now isn't "did I write enough checks" — it's going back through every tool this server exposes and asking, for each one, whether a wrong call and a right call are actually distinguishable at all before anything gets written. Where they aren't, I'll keep adding fetch-before-write and confirm gates, because that's the only lever I have. Where the platform already makes the wrong call impossible on its own, I'm done, and I'd rather find three more operations like that than write a fifth guard for `update_article`.
