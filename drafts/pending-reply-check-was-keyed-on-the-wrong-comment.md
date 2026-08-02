---
title: My Comment-Reply Queue Draft One Reply to a Thread and It Went Deaf to Every Follow-Up After That
published: true
tags: python, debugging, devtools, ai
---

I have a small script, `reply_comments.py`, that keeps me from having to re-scan every DEV.to article for new comments by hand. It has two commands: `pending` (unanswered comments I haven't drafted a reply to yet) and `audit` (drafted replies I said I'd paste manually but apparently never did). I've already fixed two bugs in this file — one in `needs_reply()` (a thread stayed "handled" forever after a single reply, even when the other person followed up again) and one in `audit()` (it only checked direct children, so a reply nested two levels deep was invisible). Today I found a third, in `pending()` itself, and it's the kind of bug that hides precisely because the first two fixes made everything else in the file look trustworthy.

## What `pending()` actually does

Comments on DEV.to come back from the API as trees — each top-level comment has a `children` list, and replies can nest arbitrarily deep. `pending()` walks each article's top-level comments and decides, for each one, whether it needs a reply:

```python
def pending():
    try:
        drafted_text = open(DRAFTS, encoding="utf-8").read()
    except FileNotFoundError:
        drafted_text = ""
    drafted_codes = set(re.findall(r"^## (\S+)", drafted_text, re.M))
    out = []
    for a in api(f"/articles?username={ME}&per_page=100"):
        if not a["comments_count"]:
            continue
        for c in api(f"/comments?a_id={a['id']}"):
            if not needs_reply(c):
                continue
            if c["id_code"] in drafted_codes:
                continue
            out.append({
                "id_code": c["id_code"],
                "author": c["user"]["username"],
                "article": a["title"],
                "comment_url": f"https://dev.to/{ME}/comment/{c['id_code']}",
                "body": strip_html(c["body_html"]),
            })
    return out
```

`needs_reply(c)` is the fix from a few weeks ago — it recurses the whole subtree and checks who posted the *most recent* message, not just whether I've ever replied. That part's correct. The bug is in the two lines right after it: `c["id_code"]` and `c["body_html"]`. `c` here is always the **top-level comment**, no matter how deep the actual unanswered message sits.

## The two things that go wrong

For a single-round comment — someone posts, I haven't replied — `c` *is* the unanswered message, so this works fine. It's the only case I'd ever tested against.

But this pipeline exists specifically for back-and-forth threads. Say someone comments (`id_code: "aaa"`), I draft and post a reply, and they follow up with a genuine new question. That follow-up is a brand new comment object, nested under my reply, with its own `id_code` (say `"bbb"`). Two things break at once:

1. **The dedup check is keyed on the wrong id.** `drafted_codes` already contains `"aaa"` from the first round. The code checks `c["id_code"] in drafted_codes` — but `c` is still the root, so it's still `"aaa"`, which is still in the set. The thread gets skipped, permanently. The follow-up's actual id, `"bbb"`, is never checked against anything, and never will be, because `pending()` never looks past the root to find it.
2. **Even without the dedup skip, the content is stale.** If it *did* surface, the returned `body` would be `c["body_html"]` — the root's original message from round one — not the actual follow-up question sitting three levels down that I'd be pasting a reply to.

I confirmed this with a script before touching anything, rather than trusting my reading of the code:

```python
root_round2 = msg("x", "2026-07-24T08:00:00Z", "aaa", body="original question", children=[
    msg(ME, "2026-07-25T10:00:00Z", "myreply1", children=[
        msg("x", "2026-07-26T09:00:00Z", "bbb", body="follow-up question, still unanswered"),
    ]),
])

c = root_round2
print(needs_reply(c))                        # True -- x's follow-up is the latest message
print(c["id_code"] in {"aaa"})                # True -- but "aaa" is the ROOT's id, not the follow-up's
```

`needs_reply` correctly says the thread is open. The dedup check then throws that answer away, because it's asking the wrong question — "has the root ever been drafted," not "has the message that actually needs a reply been drafted." Once a thread gets its first draft, `pending()` goes deaf to it. Not until the next comment, forever.

This is distinct from the two prior bugs in this file. The `needs_reply()` fix changed the *definition* of "does this thread need a reply" from "did I ever post here" to "who posted most recently" — that logic, once fixed, is actually correct now, and my repro confirms it. The `audit()` fix was about walking one level too few into a tree. This one is neither of those — it's a dedup key silently pointing at a stable, wrong node in a tree whose interesting node moves every round.

## The fix

The information `pending()` actually needs — for both the dedup check and the returned content — is the *latest unanswered message*, not the root. `latest_message()` already exists in this file (it's what `needs_reply()` is built on), so the fix is just using it in the right place:

```python
def _pending_entry(comment, drafted_codes):
    if not needs_reply(comment):
        return None
    latest = latest_message(comment)
    if latest["id_code"] in drafted_codes:
        return None
    return {
        "id_code": latest["id_code"],
        "author": latest["user"]["username"],
        "comment_url": f"https://dev.to/{ME}/comment/{latest['id_code']}",
        "body": strip_html(latest["body_html"]),
    }


def pending():
    ...
    for c in api(f"/comments?a_id={a['id']}"):
        entry = _pending_entry(c, drafted_codes)
        if entry:
            out.append({**entry, "article": a["title"]})
    return out
```

Now the dedup check and the surfaced content both key off the message that's actually pending, at whatever depth it lives. I added a selftest case for exactly the round-2 scenario above — root drafted, follow-up not — and confirmed the follow-up now surfaces with its own id and body, and correctly drops out only once *its* id gets drafted:

```python
entry = _pending_entry(root_round2, drafted_codes={"aaa"})
assert entry["id_code"] == "bbb"
assert entry["body"] == "follow-up question"
assert _pending_entry(root_round2, drafted_codes={"aaa", "bbb"}) is None
```

## Why this one hid so long

Every prior fix to this file made the surrounding code look more correct, which made it a worse candidate for re-scrutiny, not a better one. `needs_reply()` got fixed and tested. `audit()` got fixed and tested, with a nested-thread case added specifically because a shallow check had already burned me once. `pending()` sat right between the two, calling the now-correct `needs_reply()`, and inherited a false sense of "this part's been gone over already." Nobody had asked whether the *id* attached to that correct boolean was still pointing at the thing the boolean was actually about — because on the input everyone had tested (a single unanswered comment, no history), the root and the pending message are the same object, and the bug is invisible. It only shows up on the second round of a real conversation, which is exactly the case a comment-reply pipeline exists to handle.
