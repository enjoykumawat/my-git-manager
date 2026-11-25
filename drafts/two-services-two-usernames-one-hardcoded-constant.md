---
title: Two Services, Two Usernames, One Hardcoded Constant
published: true
tags: python, devtools, debugging, mcp
---

My GitHub handle is `enjoykumawat`. My DEV.to handle is `enjoy_kumawat`. One letter apart — an underscore — and for the first few days of running the MCP server behind this account, that underscore was the whole problem.

The original setup kept one `.env` file with `GITHUB_USERNAME=enjoy_kumawat` in it, because that's the value I'd typed in when I set up the DEV.to side first and never revisited. Every GitHub API call built from that variable 404'd, because the account `enjoy_kumawat` doesn't exist on GitHub — mine there has no underscore. The fix that's been in place since, recorded as ADR-003 in this repo's decision log, was to stop reading either username from config at all:

```python
# server.py
GITHUB_USERNAME = "enjoykumawat"
DEV_USERNAME = "enjoy_kumawat"
```

Two plain constants, one per platform, defined once in code and imported everywhere that needs them. No `.env` key to mistype, no risk of the DEV.to value leaking into a GitHub call because they're not sharing a variable name anymore. The ADR's reasoning holds up: config is for things that actually vary between environments or deployments. My GitHub username is never going to be different depending on which machine the script runs on. Hardcoding it didn't lose any flexibility I was using.

For a while I treated that as the whole fix. It wasn't.

Five months and change after ADR-003 landed, a routine audit of this account's own published articles (checking every GitHub link across 92 posts actually resolved) turned up a third spelling nobody had caught: this account's second-ever article, published the same day as the username bug above, linked to `github.com/enjoy-kumawat` — hyphenated. Not the GitHub spelling, not the DEV.to spelling, a third one that only ever existed as text typed into that article's source file. It had been sitting there, 404ing, for 45 days before anyone looked.

What makes that interesting isn't that there was a second bug — it's *why* the hardcoded constant did absolutely nothing to prevent it. `GITHUB_USERNAME = "enjoykumawat"` guards every code path that reads that variable. The script that posted the broken article didn't read that variable; the wrong string was hand-typed straight into the markdown body, by a script that's since been deleted, and never touched the constant at all. A hardcoded value is a fix for the paths that go through the value. It has zero reach into content a human — or an LLM drafting an article — types out fresh.

That's a distinction I hadn't thought about cleanly until I dug through why the second bug happened despite the first fix being in place for months. A config bug and a prose typo look similar (both are "the wrong username showed up somewhere") but they need completely different defenses: one is a code-level problem with a code-level fix, the other is a content-level problem that needs a content-level check, run against the actual output, not the code that produced it.

So I wrote the check that should have existed after the first bug, not just after discovering the second one. It's small on purpose — not a general link-checker, just a direct scan for the specific wrong spellings this account has actually produced:

```python
import re, pathlib

BAD_PATTERNS = {
    r"github\.com/enjoy-kumawat": "hyphenated (never existed)",
    r"github\.com/enjoy_kumawat": "underscored (that's the DEV.to spelling, not GitHub's)",
}

root = pathlib.Path(".")
hits = []
for path in root.rglob("*"):
    if path.is_file() and path.suffix in (".py", ".md") and ".git" not in path.parts:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, why in BAD_PATTERNS.items():
            for m in re.finditer(pattern, text, re.IGNORECASE):
                line_no = text.count("\n", 0, m.start()) + 1
                hits.append((str(path), line_no, m.group(), why))

for h in hits:
    print(f"{h[0]}:{h[1]}  {h[2]!r}  -- {h[3]}")
```

Running it against this repo right now turns up exactly the places you'd expect: the draft and the log entries that document the original 2026-08-05 bug, which still contain the bad string because they're *about* the bad string, and nothing live. No new, undiscovered instance — which is the right outcome, but only because someone already fixed the one real case and wrote it down. The value of the script isn't today's clean result; it's that it now runs as a five-second check instead of a 92-article manual audit the next time this account's publishing pipeline writes a GitHub link into something, and nobody has to remember to re-run that audit by hand.

The general shape I'd take from this to any project with more than one platform identity in play: hardcoding an identity constant is the right call the moment you've confirmed it genuinely never varies — it closes off an entire class of cross-platform key collision, permanently, and ADR-003 has held for five months without a repeat of the original bug. But it only closes the paths that read the constant. If the same identity ever gets typed into generated content — an article, a commit message, a comment reply — that's a second surface, and it needs its own check, because the fix for "the code reads the wrong value" and the fix for "the output contains the wrong value" are not the same fix, even when the wrong value is identical both times.
