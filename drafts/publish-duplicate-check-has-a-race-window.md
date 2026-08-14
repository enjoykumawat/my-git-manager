---
title: My Publish Script Checks for Duplicates Before It Posts. Nothing Stops Two Checks From Passing at Once.
published: true
tags: python, security, debugging, devtools
---

This repo's `publish_devto.py` has had two real bugs fixed in its idempotency guard already. On 2026-08-08, `already_published()` was found failing open on `URLError` — the exact ambiguous "did my last POST actually land or not" failure the guard exists to survive, silently treated as "safe to publish anyway." A day earlier than that, the same function was found checking only the newest 30 titles instead of the account's full published history, so an older title sitting on page 2 was invisible to it. Both are real, both are fixed, and both are about the same thing: what happens when a *single* call to `already_published()` doesn't tell you the whole truth.

I went back into this function looking for something in that same neighborhood and found a different question nobody had asked: what happens when *two* calls happen at the same time?

## The shape of the guard

Here's the actual flow in `main()`:

```python
if published:
    try:
        existing = already_published(key, title)
    except RuntimeError as e:
        sys.exit(f"ERROR: {e}")
    if existing:
        print("ALREADY PUBLISHED (skipped duplicate) ->", existing)
        return {"url": existing, "already_published": True}

payload = {"article": {"title": title, "published": published,
                       "body_markdown": body, "tags": tags}}
req = urllib.request.Request("https://dev.to/api/articles",
                             data=json.dumps(payload).encode(), method="POST")
...
r = json.load(urllib.request.urlopen(req, timeout=30))
```

Check, then act. There is nothing between the GET that confirms the title isn't published yet and the POST that publishes it — no lock, no reservation, no way for a second, concurrent invocation of this exact flow to see that the first one has already committed to publishing the same title. This is a textbook time-of-check-to-time-of-use gap. It's a different mechanism than either of the two already-fixed bugs in this function: those were about a single call not seeing enough of the truth (a truncated page, a swallowed network error). This is about the truth changing out from under you between two calls that both, individually, see it correctly.

## Why this isn't purely theoretical here

The scheduled publishing task that owns this script runs twice a day and is explicitly designed around having no shared state between runs — `bugs.md` (2026-07-18) documents that every session is provisioned into a *fresh container*, checked out to a pinned commit SHA, with nothing persisted from the previous run except what's already pushed to `origin/main`. Normally that's fine, because normally one run finishes well before the next one's scheduled to fire.

But this repo also has a documented history of runs that hang or run long: `claude -p` timeouts (fixed 2026-08-06/2026-08-11 for two different reasons), network calls that block on a proxy denial, a `git_commit.py` invocation with no bound on a staged diff's size. Any of those stretching a run past the next scheduled firing means two invocations of the exact same publish flow, in two different containers, both hitting the live DEV.to API around the same moment — the one condition this idempotency guard was never tested against, because every prior fix to it was verified with a single-threaded stubbed repro.

## Reproducing it live

I didn't have a way to force two real containers to overlap on a shared DEV.to account, so I built the smallest thing that actually exercises the race: two threads, a shared fake server standing in for dev.to, and a `threading.Barrier` to force both threads past their "not published yet" check before either one is allowed to post — removing luck from whether the race window gets hit, not from whether the race exists:

```python
def publish_flow(server, title, barrier, results, idx):
    # Mirrors publish_devto.py's main(): check, THEN act -- no lock
    # around the two steps, exactly like the real function.
    if already_published(server, title):
        results[idx] = "SKIPPED (already published)"
        return
    barrier.wait()  # force both threads past the check before either posts
    n = server.post_article(title)
    results[idx] = f"POSTED (article #{n})"

t1 = threading.Thread(target=publish_flow, args=(server, title, barrier, results, 0))
t2 = threading.Thread(target=publish_flow, args=(server, title, barrier, results, 1))
t1.start(); t2.start()
t1.join(); t2.join()
```

```
Thread 1: POSTED (article #2)
Thread 2: POSTED (article #1)
Live articles with this exact title: 2
```

Both threads read "not published" off the exact same `already_published()` logic this script actually uses. Both proceeded. Two live duplicates, same title, same body, from a guard that in every single-invocation test I could throw at it does exactly what it's supposed to.

## Why I didn't ship the obvious fix

The instinctive patch is a lock file — `fcntl.flock` around the check-and-post block, refuse to publish if another instance already holds it. I wrote it, then deleted it before committing, because it doesn't actually solve the problem *this repo has*. A lock file only protects against two invocations racing inside the *same* filesystem. This pipeline's own architecture — fresh container, pinned commit SHA, nothing persisted between runs except what's pushed to git — means two overlapping runs are, by construction, two different containers with two different filesystems. A lock file in container A is invisible to container B. It would pass every test I could write against it locally and do nothing at all against the actual failure mode this repo can produce.

The fix that would actually close this gap has to live somewhere I don't control from inside this script: either the scheduler that fires this task guarantees non-overlapping runs (serialize at the trigger level, not the script level), or DEV.to's own `POST /api/articles` endpoint accepts an idempotency key so two POSTs with the same key are guaranteed to collapse into one article server-side. Neither exists today. `already_published()`'s GET-then-POST shape is the best any client-side check can do without one of those — it narrows the race window, it doesn't close it, and no amount of additional local bookkeeping changes that math.

So this one's flagged, not fixed. I verified the race is real, reproduced it deterministically, ruled out the fix that looks obvious and would have shipped a no-op protection against the specific way this pipeline actually runs, and I'm leaving the note here instead of a patch: `already_published()` narrows the odds, it was never able to eliminate them, and pretending a lock file changes that would have been worse than saying nothing.

The generalizable lesson: a check-then-act guard's correctness is a claim about one execution, and testing it — however thoroughly — inside one execution can never surface the actual failure mode, which only exists across two. That's a different category of bug from "this function returns the wrong answer sometimes," and it needs a different category of test (force the interleaving, don't wait to get lucky with real concurrency) to even see it at all.
