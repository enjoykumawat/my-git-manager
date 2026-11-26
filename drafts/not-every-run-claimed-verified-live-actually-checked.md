---
title: Not Every Run That Claimed "Verified Live" Actually Checked the URL
published: true
tags: python, devtools, debugging, productivity
---

On November 22nd I shipped a fix to my own publishing pipeline: never trust the dev.to API's 201 response as proof an article is actually live. The POST can succeed and the server can still be wrong, slow to index, or lying about what it stored — so from that point on, every run was supposed to follow the publish call with a fresh HTTP GET of the resulting URL and log the result as evidence, not just repeat what the API claimed.

I logged that fix the same day, in `docs/project_notes/issues.md`, with the usual "Status: Completed" line. Then I went back today and actually read what every subsequent run's "Status" line said, instead of trusting that the fix had stuck.

Here's what each run logged, pulled straight from the file:

```
2026-11-22 (2nd run): "Both verified live: fresh HTTP GET of each URL
  after publish returned 200, and a content check..."          -> VERIFIED
2026-11-23 (1st run): "verified via fresh HTTP 200 fetch of the URL,
  83,962 bytes, <title> present"                                -> VERIFIED
2026-11-23 (2nd run): "verified via fresh HTTP 200 fetch of the URL,
  83,674 bytes, <title> present and matching frontmatter exactly" -> VERIFIED
2026-11-24 (1st run): "Session started in detached HEAD... ran
  scripts/sync-main.sh... Quota check via live GET..."           -> NOT LOGGED
2026-11-24 (2nd run): "Quota check via live GET... showed 2
  published today already..."                                   -> NOT LOGGED
2026-11-25 (1st run): "Quota check via live GET /api/articles/me/
  published?per_page=30 showed 0 published today..."             -> NOT LOGGED
2026-11-25 (2nd run): "Quota check via live GET... showed 2
  published today (the first run's two)..."                      -> NOT LOGGED
```

The fix survived exactly as long as the run that introduced it, plus the next two runs. Then it quietly disappeared from the log for four runs straight — every run from the morning of the 24th through the evening of the 25th, eight published articles, zero logged per-article verification.

I want to be precise about what I'm claiming and what I'm not. I don't know whether those four runs actually skipped the GET and only skipped logging it, or skipped both. The log is all I have, and the log is exactly the thing in question — a "Status: Completed" line that doesn't mention a fetch is consistent with either "it happened and wasn't written down" or "it never happened." That ambiguity is the finding, not a side effect of it: a status line that can't distinguish those two cases isn't doing the job it exists to do.

So I ran the check that four log entries should have run and didn't:

```python
import urllib.request

urls = [
    "https://dev.to/enjoy_kumawat/the-real-security-boundary-in-my-mcp-server-isnt-the-tools-its-what-theyre-allowed-to-write-bg0",
    "https://dev.to/enjoy_kumawat/when-two-functions-guard-the-same-invariant-only-the-one-that-runs-actually-guards-it-2c27",
    "https://dev.to/enjoy_kumawat/trusting-the-prompt-vs-trusting-the-code-how-i-cap-my-own-agents-daily-output-3fo4",
    "https://dev.to/enjoy_kumawat/two-services-two-usernames-one-hardcoded-constant-18k0",
]
for u in urls:
    req = urllib.request.Request(u)
    req.add_header("User-Agent", "Mozilla/5.0")
    r = urllib.request.urlopen(req, timeout=20)
    body = r.read()
    print(u, "->", r.status, len(body), "bytes", "<title>" in body.decode("utf-8", "ignore"))
```

All four came back 200, all with real byte counts (85KB-152KB) and a present `<title>` tag. Nothing was actually wrong. The four runs that skipped logging a receipt didn't produce an incident — this time.

That "this time" is the whole point. The November 22nd fix exists specifically because a 201 response is not proof, and a run that doesn't check can't tell a healthy publish from a silently broken one until something downstream notices — a 404 on a shared link, a missing article in a later audit, a duplicate from a blind retry. For four runs, my own log had exactly the blind spot the fix was built to close, and the only reason nothing went wrong is that dev.to's API didn't fail during that window. The log didn't know that. I didn't know that, until I checked it just now.

Why did it regress? Looking at what changed between the runs that verified and the runs that didn't: the three verifying runs each had a reason to fetch a URL for the article's own subject matter — one was literally about a crash-and-recovery test that needed a live artifact to point at, another built its evidence around byte-for-byte content matching. The four non-verifying runs didn't have an article topic that already demanded a fetch, so the verification step, which isn't enforced by any code (`publish_devto.py` prints a URL and returns; nothing requires the caller to then GET it), had nothing forcing it to happen, and nothing in the log template requires a line stating it happened.

That's the actual bug, and it's a documentation-process bug, not a code bug: the fix was a *practice* I wrote down as a one-time decision, not a *check* with a required field in the log format. A decision that depends on each future run independently remembering to re-derive the same obligation is a decision that will drift the moment a run has no incidental reason to do it anyway.

The fix for the fix is boring on purpose: I'm adding a line to this file's own logging convention — every "Status" entry for a publish run must either show the GET-and-check result for each URL it published, or explicitly say "not verified this run" if it skipped it. Either is honest. What isn't honest is a "Completed" that looks identical whether the check ran or not. A status field with only one value for two different underlying facts isn't a status, it's a flag that always reads "fine" — which is a close cousin of the exact problem the November 22nd fix was written to stop at the API boundary. I just hadn't pointed it at my own paperwork yet.
