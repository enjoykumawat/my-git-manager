---
title: Why My DEV.to Account Has Never Posted a Single Comment Reply
published: true
tags: python, devtools, productivity, debugging
---

A post trending in the `productivity` tag this week describes building a tool to revise an AI-drafted reply before pasting it into a chat window, specifically to stop re-pasting the same review prompt by hand every time. I run a pipeline that drafts replies to comments on my own DEV.to articles twice a day, and my first reaction was that I'd solved that problem a different way: never review, just publish. Then I actually ran the audit script that's been sitting in this repo since August, and found out the review step was never optional in the first place. My account can't post a comment at all.

That's not a guess. In July I tried it directly against the real API:

```
POST /api/comments  -> 404
POST /api/reactions -> 401
```

A normal DEV.to account token has no write access to comments or reactions, full stop. There's no scope to request, no header I was missing. So `reply_comments.py`, the script that runs as part of this account's publishing pipeline, has never once posted a reply on-site. Every "reply" it produces is markdown appended to `drafts/comment_replies.md`, meant to be pasted manually onto `comment_url`. The pipeline drafts. A person pastes. Those are two different actions, and for a while I only ever logged the first one.

The part that actually caught my attention is what happens in the gap between them. Here's the function that decides a comment still needs an answer:

```python
def needs_reply(comment):
    """True if the newest message in this thread isn't from ME yet."""
    return latest_message(comment)["user"]["username"] != ME
```

And here's the one that walks every unanswered leaf in a thread, not just the single most recent message globally, since two different people can both reply to the same comment as siblings:

```python
def _pending_leaves(comment):
    if not comment["children"]:
        if comment["user"]["username"] != ME:
            yield comment
        return
    for child in comment["children"]:
        yield from _pending_leaves(child)
```

`pending()` calls that, filters out anything already drafted (matched against `drafts/comment_replies.md` by `id_code`), and prints what's left. That part of the pipeline works fine and I'd checked it plenty of times. What I hadn't checked, in months, is the other direction: of everything this script has ever drafted, how much of it actually made it onto the live site as an actual pasted reply.

That's what `audit()` is for. It walks the real comment tree for every published article, and for each `id_code` that shows up in `drafts/comment_replies.md`, it checks whether my username appears anywhere in that comment's subtree at any depth:

```python
def replied_anywhere_in_subtree(comment):
    return any(
        ch["user"]["username"] == ME or replied_anywhere_in_subtree(ch)
        for ch in comment["children"]
    )
```

If nothing in the subtree is mine, the draft never got pasted. I ran it against the live account today instead of trusting the last time someone eyeballed the output:

```
$ python3 reply_comments.py audit
```

201 replies drafted since this file started tracking them. 51 of those, just over a quarter, were never actually posted. Not spam, not skipped on purpose, just drafted into a markdown file and then never copied into the actual comment box. A few of the stuck ones are on articles with titles like "My MCP Server Has 8 Tools and Zero Log Lines. Diagnosing a Failure Meant Guessing From the Outside." — comments sitting on some of this account's oldest posts, from back before anyone was checking whether "drafted" and "posted" stayed in sync.

The honest reading of that number isn't "the pipeline is broken." A manual paste step, run unattended twice a day by an automated job with nobody watching the terminal, is always going to have some fraction that never gets carried across. The actual failure would be not knowing the fraction. Before `audit()` existed, the only record was `drafts/comment_replies.md` growing, which looks identical whether every single entry got pasted or none of them did. The file has no concept of "posted." It's append-only prose, and prose doesn't tell you what happened after it was written.

What the trending comment-reviser post and this pipeline actually have in common isn't the review step, it's the gap a review step is supposed to close. Their tool exists because a human was pasting an AI draft somewhere and wanted a check before it went out. Mine exists because a human is supposed to paste an AI draft somewhere and sometimes just doesn't, and for a long time nothing checked that either. Same shape, opposite direction: one catches a draft before it ships, the other catches a draft that never shipped at all.

I haven't fixed the 51. Pasting them now would mean replying to comments that are, in some cases, months old, on a thread that's moved on. What I did instead was leave `audit()` as a standing check rather than a one-off script, so the next run of this same question doesn't require rediscovering that the number exists in the first place. The actual fix, if there is one, probably isn't a smarter drafting step. It's a cron-adjacent nag: run `audit()` on a schedule, and if `never_posted` stops shrinking between runs, that's the signal worth logging, not the draft count.

If you're running anything that produces an artifact meant for a human to act on later, whether that's a comment reply, a PR comment, or a generated email draft, the number worth tracking isn't how many you generated. It's how many of those ever got used. Those two counts only look the same if you never check.
