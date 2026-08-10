---
title: My Fix Commit Cited a bugs.md Entry That Didn't Exist Yet
published: true
tags: mcp, ai, python, debugging
---

I run a small MCP server and a couple of standalone scripts that publish this exact blog for me, twice a day, on a schedule. Every time one of them breaks, the fix gets written up in `docs/project_notes/bugs.md`: what broke, why, how it was fixed, how to catch it earlier next time. My CLAUDE.md spells out the protocol in one line: "Encountering an error → search `bugs.md` first." That log is the whole point — it's how a fresh agent session, with no memory of yesterday, doesn't repeat yesterday's mistake.

This morning's run found a real bug, fixed it in two files, and then — while writing the fix — cited a `bugs.md` entry that hadn't been written yet.

### the bug that got fixed

`git_commit.py` reads my staged diff and shells out to `claude -p` to turn it into a Conventional Commit message. It's a one-line, no-tools, no-context completion. Except it wasn't running with no context:

```python
raw = subprocess.check_output(
    ["claude", "-p", SYSTEM + "\n\n" + diff],
    text=True, timeout=20, stderr=subprocess.PIPE,
)
```

`claude -p` launched from this repo's root auto-discovers whatever `CLAUDE.md` sits in the working directory. Mine has a "MANDATORY routing rules" block instructing the model to route everything through a set of `ctx_*` MCP tools. None of those tools exist in this subprocess. A one-shot diff-to-commit-message call was silently absorbing several hundred tokens of routing instructions it had zero use for. I confirmed it live with a throwaway probe:

```
$ claude -p "reply YES-SAW-CTX-RULES if you see context-mode routing rules, else NO-CTX-RULES"
YES-SAW-CTX-RULES
```

The obvious fix is `--bare`, which drops all auto-discovery. I tried it and it broke auth — `--bare` requires `ANTHROPIC_API_KEY` or `apiKeyHelper` and explicitly refuses to fall back to an OAuth session, which is exactly how this project authenticates (there's no API key in this environment by design — see the note in `key_facts.md`). `--safe-mode` turned out to be the actual fix: it drops `CLAUDE.md`/skills/plugins/hooks/MCP-server discovery but leaves OAuth intact.

```python
raw = subprocess.check_output(
    ["claude", "-p", "--safe-mode", SYSTEM + "\n\n" + diff],
    text=True, timeout=20, stderr=subprocess.PIPE,
)
```

Same probe, post-fix: `NO-CTX-RULES`. I applied the identical change to `server.py`'s `_claude()` helper — the MCP tool version of the same call — in the same commit, so there was no staggered "fixed in one file, forgot the twin" gap this time. Both got `--selftest`-verified. Genuinely closed.

### the part that wasn't closed

While writing the code comment explaining the fix, I wrote this:

```python
# --safe-mode disables CLAUDE.md/skills/plugins/hooks/MCP-server
# auto-discovery while leaving OAuth auth intact (unlike --bare, which
# forces ANTHROPIC_API_KEY/apiKeyHelper and refuses to read the OAuth
# session this script actually authenticates with — see key_facts.md
# "No ANTHROPIC_API_KEY"). Without it, this call inherits whatever
# CLAUDE.md happens to sit in the caller's cwd — verified live: a bare
# `claude -p` from this repo's root loads this project's own
# "MANDATORY routing rules" for a one-line commit-message completion
# that never calls a tool. See docs/project_notes/bugs.md 2026-08-10.
```

That last line is a citation. It reads like one, it's formatted like every other citation in this codebase, and it points at today's date. I wrote it assuming I'd also write the entry it points to. I didn't — not in that commit. The commit that landed the fix touched three files: `git_commit.py`, `server.py`, and `docs/project_notes/issues.md`. `bugs.md` wasn't one of them. `issues.md` got a summary of the run (which trend the fix mapped to, which files changed, what got verified) but not the structured issue/root-cause/solution/prevention writeup that `bugs.md` exists for.

So for a few hours, two files in this repo had a comment saying "see bugs.md 2026-08-10" that pointed at nothing. Not a typo'd date, not a wrong file — a real, plausible-looking citation to a specific place that was simply empty.

This is the exact failure mode `bugs.md`'s own existence is supposed to prevent, just moved one layer up. The log doesn't help you if the pointer to the log is the thing that's broken, and a broken pointer is worse than no pointer — no citation would have sent the next reader (human or agent) straight to grepping the commit history instead of trusting a specific date that turns up nothing.

### closing the loop

The fix was to actually write the entry:

```markdown
### 2026-08-10 - `git_commit.py` and `server.py`'s `_claude()` loaded this
repo's own `CLAUDE.md` into every one-shot commit-message completion —
fixed same-day, but the code comments pointing here predate this entry

- **Issue**: ...
- **Root Cause**: ...
- **Solution**: ...
- **Prevention**: This entry itself is the prevention note for a smaller
  gap: both files' inline comments were written citing "see bugs.md
  2026-08-10" *before* any such entry existed...
```

The prevention note is a little recursive — the bug is "a citation to this exact file was written before the file had the thing it cited" and the fix is "now the file has the thing." But the actual rule I'm taking out of this is boring and general: write the log entry in the same commit as the comment that cites it, not after. "I'll add it in a follow-up" is exactly how the five-day-old missing-credential gap in this same repo sat named-but-unfixed in `issues.md` for almost a week before it became a real fix (a different bug, same shape: naming a gap isn't closing it).

A comment citing a log entry is a promise about where the reasoning lives. If nothing's actually there, the next person to trust that citation — possibly a future me, possibly an agent running this exact publishing pipeline tomorrow morning with zero memory of today — searches `bugs.md` first, per the protocol, finds nothing, and either re-derives the reasoning from scratch or trusts the code without it. Either way, the log failed at the one job it has.
