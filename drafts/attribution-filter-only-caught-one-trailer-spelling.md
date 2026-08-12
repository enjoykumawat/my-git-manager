---
title: My Commit Message Filter Only Knew One Way to Say "Written by Claude"
published: true
tags: ai, python, git, security
---

`git_commit.py` in my project is a small script: it reads the staged diff, sends it to `claude -p` with a system prompt asking for a Conventional Commit message, and prints the result. `server.py`'s MCP tool `generate_commit_message` does the same thing through a different interface. Both have a system prompt that says, in effect, "no co-author lines, no signatures, no AI references" — but a system prompt is a request, not a guarantee, so both files also carry a regex safety net that strips anything attribution-shaped out of whatever comes back, just in case the model doesn't fully comply.

I've hardened that regex three separate times over the past few weeks. Every single time, the fix went the same direction: the filter was too aggressive and wiped legitimate commit messages that happened to mention "llm" or "claude" in a normal technical sentence — a commit fixing an MCP timeout, a doc update about a Claude Code hook. I never once checked the opposite direction until this week: what attribution phrasings does the filter *fail* to catch?

## The list it was built from

Here's `_STRIP_PATTERNS`, identical in both `git_commit.py` and `server.py`, before this week:

```python
_STRIP_PATTERNS = [
    r"co-authored-by\s*:",
    r"generated (with|by)\s+claude",
    r"\bclaude code\b",
    r"\bwritten by (an )?(ai|llm|claude|chatgpt|copilot)\b",
    r"\bai-generated\b",
    r"🤖",
]
```

Every one of these six patterns is shaped around a specific incident. `co-authored-by\s*:` exists because that's the exact trailer format that leaked into a commit on 2026-06-21. `\bclaude code\b` and the "written by" pattern came out of later incidents with the same shape. The list grew by accretion, one real leak at a time — which means it's really good at catching the *one* attribution style that's actually happened here, and says nothing about every other conventional way to credit a contributor in a commit message.

I tested that theory directly against the compiled regex, no `claude -p` call needed:

```python
>>> _STRIP_RE.search("Signed-off-by: Claude <noreply@anthropic.com>")
None
>>> _STRIP_RE.search("Reviewed-by: Claude <noreply@anthropic.com>")
None
>>> _STRIP_RE.search("Assisted-by: AI")
None
>>> _STRIP_RE.search("noreply@anthropic.com")
None
```

`Signed-off-by:` is a standard git trailer — the Developer Certificate of Origin format, `git commit -s` output, familiar to anyone who's contributed to a project that requires DCO sign-off. `Reviewed-by:` and `Acked-by:` are just as standard, used constantly in kernel-style workflows. None of them are exotic. They're arguably *more* likely than `Co-Authored-By:` for a model that's read a lot of real-world git history to reach for if it decides to credit itself despite the system prompt saying not to — and every one of them sailed through this filter untouched, no strip, no error, nothing. A commit message that looked completely clean would have gone out the door with a live attribution trailer sitting in it.

## Why nobody caught this sooner

I went back through the three prior hardening passes on this exact list. 2026-07-22 fixed a bare-substring match that was over-triggering. 2026-07-26 shipped essentially the same fix four days later after it turned out the first pass missed a case. 2026-07-29 found that `server.py`'s copy of the list hadn't even gotten the earlier hardening that `git_commit.py`'s had. Three fixes, three commits, and every single one was reactive — a specific false positive got reported or noticed, and the pattern got narrowed or duplicated to fix that one case.

Nobody tried the inverse test: take the instruction the filter is supposed to enforce ("no signatures") and enumerate the other plausible ways to violate it, then check whether the regex catches those too. A blocklist built entirely from postmortems only ever covers postmortems that already happened.

## The fix

Two new patterns, added to both files' identical `_STRIP_PATTERNS` list:

```python
r"\b(signed-off-by|reviewed-by|acked-by|tested-by|reported-by|co-developed-by|assisted-by)\s*:\s*(claude|chatgpt|copilot|anthropic|ai|llm)\b",
r"noreply@anthropic\.com",
```

The trailer pattern is anchored to the *value* after the colon, not just the label — `signed-off-by\s*:` on its own would have been the lazy version, and it would have reintroduced exactly the false-positive class the 2026-07-22 fix already spent a whole pass cleaning up. A commit message that says `docs: add reviewed-by field to PR template generator` has the word "reviewed-by" in it but nothing that looks like an AI name after a colon, so it has to survive. I added both directions as permanent regression cases:

```python
_CASES = [
    # ... existing cases ...
    ("Signed-off-by: Claude <noreply@anthropic.com>", True),
    ("Reviewed-by: Claude <noreply@anthropic.com>", True),
    ("Co-Developed-By: Claude", True),
    ("Assisted-by: AI", True),
    ("noreply@anthropic.com", True),
    # Benign vocabulary overlap — must still survive.
    ("docs: add reviewed-by field to PR template generator", False),
    ("feat: signed-off-by trailer support for DCO bot", False),
]
for line, expect_stripped in _CASES:
    got = bool(_STRIP_RE.search(line))
    assert got == expect_stripped, (line, got, expect_stripped)
```

Ran it before and after: every bypass phrasing above matched `None` on the old pattern list and matches on the new one; the benign-overlap cases matched `None` on both, so the fix doesn't trade new false positives for closing the false negatives. Both files' `--selftest` blocks pass with the new cases included.

## What I'd actually take from this

A safety-net regex that's only ever been tightened in response to specific leaks will, by construction, have a blind spot shaped exactly like "anything nobody has leaked yet." That's not a criticism of the earlier fixes — narrowing a false positive when you find one is the right response in the moment. But it's worth periodically asking the filter's question backwards: not "did this actually-seen bad input get caught," but "here's the general shape of thing I'm trying to block, what other spellings of it exist that I haven't tried." For a "no attribution" filter, that meant sitting down and listing standard git trailer conventions instead of only the one that happened to show up here first.
