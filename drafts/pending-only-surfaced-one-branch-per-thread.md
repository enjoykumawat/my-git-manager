---
title: My Comment-Reply Pipeline Picks One Winner Per Thread. Two Commenters Broke That.
published: true
tags: python, debugging, devtools, ai
---

`reply_comments.py` is the script that tells me which DEV.to comments still need a reply. It walks every comment tree on every article I've published and reports the ones I haven't answered yet. I've fixed two bugs in it already: `needs_reply()` used to think a thread was "handled" forever after a single reply, even if the other person followed up again, and a dedup check was keyed on the thread's root comment instead of whichever message actually needed the reply, so a second round of conversation went permanently invisible. Both fixes are in `--selftest` now, and both looked, from the outside, like they'd covered this file's tree-walking logic pretty thoroughly.

They hadn't. Today I found a third bug in the same handful of functions, and it survives even with both prior fixes applied.

## What the existing code assumes

Comments on DEV.to come back from the API as trees. A top-level comment has a `children` list, and each child can have children of its own. The function that decides whether a thread needs attention is `needs_reply()`, built on `latest_message()`:

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

This walks the whole subtree and returns exactly one message: whichever one has the latest timestamp, anywhere in the tree. `_pending_entry()` (the function `pending()` actually calls) is built directly on top of that single answer — it checks whether the latest message needs a reply, and if so, returns one entry for the whole thread.

That's a reasonable design if a thread only ever grows one message at a time: root comment, my reply, their follow-up, my reply, and so on. Every test case in this file's `--selftest`, and both of the earlier bug writeups, modeled exactly that shape. Nothing ever modeled two different people replying to the *same* comment.

## The case that breaks it

DEV.to threads aren't guaranteed to be a single chain. Someone can post a top-level comment, I can reply to it, and then two entirely different people can each reply to *my* reply, as siblings, not to each other. I checked this is a real shape the API returns, not a hypothetical edge case I invented for the test — a comment's `children` array is just a list, and nothing about it caps the count at one branch.

I built a repro using the actual functions in the file, not a stub:

```python
root = msg("userA", "2026-08-01T08:00:00Z", id_code="root1", body="original", children=[
    msg(ME, "2026-08-02T08:00:00Z", id_code="myreply1", children=[
        msg("userB", "2026-08-03T08:00:00Z", id_code="sibB", body="question from B"),
        msg("userC", "2026-08-05T08:00:00Z", id_code="sibC", body="question from C"),
    ]),
])

entry = _pending_entry(root, drafted_codes=set())
print(entry)
```

Before touching any code, this printed one entry: `sibC`, userC's question, the later of the two timestamps. `sibB`, userB's question, sitting right next to it in the same `children` list, never showed up. Not as a duplicate to skip, not as something already handled. It just wasn't in the output, with nothing anywhere suggesting a second unanswered comment existed on that thread.

That alone would be a bug worth fixing — two live commenters, one gets an answer and one doesn't, and I'd have no way of knowing from `pending()`'s output. But it gets worse once you follow it forward. If I actually reply to userC's comment, that reply becomes a real message in the tree with a timestamp later than anything else in the subtree. The next time `pending()` runs, `latest_message()` finds *my own reply* as the newest thing in that thread, `needs_reply()` says the thread is handled, and the whole thing — including userB's still-unanswered question — drops out of the pipeline's view entirely. Not delayed. Gone. Nothing about this file's design would ever surface userB's comment again unless userB happened to post something new after that point, and even then only their newest message would show up, not the specific comment I skipped.

## Why the earlier fixes didn't catch it

The 2026-08-02 fix in this same file solved a real and related-looking problem: a dedup key that pointed at the wrong node once a thread grew past its first message. But that fix, like everything else tested against this code, used a strictly linear chain — root, my reply, their follow-up — where there's only ever one "current" message at any given moment. `latest_message()`'s job, in that shape, really is well-defined: there's one thread, one front, one thing to check. The function is correctly named and correctly implemented for the question "who spoke most recently here." The bug is that `_pending_entry()` used that single answer as a stand-in for "is there anything at all pending in this thread" — a question that a branching tree doesn't reduce to one answer, no matter how correct the single-winner logic underneath it is.

## The fix

The pipeline needs every open branch, not the single newest one. I added a generator that walks the whole subtree and yields every leaf — every childless comment — that isn't authored by me:

```python
def _pending_leaves(comment):
    if not comment["children"]:
        if comment["user"]["username"] != ME:
            yield comment
        return
    for child in comment["children"]:
        yield from _pending_leaves(child)


def _pending_entries(comment, drafted_codes):
    for leaf in _pending_leaves(comment):
        if leaf["id_code"] in drafted_codes:
            continue
        yield {
            "id_code": leaf["id_code"],
            "author": leaf["user"]["username"],
            "comment_url": f"https://dev.to/{ME}/comment/{leaf['id_code']}",
            "body": strip_html(leaf["body_html"]),
        }
```

`pending()` now loops over `_pending_entries()` per top-level comment instead of taking at most one optional result:

```python
for c in api(f"/comments?a_id={a['id']}"):
    for entry in _pending_entries(c, drafted_codes):
        out.append({**entry, "article": a["title"]})
```

I left `needs_reply()`/`latest_message()` exactly as they were. They're still correct for the specific question they answer, and nothing else in the file depends on them being wrong. Reran the userB/userC repro against the fixed code and both entries came back, `sibB` and `sibC` separately, with their own `id_code`s. I also reran every previously-passing selftest scenario through the new `_pending_entries()` instead of the old `_pending_entry()`, since a linear thread only ever has one leaf, they all produce identical results to before, so I didn't lose any coverage swapping the underlying mechanism. Added the branching case as a new permanent assertion, plus one confirming that drafting a reply to one sibling leaves the other one correctly still pending. `reply_comments.py --selftest` passes, along with the rest of this repo's self-tested scripts.

## The actual lesson

A recursive function that's designed to return a single winner (latest, deepest, first, whatever) is a reasonable thing to build when the question really does have one answer. The mistake was reusing that single answer for a different question, "is there anything open here," where the honest answer can be a list. I'd tested this file's tree-walking against every shape I'd already thought to model, and every one of those shapes happened to be a chain. It took building an input that genuinely branches, not just building a longer chain, to find the gap, and dev.to's own comment API had been capable of producing that shape the entire time I was testing against chains instead.
