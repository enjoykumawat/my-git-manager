---
title: My AI-Attribution Filter Stopped Over-Matching Ordinary Words. It Still Wipes Any Commit That's Legitimately About Claude Code.
published: true
tags: git, ai, claudecode, debugging
---

This repo has a git hook that generates commit messages with `claude -p`, then runs the output through a filter that strips anything that looks like AI self-attribution — no "Co-Authored-By: Claude," no "🤖 Generated with Claude Code" footer, nothing that violates the project's no-AI-attribution rule. A few weeks ago I found and fixed a real bug in that filter: it used bare substring matching, so a legitimate commit like `fix: retry llm calls on 429 with backoff` got silently erased just for containing the word "llm." I replaced the bare substrings with anchored regexes and moved on, confident the filter was now precise.

It's more precise. It's still wrong, in the opposite direction, for one specific pattern.

## Re-testing the fix that already shipped

The current filter lives in both `server.py` and `git_commit.py` (same logic, two files — a known drift risk in this repo I've written about before):

```python
_STRIP_PATTERNS = [
    r"co-authored-by\s*:",
    r"generated (with|by)\s+claude",
    r"\bclaude code\b",
    r"\bwritten by (an )?(ai|llm|claude|chatgpt|copilot)\b",
    r"\bai-generated\b",
    r"🤖",
]
_STRIP_RE = re.compile("|".join(_STRIP_PATTERNS), re.IGNORECASE)
```

Auditing this file for the audit-log bug I wrote about separately, I re-ran the fixed regex against realistic inputs instead of trusting that "anchored now" meant "correct now." The line I stopped on was `r"\bclaude code\b"`. It's a bare phrase match — no requirement that "Claude Code" appear as part of an attribution statement. And this project's own commit history is full of legitimate reasons to say "Claude Code" as a plain technical noun: it's the name of the CLI tool this repo's hooks, scripts, and MCP server all wrap.

```python
candidates = [
    "fix: retry llm calls on 429 with backoff",
    "docs: add claude code hook install instructions",
    "feat: wire up claude code review workflow for PRs",
    "chore: document claude code slash commands in README",
    "fix: handle claude code MCP timeout in server.py",
]
for c in candidates:
    print(bool(_STRIP_RE.search(c)), "|", c)
```

```
False | fix: retry llm calls on 429 with backoff
True  | docs: add claude code hook install instructions
True  | feat: wire up claude code review workflow for PRs
True  | chore: document claude code slash commands in README
True  | fix: handle claude code MCP timeout in server.py
```

Four out of five candidates get stripped, and none of them are attribution. They're ordinary descriptions of work on this repo's own git hook and MCP tooling — the exact kind of commit this repo generates constantly, since half its work log is about fixing `hooks/prepare-commit-msg`, `scripts/install-hooks.sh`, and the `claude -p` wrapper itself.

## Why this is worse than the last version of the bug

The generator's system prompt tells `claude -p` to output exactly one line — no explanation, no markdown, just the commit message. The filter operates per-line:

```python
msg = "\n".join(
    l for l in raw.splitlines()
    if not _STRIP_RE.search(l)
).strip()
```

When the output is genuinely multi-line, stripping one offending line still leaves the rest of the message intact. But the system prompt guarantees there's only ever one line to begin with. If that single line matches `_STRIP_RE` for any reason — including a false positive — `msg` becomes the empty string. There's no partial redaction, no fallback line, nothing. `hooks/prepare-commit-msg` checks `[ -n "$MSG" ]` before writing anything to the commit editor, so an empty message here is indistinguishable from "the AI call produced nothing" or "the hook isn't installed" — the exact failure mode two earlier bug-log entries already covered for different root causes. This bug produces the same silent symptom through a third mechanism: a working hook, a working `claude -p` call, a real one-line commit message, deleted in full because it happened to describe the tool by name.

## Why I can't just delete the line

My first instinct was that `r"\bclaude code\b"` looks redundant with `r"generated (with|by)\s+claude"` — surely "Generated with Claude Code" already matches the second pattern. I checked before assuming that:

```python
import re
p = re.compile(r"generated (with|by)\s+claude", re.I)
print(bool(p.search("🤖 Generated with [Claude Code](https://claude.ai/code)")))
```

`False`. The real attribution footer Claude Code emits is markdown-linked — `[Claude Code](url)` — and the bracket sits between "with" and "Claude," breaking the no-punctuation assumption in the existing pattern. The bare `\bclaude code\b` line isn't dead weight; it's the only pattern in the list that actually catches the bracketed real-world footer. Deleting it would have reopened the exact hole the filter exists to close, just to fix the false positive I'd found. That's not a fix, that's trading one bug for the other.

## The actual fix

Scope the match to require an attribution preposition immediately before "claude code," and allow the bracket:

```python
r"\b(with|by|using|via)\s*\[?\s*claude code\]?",
```

Reran both sides of the test:

```
🤖 Generated with [Claude Code](https://claude.ai/code)  -> True  (still caught)
Co-Authored-By: Claude <noreply@anthropic.com>             -> True  (still caught)
generated by claude code                                   -> True  (still caught)
docs: add claude code hook install instructions             -> False (no longer stripped)
feat: wire up claude code review workflow for PRs            -> False (no longer stripped)
chore: document claude code slash commands in README         -> False (no longer stripped)
fix: handle claude code MCP timeout in server.py              -> False (no longer stripped)
```

Every real attribution shape I tested still gets caught. Every legitimate technical mention now survives. Applied the same one-line change to both `server.py` and `git_commit.py`, since they share the pattern list by copy, not by import — the same twin-drift shape that's bitten this repo before, so I checked both files instead of just the one I started reading.

## The general lesson

"I anchored the regex, so it's precise now" and "I anchored the regex correctly" are different claims, and only the second one is worth writing a bug-log entry closed. A blocklist filter guarding against a specific bad phrase needs testing against two directions, not one: does it still catch the bad phrase in its real, messy form (markdown brackets included), and does it now let through the ordinary vocabulary of the exact project it's running in. I'd tested the first direction when I shipped the anchored-regex fix. I hadn't tested the second, and this repo's own commit history is the one place where "the tool's own name" and "a phrase that means AI wrote this" are guaranteed to collide.
