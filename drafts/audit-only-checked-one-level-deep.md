---
title: My Comment-Reply Audit Only Checked One Level Deep. Nested Replies Reported as Never Posted.
published: true
tags: python, debugging, devtools, ai
---
This repo runs a small comment-reply pipeline for my DEV.to articles. DEV.to's API can't post comments or reactions for a normal account key (`POST /api/comments` is 404, `POST /api/reactions` is 401 — verified back in a previous run), so replies get drafted into a markdown file and pasted by hand. Two functions carry the whole thing: `pending()` decides what still needs a draft, and `audit()` checks whether a reply that was already drafted actually made it onto the live site, since the pasting step is manual and happens outside anything this pipeline can see.

Both functions walk the same kind of data — a DEV.to comment and its nested replies. I went back into `reply_comments.py` today expecting to look for something else entirely, and instead noticed the two functions don't walk that tree the same way.

## The two checks, side by side

`pending()` calls `needs_reply()`, which was rewritten back on 2026-07-26 after a bug where it only checked "did I ever reply anywhere in this thread" instead of "did I reply *most recently*." The fixed version recurses the whole subtree to find whichever message has the latest timestamp:

```python
def latest_message(comment):
    """The most recently created message anywhere in this comment's subtree."""
    latest = comment
    for c in comment["children"]:
        candidate = latest_message(c)
        if candidate["created_at"] > latest["created_at"]:
            latest = candidate
    return latest


def needs_reply(comment):
    return latest_message(comment)["user"]["username"] != ME
```

That's correct, and it's recursive by construction — `latest_message` calls itself on every child, so it doesn't matter how deep a reply is nested, it gets found.

`audit()` does something that looks parallel but isn't:

```python
for c in api(f"/comments?a_id={a['id']}"):
    if c["id_code"] not in drafted_codes:
        continue
    if not any(ch["user"]["username"] == ME for ch in c["children"]):
        unposted.append({...})
```

`c["children"]` is only the *direct* replies to the root comment `c`. If I paste my reply directly under the original comment, this works — my reply shows up as a direct child, the `any(...)` finds it, `audit()` correctly says "posted." But that's not the only shape a real thread takes. If someone replies to *my* reply, and I reply again, my second message is a grandchild of `c`, nested two levels down — a completely normal shape for any back-and-forth conversation. `audit()` never looks past the first level, so it can't see that message at all.

## Reproducing it before touching anything

Before assuming this was a real bug and not just an unlikely edge case, I built the exact tree shape and ran it against the real function:

```python
fake_thread = {
    "id_code": "abc12", "user": {"username": "someuser"}, "created_at": "2026-07-20T08:00:00Z",
    "children": [{
        "id_code": "abc13", "user": {"username": "someuser"}, "created_at": "2026-07-20T09:00:00Z",
        "children": [{"id_code": "abc14", "user": {"username": ME},
                       "created_at": "2026-07-21T10:00:00Z", "children": []}],
    }],
}
```

Root comment from `someuser`, their own follow-up as a direct child, and my reply to *that* follow-up as a grandchild — the id_code `abc12` is marked drafted. Running the unmodified `audit()` against this:

```json
{
  "drafted": 1,
  "never_posted": [
    {"id_code": "abc12", "article": "Test Article",
     "comment_url": "https://dev.to/enjoy_kumawat/comment/abc12"}
  ]
}
```

Flagged as never posted, even though a reply from me is right there in the tree, one level further down than the function bothered to check. Running `needs_reply()` against the identical structure returns `False` — correctly recognizing I've already replied. Same data, two functions in the same file, two different answers.

## What this actually costs

`audit()` isn't the thing deciding whether to draft a reply — that's `pending()`, and it was already fixed. `audit()` is the safety net behind the manual paste step, the thing that's supposed to catch "I drafted this and then forgot to actually go paste it." A false positive here doesn't lose a reply. It tells me a reply is missing when it isn't, which means re-checking a thread that's already handled, and if that happens often enough, it trains me to stop trusting `audit()`'s output — which defeats the entire point of having it, since the whole reason it exists is that the manual step is otherwise invisible to the pipeline.

## The fix

Same shape as `latest_message`, recursing instead of stopping at one level:

```python
def replied_anywhere_in_subtree(comment):
    """True if ME appears anywhere below this comment, at any depth."""
    return any(
        ch["user"]["username"] == ME or replied_anywhere_in_subtree(ch)
        for ch in comment["children"]
    )
```

And swapped into `audit()` in place of the one-level `any(...)` check. Reran the exact repro above against the fixed code:

```json
{
  "drafted": 1,
  "never_posted": []
}
```

Correctly empty. I also added a case to the file's existing `--selftest` block covering a reply nested two levels deep, since the only test coverage this file had before today was for `needs_reply()` — `audit()` had none, which is very likely how the same tree-walking mistake made it into one function without the other catching it in code review, self-inflicted or otherwise, since there wasn't a test that would have failed either way.

## Why this wasn't caught by the 2026-07-26 fix

The `needs_reply()` rewrite happened because of a *different* bug — checking "ever replied" instead of "replied most recently." Fixing that one required recursion anyway, since finding the latest message in a tree means visiting the whole tree. `audit()` asks a simpler-sounding question — "did I reply at all, anywhere" — and a simpler-sounding question is exactly the kind that gets a one-level check that looks sufficient until you actually draw out a three-level-deep conversation and trace it by hand. Nothing forced a side-by-side comparison between the two functions once one of them got fixed; they just happened to be walking the same kind of tree, one correctly and one not, forty-something lines apart.
