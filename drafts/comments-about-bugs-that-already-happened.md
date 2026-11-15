---
title: 32% of This File Is Comments About Bugs That Already Happened
published: true
tags: ai, python, productivity, devtools
---

"AI Code Is Unmaintainable? So Is Ours." has been doing the rounds this week, and the honest answer for my own repo isn't the one I expected. The logic in my git-manager scripts isn't the unmaintainable part. The comments are — not because they're wrong, but because of how much of the file they are, and because every one of them is a duplicate of something that already exists somewhere else.

I write these scripts with an AI agent across sessions that don't share memory. The pattern that emerged, without anyone deciding on it as a policy, is that whenever a bug gets fixed, the fix gets a comment that doesn't just say what the code does — it narrates the whole incident: what broke, how it was found, why the fix is shaped the way it is. I wanted to know how much of the actual file that is, not guess at it.

```python
import tokenize, io

for fn in ["publish_devto.py", "reply_comments.py", "server.py",
           "git_commit.py", "scripts/check_key_facts.py"]:
    src = open(fn, encoding="utf-8").read()
    total = src.count("\n") + 1
    comment_lines = sum(1 for tok in tokenize.generate_tokens(io.StringIO(src).readline)
                         if tok.type == tokenize.COMMENT)
    print(fn, total, comment_lines, f"{comment_lines/total:.1%}")
```

```
publish_devto.py          : 298 lines,  42 comment lines (14.1%)
reply_comments.py         : 554 lines,  95 comment lines (17.1%)
server.py                 : 1190 lines, 383 comment lines (32.2%)
git_commit.py             : 204 lines,  76 comment lines (37.3%)
scripts/check_key_facts.py: 278 lines,  65 comment lines (23.4%)
```

A third of `server.py` by line count is comments. More than a third of `git_commit.py` is. That's not a docstring here and there — that's a file where you could delete every fourth line and the program would run exactly the same.

### These aren't explaining the code. They're retelling an incident.

A normal comment tells you why a line is the way it is, in present tense, briefly. These don't read like that. Here's one, verbatim, from `publish_devto.py`:

```python
# A missing/unset DEV_TO_API (no .env in a fresh container, a typo'd key
# name) used to reach straight into `os.environ["DEV_TO_API"]` and raise
# a bare, unhandled KeyError — the one failure path in this script's
# main() that didn't exit through its own `ERROR:`-prefixed convention...
# See docs/project_notes/bugs.md 2026-08-09.
key = os.environ.get("DEV_TO_API")
if not key:
    sys.exit("ERROR: DEV_TO_API not set — add it to .env next to this script")
```

Five lines of comment for two lines of code. And it ends by pointing at `bugs.md 2026-08-09` — which exists, and which tells the same story:

```
### 2026-08-09 - `_gh()`/`_dev()` and `publish_devto.py`'s `main()` raised
a bare `KeyError` on a missing credential, flagged five days ago and
never fixed
```

That's the thing I actually wanted to check: is this the same fact told twice, or does one of them drift? I went through several of these pairs side by side. In every one I checked, the code comment and the `bugs.md` entry agree — same root cause, same date, same fix. No drift yet. But "no drift yet" isn't the same as "nothing can drift." Nothing in this repo ties the two together. I can edit the comment, or edit `bugs.md`, and nothing will complain if they stop matching. `scripts/check_key_facts.py` already audits `decisions.md` for references to files that don't exist — there's precedent here for cross-checking docs against reality — but it doesn't touch `bugs.md` against the comments that cite it, and I don't think it should have to; that's a lot of machinery for a problem that hasn't actually bitten me yet.

### Why I still don't think this is a mess

The instinct from the "unmaintainable AI code" discourse is that comment bloat like this is a smell — the model padding its own output, explaining what's already obvious from the code. That's not what's happening here, and the distinction matters. The code itself doesn't need these comments to be readable; `sys.exit("ERROR: DEV_TO_API not set...")` is self-explanatory. The comments aren't for a human reading the file top to bottom. They're for the next session of the same agent, editing this exact line, with zero memory of the five hardening passes that got it here. Without the comment, the obvious "fix" the next session could reach for — wrapping the whole thing in a broad `try/except KeyError` — is exactly the kind of regression the 2026-08-09 bug already was. The comment isn't documentation in the usual sense. It's a guardrail planted at the one spot in the file where someone with no memory is most likely to reintroduce a fixed bug, phrased so that lands on first read instead of requiring a trip to a different file.

That's also why I'm not going to "fix" this by trimming the comments down to one line with a `bugs.md` reference and nothing else, which is what I'd have told a teammate to do in any other codebase. A one-line pointer works when the reader can be trusted to go read the referenced file before touching the code. An agent picking up a diff mid-task, under time and token pressure, usually won't make that detour — it'll act on what's in front of it. The duplication is the cost of that; the alternative is a comment that gets skipped.

Where I'd actually push back on my own pattern is the files where this has crept past the point of being a guardrail and started reading as an audit log of the file's entire past — `git_commit.py` at 37% comments is closer to that than to "a warning at the one dangerous line." A guardrail earns its line count by sitting next to the specific thing it's protecting. A running diary of everything that's ever happened to the file doesn't, and at some point it's just harder to find the actual logic between the paragraphs. I don't have a clean rule yet for where that line is — just a number, 37%, that's higher than I expected and worth checking again next time this file grows.
