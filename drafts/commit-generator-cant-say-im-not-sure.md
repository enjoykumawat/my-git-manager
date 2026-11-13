---
title: What Happens When a Commit-Message Generator Can't Say "I'm Not Sure"?
published: true
tags: ai, llm, debugging, devtools
---

A trending post this week argued that an agent isn't hallucinating when it gives a confident wrong answer — it's doing exactly what its rules told it to, because the rules never defined what "I don't know" looks like. I have a small, boring, real example of that sitting in my own repo: `git_commit.py`, a script that reads a staged diff and asks `claude -p` for a Conventional Commit message. I'd never actually checked whether its system prompt leaves room for the model to say "this diff doesn't fit cleanly into one type." So I checked, by running it against diffs built specifically to not fit cleanly.

## The prompt as written

Here's the actual system prompt, unchanged, from `git_commit.py`:

```python
SYSTEM = (
    "You are a git commit message generator. "
    "Output ONLY the commit message — one line, no explanation, no markdown, no quotes, "
    "no co-author lines, no signatures, no AI references. "
    "Follow Conventional Commits: type(scope): subject. "
    "Types: feat, fix, docs, style, refactor, test, chore. "
    "Subject: imperative, lowercase, max 72 chars."
)
```

Read it as a set of exits available to the model. There are exactly seven: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`. There's no eighth option for "both of the above," no instruction for what to do if a diff touches two unrelated concerns, and "Output ONLY the commit message" explicitly forbids adding a caveat even if the model wanted to. Whatever diff comes in, something in that list of seven has to come out, in one line, with no hedge. That's not a flaw I'm claiming the script has — for the diffs it's normally fed, picking one type is exactly right. I wanted to see what happens at the edges.

## Test 1: a diff with two unrelated changes stapled together

I built a synthetic diff that does two things a human would almost certainly split into two commits: adds a new feature (split-card payments) and separately swaps a hardcoded gateway URL from v1 to v2.

```python
MIXED_DIFF = """diff --git a/payments.py b/payments.py
index 1111111..2222222 100644
--- a/payments.py
+++ b/payments.py
@@ -10,6 +10,9 @@ def charge_card(amount, token):
     if amount <= 0:
         raise ValueError("amount must be positive")
+    # NEW: support split payments across two cards
+    if isinstance(token, (list, tuple)) and len(token) == 2:
+        return _charge_split(amount, token)
     return _gateway.charge(amount, token)
 
 def _gateway_url():
-    return "https://api.old-gateway.example.com/v1/charge"
+    return "https://api.new-gateway.example.com/v2/charge"
"""
```

I ran it through the exact same call shape `git_commit.py` uses — same system prompt, same `claude -p --safe-mode`, same environment scrubbing of `GITHUB_TOKEN`/`DEV_TO_API` the script already does:

```python
raw = subprocess.check_output(
    ["claude", "-p", "--safe-mode", SYSTEM + "\n\n" + diff],
    text=True, timeout=30, stderr=subprocess.PIPE, env=_env(),
).strip()
```

Live result:

```
feat(payments): add split card payments and switch to v2 gateway
```

One line, fully confident, zero hedging — and it quietly merged a new feature and an API endpoint migration (arguably a breaking change on its own) into a single `feat` commit. Nothing about the output signals that these were two separable changes. A human reviewing a diff like this would likely say "these should be two commits" before writing either message. The model never gets the chance to say that, because the prompt doesn't ask it to evaluate whether one type is actually sufficient — only to pick one.

## Test 2: a diff Conventional Commits doesn't clearly define

Second test: a pure file rename with zero content change.

```python
RENAME_ONLY_DIFF = """diff --git a/utils/helpers.py b/lib/helpers.py
similarity index 100%
rename from utils/helpers.py
rename to lib/helpers.py
"""
```

Conventional Commits itself doesn't pin down whether a content-free rename is `chore` (no production code change) or `refactor` (a structural change to the codebase). Reasonable people pick either. The live result:

```
refactor(lib): move helpers module from utils to lib
```

Again, one confident answer, no "could also be chore" — which is a defensible choice, but it's indistinguishable from a case where the model actually had a principled reason to prefer `refactor` over `chore`. From the output alone you can't tell "I resolved a genuine ambiguity" from "I had to pick something and this is what came out."

## What this is and isn't

This isn't a bug report. `git_commit.py` isn't broken — on the diffs it's actually fed day to day (one coherent change, one obvious type), it does its job. What I'm pointing at is a structural property of the setup, not an edge case in the code: give a model a closed label set and an instruction that forbids anything but exactly one label, and you've engineered away its ability to ever say "neither of the above" or "actually, both" — regardless of how good the model is. The failure mode in the trending post's framing ("confidently wrong because the rules never defined uncertain") doesn't need a weird prompt or an adversarial input to show up. It shows up from a completely ordinary multi-concern diff, the kind that gets written by hand all the time when someone is in a hurry.

A fix I didn't implement, and want to flag honestly as unverified rather than claim as done: detecting when a diff spans clearly unrelated hunks (different functions, no shared symbols) before calling `claude -p` at all, and either splitting the prompt into two commit-message calls or explicitly telling the model it's allowed to output "needs manual split" as an eighth outcome. Both of those change the contract this script has had since ADR-004 established the `claude -p` subprocess pattern, so they'd need their own round of actual testing against real staged diffs before I'd trust them — which is exactly the same discipline this post is about in the first place: don't assume the fix works until you've run it.
