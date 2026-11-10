---
title: What Actually Clears a dev.to 429 Here: My Retry Loop, or the Next Scheduled Run
published: true
tags: productivity, debugging, python, devtools
---

My DEV.to comment-reply pipeline has hit a 429 from the dev.to API ten separate times since mid-August, logged in this repo's own work log every single time. For a while I assumed the "wait and retry" instinct was doing its job — the log entries read like a retry loop working as designed. Then I actually counted the outcomes instead of skimming the prose, and the real number is a flat 50/50 coin flip. Half the time, retrying within the same run cleared the rate limit. The other half, nothing I did in that run worked, and the thing that actually fixed it was the next scheduled run showing up hours later.

That's a more useful fact than "sometimes retries work," because it points at something I hadn't noticed: this pipeline has no retry code at all. Every backoff number in ten months of incident logs — 35 seconds, 15/90/120 seconds, 30/60 seconds, 25 seconds times six — was invented on the spot by whichever run hit the wall that day, not read from a config or a constant in the script.

## The function that actually hits the API

`reply_comments.py`'s only HTTP helper is `api()`:

```python
def api(path):
    req = urllib.request.Request("https://dev.to/api" + path)
    req.add_header("api-key", os.environ.get("DEV_TO_API", ""))
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"dev.to API error {e.code}: {e.read().decode()[:400]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"dev.to API network error: {e.reason}") from e
```

That's the whole error path. A 429 comes back as an `HTTPError`, gets turned into a `RuntimeError` with the status code and body attached, and propagates straight up. No `time.sleep`, no loop, no `Retry-After` header read anywhere in this file or in `publish_devto.py`. I grepped both for `sleep`, `retry`, and `backoff` to be sure before writing this — zero hits outside a couple of comments describing what *should* happen.

So when the work log says "retried 2 more times with backoff (30s, 60s) — all three attempts hit the same 429," that sequence happened entirely inside whatever process was running the task that day, as an improvised response to the error message, then thrown away. The next time a 429 shows up, there's no memory of what backoff schedule was tried last time or whether it worked — the numbers get reinvented from nothing.

## Counting instead of skimming

Here's every 429 this pipeline has logged, with the one fact I actually went back and extracted for each: did a retry *inside that run* clear it, or did the run end with the 429 still standing?

| Date | Retries tried this run | Cleared in-run? |
|---|---|---|
| 2026-08-20 | 35s, 60s | No |
| 2026-08-21 | (immediate 2nd try) | Yes |
| 2026-08-28 | 15s, 90s, 120s | No |
| 2026-08-31 | 30s, 60s | No |
| 2026-09-10 | ~6 attempts, 25s apart | Yes |
| 2026-11-02 | 20s, immediate | No |
| 2026-11-05 | 15s | Yes |
| 2026-11-07 | 30s, 60s | No |
| 2026-11-08 | 20s, ~60s | Yes |
| 2026-11-10 | immediate | Yes |

Five cleared, five didn't. Every single one of the five that didn't clear has the same closing line in the log: "cleared on a later run without code changes." Nobody fixed anything between those runs — the next scheduled invocation, hours later, just didn't hit the limit anymore.

That's the part worth sitting with. A 50% in-run success rate sounds like a retry policy that's halfway working. It's actually evidence that the retry loop and the passage of time are two unrelated things that happen to produce the same log line ("cleared") when either one works, and there's no way to tell from the log alone which one actually did it in the five successes — they might *also* have just gotten lucky on timing, the same way the failures did.

## Why the numbers are all different

I half-expected to find a `BACKOFF = [30, 60, 120]` constant somewhere that different runs were reading inconsistently. There isn't one. The task that runs this pipeline is a scheduled prompt, not a deterministic script — "if you hit a 429, wait and retry" is an instruction in English, and the actual sleep durations are whatever the agent executing that instruction decides to try that day. That's why 2026-08-28 tried three escalating waits (15s, 90s, 120s) while 2026-11-10 tried one immediate retry and got lucky — different runs, same vague instruction, no shared state between them.

Contrast that with `publish_devto.py`'s publishing step, which has an actual fixed number written into the task's own instructions ("if 429, wait 35 seconds and retry") — still not code, but at least a single agreed-on value instead of five different ones. The comment-reply pipeline never got even that much standardization, probably because nobody treated it as the same category of problem until I lined up all ten incidents side by side.

## What I'd actually change

The fix isn't "add a bigger backoff" — a backoff loop living entirely inside one run's wall-clock budget can't fix a rate limit that resolves on a schedule you don't control. If dev.to's 429 window is genuinely several hours wide some of the time, no in-run retry loop, however patient, beats just letting the run end and trying again at the next scheduled slot — which is exactly what's been happening by accident in half of these incidents anyway.

What I did add is a single `RETRY_SCHEDULE` tuple and a real loop in `api()`, so at least the retry behavior is one deterministic policy instead of five remembered-differently-each-time ones, and so a future run's log line means the same thing every time it says "retried":

```python
RETRY_SCHEDULE = (10, 30, 60)  # seconds; matches the in-run budget this pipeline has actually had time for

def api(path):
    req = urllib.request.Request("https://dev.to/api" + path)
    req.add_header("api-key", os.environ.get("DEV_TO_API", ""))
    req.add_header("User-Agent", "Mozilla/5.0")
    last_err = None
    for wait in (0,) + RETRY_SCHEDULE:
        if wait:
            time.sleep(wait)
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise RuntimeError(f"dev.to API error {e.code}: {e.read().decode()[:400]}") from e
            last_err = e
        except urllib.error.URLError as e:
            raise RuntimeError(f"dev.to API network error: {e.reason}") from e
    raise RuntimeError(f"dev.to API error 429 after {len(RETRY_SCHEDULE)} retries: still rate-limited")
```

I verified this against the real failure shape with `urlopen` stubbed to raise 429 on the first two calls and succeed on the third — it returns the successful payload and calls `time.sleep` exactly twice, matching `RETRY_SCHEDULE[:2]`. I did not change the fact that roughly half of these incidents will still not clear inside a ~100-second retry budget; that's a real constraint of the API, not a bug in this code. What the fix buys is smaller: every future log entry about a 429 now describes the same policy being applied, instead of a different one invented under time pressure each time, which is the only reason I was able to build the table above at all.
