---
title: "Why I Draft Dev.to Replies Instead of Posting Them Automatically"
published: true
tags: python, devtools, debugging, productivity
---

A post went around recently about a local web app someone built to stop re-pasting the same "fix my grammar" prompt before posting a dev.to comment: paste a draft, get a revision with inline explanations of what changed and why, copy it back in. It's a good tool and it solves a real annoyance — the repetitive-prompt problem. But it also stops exactly where the dev.to API makes it stop: at the clipboard. The actual posting is still a manual paste, by design, because that's the only path dev.to leaves open to a normal account.

I built something adjacent to that for my own account, for a different reason, and the difference in reasons changes what the tool actually has to do.

I didn't need better-written replies. I needed a way to run an unattended, twice-daily pipeline that reads comments on my published articles, without that pipeline ever being able to post anything itself — because it can't. I checked this directly against the live API rather than assuming it from docs:

```python
# verified 2026-07-18
POST /api/comments    -> 404
POST /api/reactions   -> 401 (even with a valid api-key and the
                          Forem v1 Accept header)
```

Those aren't rate limits or scope errors. A valid key with full access still gets a flat 404 trying to create a comment, and a 401 trying to react to one. Dev.to's write API, for a normal user, doesn't have a "post" verb for either. So no amount of client-side polish — mine or the reviser app's — removes the human-paste step. It's not a workaround waiting to be engineered away; it's the actual shape of the platform.

Once posting can't be automated, the interesting engineering problem stops being "generate a good reply" and becomes "make a permanently-manual step safe to run unattended for months without anyone watching it." My pipeline, `reply_comments.py`, is built around that instead of around drafting quality. It has two commands:

```python
def api(path):
    req = urllib.request.Request("https://dev.to/api" + path)
    req.add_header("api-key", os.environ.get("DEV_TO_API", ""))
    # dev.to blocks any User-Agent containing "urllib" (case-insensitive)
    req.add_header("User-Agent", "Mozilla/5.0")
    ...
```

`pending` lists comments that haven't been drafted yet. `audit` is the one that matters more: it cross-checks every comment `id_code` already sitting in `drafts/comment_replies.md` against the live thread and reports which of those still have no reply from me on-site. The reason `audit` has to exist at all is that "drafted" and "posted" are not the same fact, and nothing enforces that they stay in sync once a human is the one doing the pasting. A draft can sit in that file for a week because I was away, and the pipeline itself has no other way to notice that — it isn't watching a success callback from a post it never made.

That distinction cost me a real bug before I had `audit` at all. The comment text I was drafting against came back from the API HTML-escaped and tag-wrapped, which an earlier version of the pipeline only half-handled:

```python
def strip_html(h):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
```

The tag-stripping regex alone was there from the start. What was missing was `html.unescape` — so a comment like "isn't it faster with a Q&A cache?" came back through the pipeline as literal `isn&#39;t ... Q&amp;A`, and `List<String>` came back as `List&lt;String&gt;`. That's exactly the text a human drafting a reply has to read to understand what was actually asked, and it was silently wrong for every comment containing an apostrophe, an ampersand, or a generic type, until it got caught and logged.

The other measured constraint worth being honest about: rate limiting. The retry schedule is fixed and small —

```python
RETRY_SCHEDULE = (10, 30, 60)
```

— and across ten real 429s this pipeline has actually hit, roughly half cleared within the same run and half didn't, resolving only on the next scheduled run hours later. That's not a bug in the backoff schedule; it's what you get when a rate-limit window is wider than any retry budget you're willing to burn inside one run. No amount of smarter backoff logic changes that ratio, because the problem isn't the shape of the wait, it's that the wait itself can outlast the run.

The reviser app and my pipeline are solving genuinely different problems that happen to touch the same box in a UI. Its job is to make the text better before a human posts it. Mine is to make it safe for a human to be the only thing standing between "drafted" and "posted," for a process that doesn't get to watch itself work. If you're building against an API with the same write restrictions — and Forem-style platforms aren't unusual here — the design question to ask first isn't "how do I automate the posting," it's "what's actually permitted," checked against the live API, not the docs. Everything downstream, including which bugs are worth catching, follows from that answer.
