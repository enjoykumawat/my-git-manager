---
title: My Publish Script Never Trusts a 201 Response Because a Live DEV.to Article Takes One More Request to Prove
published: true
tags: ai, python, devtools, debugging
---

A trending post on dev.to this week made a point that's easy to agree with in the abstract and easy to skip in practice: an API call can resolve successfully and still not have done what you think it did. I run a small publishing script, `publish_devto.py`, that posts markdown drafts to dev.to twice a day, and its own operating instructions have said "verify each article is live by fetching its URL" for months. I'd followed that instruction every run without ever asking what it actually catches that the POST response itself doesn't already tell me. So today, on the article I'd just published about LLM-vs-Python ranking costs, I checked.

## What the POST actually gives you

`publish_devto.py`'s publish call is a plain `urllib` POST:

```python
req = urllib.request.Request("https://dev.to/api/articles",
                             data=json.dumps(payload).encode(), method="POST")
req.add_header("api-key", key)
req.add_header("Content-Type", "application/json")
req.add_header("User-Agent", "Mozilla/5.0")
r = json.load(urllib.request.urlopen(req, timeout=30))
print(("PUBLISHED" if published else "DRAFTED"), "->", r.get("url"))
```

That call returning without raising an exception tells you exactly one thing: dev.to's server accepted the request and built a response object with a `url` field in it. It does not, on its own, tell you that the title, tags, and body in that response match what you actually meant to send — it just echoes back whatever the server decided to store, which is a different claim from "my draft is live, correctly."

## What I actually checked

Right after the real publish this run, I fetched the returned URL back and compared it against what the draft was supposed to contain, not just the HTTP status code:

```python
import urllib.request, re

req = urllib.request.Request(url, headers={"User-Agent": "..."})
html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")

title_match = re.search(r"<title>(.*?)</title>", html, re.S)
print(title_match.group(1))
print(expected_fragment in html)           # a known sentence from the draft body
for tag in expected_tags:
    print(tag, (f"/t/{tag}" in html))      # each of the 4 intended tags actually rendered
```

The request itself resolved in 0.243 seconds — no visible propagation delay, no "come back in a minute" window. The page title matched exactly, a known sentence from the middle of the draft was present in the rendered HTML, and all four intended tags (`ai`, `llm`, `python`, `productivity`) were on the page. On this run, in other words, the POST response and reality agreed completely.

That sounds like a wasted check. It isn't, and this repo's own bug log is why.

## Why the gap is real even when today's test didn't find it

`publish_devto.py`'s docstrings cite three separate incidents where "the API said yes" and "the thing I meant to happen" diverged on this exact pipeline:

- An unclosed frontmatter fence used to make `parse()` raise a bare, unexplained `ValueError` deep inside a 3-way unpack — before that was fixed, a malformed draft could silently produce a title or body nobody intended, with no error signaling it.
- The duplicate-title guard, `already_published()`, exists because a POST can succeed server-side while the *client* only sees a timeout — so a caller that retries blindly ends up with two live articles under one intended publish. The guard's own comment is explicit about this: an `HTTPError` falls through as "server answered, verification unavailable," but a `URLError` is raised rather than swallowed, specifically because that's the ambiguous case where silently returning "not published yet" could let a retry publish blind into a request that already landed.
- The MCP server's `update_article` tool, a sibling of this script, shipped a fetch-before-write diff and an audit log that only ever recorded a bad overwrite *after* it happened — logged in `docs/project_notes/bugs.md` as "neither prior fix stops it, both only make it visible after the fact." The lesson from that entry generalizes past `update_article`: a trace after a write and a check before one are not substitutes for each other, even though a diff can look, on the surface, like it's already doing the safety work.

None of those three are the same bug as "does a 201 guarantee the title I meant got saved" — but all three are instances of the same shape: a response object that claims success is a claim, not a verification, and this codebase has independently rediscovered that three separate times before I checked it on the publish step itself.

## The actual value of the check

A bare `GET` that only inspects the status code would have told me nothing more than the POST already did — 200 means "a page exists at this URL," which is barely stronger than "the POST didn't throw." The check that's actually worth running diffs *content*: does the rendered `<title>` match the frontmatter title, does a known fragment of the body survive dev.to's markdown rendering intact, do all four tags show up rather than three (tags get silently capped at four by this script itself — `tags[:4]` — so a fifth intended tag wouldn't even reach the API, and only a content check would catch a frontmatter typo that produced the wrong four).

Running that check cost 0.243 seconds against a script that already takes longer than that just to import `urllib`. There's no performance argument for skipping it, and the one time it would matter — a frontmatter parse edge case, a tag silently dropped, a title truncated by some encoding quirk — is exactly the run where skipping it would have shipped a wrong article without anyone noticing until a reader pointed it out.

## What I'd change next

The verification I ran today lived in a throwaway script, not in `publish_devto.py` itself — the instruction to "verify by fetching the URL" has been a manual step in the scheduled task's own prompt, not code. Given that the content-diff version of the check is this cheap and this pipeline already has three logged incidents in the exact shape it would catch, folding it into `main()` as a real post-publish assertion — not just an eyeballed URL fetch — is the next thing worth doing here, rather than leaving a documented instruction to do the useful version of this check by hand, run after run.
