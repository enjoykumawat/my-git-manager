---
title: "My pending() Function Learned to Draft Against Nested Comments. My audit() Function Never Learned to Look for Them."
published: true
tags: mcp, python, debugging, devtools
---

I run a small comment pipeline for my DEV.to account. `reply_comments.py pending` surfaces unanswered comments so I can draft replies by hand, and `reply_comments.py audit` cross-checks every drafted reply against the live thread to make sure the draft actually got pasted, since pasting is a manual step and the pipeline itself runs unattended. Today I found that `audit()` had quietly stopped doing its job for the exact case that's now the *normal* case in this pipeline, and it took a live repro to see it, not a read of the code.

`pending()` and `audit()` are meant to be a matched pair. `pending()` decides which comments still need a reply and hands back an `id_code` for each one; I draft against that `id_code` in `drafts/comment_replies.md` as a `## <id_code>` heading. `audit()`'s whole job is to take every `id_code` I've drafted against and check whether I actually replied to it on-site yet. If they don't agree on what an `id_code` can point at, `audit()` can't do its job — and they'd quietly stopped agreeing weeks ago.

Here's `audit()` as it stood this morning:

```python
def audit():
    try:
        drafted_text = open(DRAFTS, encoding="utf-8").read()
    except FileNotFoundError:
        drafted_text = ""
    drafted_codes = set(re.findall(r"^## (\S+)", drafted_text, re.M))
    unposted = []
    for a in my_articles():
        if not a["comments_count"]:
            continue
        for c in api(f"/comments?a_id={a['id']}"):
            if c["id_code"] not in drafted_codes:
                continue
            if not replied_anywhere_in_subtree(c):
                unposted.append({
                    "id_code": c["id_code"],
                    "article": a["title"],
                    "comment_url": f"https://dev.to/{ME}/comment/{c['id_code']}",
                })
    return {"drafted": len(drafted_codes), "never_posted": unposted}
```

The `for c in api(...)` loop is walking the comments API's response, and that response only gives you the thread *roots* — one entry per top-level comment on the article, with every reply-to-a-reply nested inside `c["children"]`. The loop checks `c["id_code"] in drafted_codes` for `c` itself. It never looks inside `c["children"]`. If a drafted `id_code` belongs to a comment nested two, three, or four levels deep — which is exactly what a real back-and-forth thread looks like — this loop never sees it at all. Not "sees it and gets the answer wrong." Never evaluates it, period.

That would be a narrow, forgivable gap if `pending()` only ever drafted against thread roots. It doesn't, and hasn't for weeks. Two earlier fixes to `pending()` changed that on purpose:

- The 2026-08-02 fix made a follow-up nested under my own reply its own pending entry, keyed on *that* comment's `id_code`, not the thread root's — otherwise a fresh follow-up got dedup'd away by the root's already-drafted code, or worse, surfaced with the stale original question as its body instead of the actual follow-up.
- The 2026-08-12 fix went further: a real thread can *branch* — two different commenters both replying to the same parent as siblings — and `_pending_leaves()` walks the whole subtree to find every unanswered leaf, at whatever depth it sits, and drafts against each leaf's own `id_code`.

After both of those fixes landed, "an `id_code` in `drafted_codes`" stopped meaning "a thread root" as its normal case. It became "some comment, at some depth, that `_pending_leaves()` decided was an unanswered leaf." `audit()`'s traversal never got updated to match. Nobody diffed the two functions' assumptions against each other when the second one changed — which, looking back at this repo's own bug log, is almost exactly the same root cause as the *first* fix to this function back on 2026-08-01, just one layer up: that fix made the *reply-detection* check (`replied_anywhere_in_subtree`) recursive; this gap was in the *candidate-selection* loop sitting right above it, which nobody separately re-examined once it had "already been fixed."

I didn't want to trust a read-through here, so I reproduced it against the real functions, not a hand-rolled stand-in. I built a thread shaped exactly like the case the 2026-08-02 fix was written for — root comment `aaa`, my reply `myreply1` nested under it, a fresh follow-up `bbb` nested under my reply — wrote `## bbb` into a scratch `comment_replies.md` as though I'd drafted a reply and never pasted it, stubbed `api()` and `my_articles()` to serve that thread, and called the real `audit()`:

```python
result = rc.audit()
# {"drafted": 1, "never_posted": []}
```

One drafted reply, sitting unposted on-site, and `audit()` reports zero problems. That's the failure mode this function exists to prevent, happening silently, on the pipeline's own most-exercised shape of thread.

The fix adds a small recursive walk with the same shape as `_pending_leaves()`, and swaps the flat iteration for it:

```python
def _walk_comments(comment):
    """Yield this comment and every comment in its subtree, at any depth."""
    yield comment
    for child in comment["children"]:
        yield from _walk_comments(child)


def audit():
    ...
    for a in my_articles():
        if not a["comments_count"]:
            continue
        for root_comment in api(f"/comments?a_id={a['id']}"):
            for c in _walk_comments(root_comment):
                if c["id_code"] not in drafted_codes:
                    continue
                if not replied_anywhere_in_subtree(c):
                    unposted.append({
                        "id_code": c["id_code"],
                        "article": a["title"],
                        "comment_url": f"https://dev.to/{ME}/comment/{c['id_code']}",
                    })
    return {"drafted": len(drafted_codes), "never_posted": unposted}
```

Same reproduction, same fixture, after the fix:

```python
result = rc.audit()
# {"drafted": 1, "never_posted": [{"id_code": "bbb", ...}]}
```

`bbb` shows up, exactly as it should. I added that reproduction as a permanent selftest case — stubbed `api()`/`DRAFTS`, run through the real `audit()` function, not a standalone helper — so a future change to either function's traversal has something to fail against instead of relying on someone noticing by inspection again. `reply_comments.py --selftest` passes, and I reran all seven selftest-bearing scripts in this repo (`server.py`, `publish_devto.py`, `git_commit.py`, `reply_comments.py`, and the three `scripts/*.py` utilities) to rule out sideways breakage.

The thing that actually got me here wasn't spotting a bug in one function. It was noticing that two functions had an implicit contract — "whatever `id_code` one of you can draft against, the other one can find" — and that contract had already been broken by two prior, individually correct fixes to just one side of it. Fixing `pending()` to draft against deeper comments was the right call both times it happened. But a fix to what one function *produces* is only half of a fix if something else in the same file *consumes* that output under an older assumption about its shape, and nothing re-checks that consumer just because its own tests still pass. `audit()`'s tests kept passing the whole time — they just never exercised a drafted reply that wasn't a thread root, because until today, nothing had asked them to.
