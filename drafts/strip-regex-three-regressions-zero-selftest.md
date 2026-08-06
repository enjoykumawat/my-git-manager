---
title: My Repo's Riskiest Regex Has Regressed Three Times on Record. It Never Got the Test Pattern I Gave Everything Else.
published: true
tags: python, debugging, ai, devtools
---

This repo has a small habit I picked up a few weeks ago without really deciding to: whenever a script's logic is deterministic — pure input-to-output, no network call, no subprocess — I give it a `--selftest` block. Run the script with that flag and it checks its own logic against a handful of fixed cases instead of doing its real job. Three scripts in this repo have one now: `publish_devto.py` tests its frontmatter parser, `scripts/list_all_published_titles.py` tests its pagination loop against a stubbed multi-page fixture, `reply_comments.py` tests its comment-tree walk. I added all three after finding real bugs in exactly that kind of logic — the pattern earns its keep every time I touch one of those files, because I don't have to trust my own re-reading of a regex or a loop condition, I can just run it.

So I went looking for what else in this repo has that same shape — deterministic, previously buggy, still running unverified — and found the one piece of logic that should have gotten a `--selftest` before any of the three that actually did.

## The regex that's already broken twice

`git_commit.py` and `server.py` both carry an identical block: a list of regex patterns that strip AI self-attribution lines out of a generated commit message, so `claude -p`'s output never lands a `Co-Authored-By: Claude` or a `🤖 Generated with Claude Code` footer in this repo's git history.

```python
_STRIP_PATTERNS = [
    r"co-authored-by\s*:",
    r"generated (with|by)\s+claude",
    r"\b(with|by|using|via)\s*\[?\s*claude code\]?",
    r"\bwritten by (an )?(ai|llm|claude|chatgpt|copilot)\b",
    r"\bai-generated\b",
    r"🤖",
]
_STRIP_RE = re.compile("|".join(_STRIP_PATTERNS), re.IGNORECASE)
```

This exact list has already been wrong twice, on the record. On 2026-07-22 an audit found the first version used bare substrings, so any legitimate commit mentioning "llm" — `fix: retry llm calls on 429 with backoff` — got silently erased in full, not partially redacted. That sat unfixed for four days and got fixed on 2026-07-26. Then on 2026-08-02, re-testing the fixed version against realistic commit messages turned up the opposite failure: the bare `\bclaude code\b` pattern was catching ordinary technical mentions of the tool this repo is built around — `docs: add claude code hook install instructions` — because it required no attribution context at all, just the phrase. Both times, the way I caught the regression was the same: sit down, write out a handful of realistic commit messages by hand, run them through `_STRIP_RE.search()` in a scratch interpreter, eyeball the True/False output.

That's a test. I was writing the exact same test by hand, three separate times, in three separate weeks, and throwing it away each time instead of committing it.

## Checking it's actually missing, not just uncommitted

```
$ grep -rn "selftest" --include="*.py" .
./reply_comments.py:154:    if "--selftest" in sys.argv:
./reply_comments.py:206:        print("selftest ok")
./scripts/list_all_published_titles.py:67:    if "--selftest" in sys.argv:
./scripts/list_all_published_titles.py:95:        print("selftest ok")
./publish_devto.py:116:    if "--selftest" in sys.argv:
./publish_devto.py:122:        print("selftest ok")

$ grep -n "_STRIP\|selftest" server.py
91:_STRIP_PATTERNS = [
99:_STRIP_RE = re.compile("|".join(_STRIP_PATTERNS), re.IGNORECASE)
115:        if not _STRIP_RE.search(l)
```

Three hits for `selftest`, none of them in `git_commit.py` or `server.py`. The file with the most documented history of getting this exact piece of logic wrong is the one file the pattern never reached, even though the other three scripts picked it up after bugs that were, if anything, less likely to recur — a pagination off-by-one and a frontmatter parser don't get re-edited nearly as often as a hand-tuned attribution blocklist that keeps needing a new exception carved into it.

## Why "I already tested it in the article" isn't the same as a test

The 2026-08-02 fix has a whole section walking through before/after regex output for eight realistic commit messages. That's real verification — it's just verification that lived in a markdown file and a scratch REPL session, not in the repo. The next time someone (me, or the AI session running this scheduled task) touches `_STRIP_PATTERNS` — adding a pattern for some new attribution phrase dev.to's own comments have already started flagging — nothing forces those eight cases to run again. The only thing standing between a third regression and a merged commit is remembering that a markdown file three weeks old contains the cases worth re-checking.

## The fix

Same shape as the other three scripts, applied to both files that carry a copy of the regex:

```python
if "--selftest" in sys.argv:
    _CASES = [
        ("co-authored-by: claude <noreply@anthropic.com>", True),
        ("🤖 generated with [claude code](https://claude.ai/code)", True),
        ("generated by claude code", True),
        ("written by an ai", True),
        ("fix: retry llm calls on 429 with backoff", False),
        ("docs: add claude code hook install instructions", False),
        ("feat: wire up claude code review workflow for prs", False),
        ("fix: handle claude code mcp timeout in server.py", False),
    ]
    for line, expect_stripped in _CASES:
        got = bool(_STRIP_RE.search(line))
        assert got == expect_stripped, (line, got, expect_stripped)
    print("selftest ok")
    raise SystemExit(0)
```

The eight cases are just the regression examples from both prior bugs, put back to work instead of left in prose. Ran it:

```
$ python3 git_commit.py --selftest
selftest ok
```

`server.py` gets the identical block inside its `if __name__ == "__main__":` guard, before `mcp.run()` — same cases, checked separately on purpose. The two files carry the pattern list by copy, not by import (a drift risk I've written about before), so a passing test in one file says nothing about the other. I could only actually run `server.py --selftest` by pulling `_STRIP_RE` out into a standalone snippet and testing it there — this sandbox doesn't have the `mcp` package installed, so `server.py` itself won't import here at all. That's an honest gap: the logic is verified identical, the file with the MCP import around it isn't executable in this environment to prove it. Worth closing for real the next time this repo runs somewhere `pip install -r requirements.txt` has actually happened.

## The general shape of the miss

The pattern I'd already adopted — deterministic logic gets a `--selftest`, hit by a real bug, don't trust re-reading — was correct. I just applied the trigger ("this had a real bug") instead of the actual criterion the trigger was standing in for ("this is deterministic and I keep manually re-verifying it"). `_STRIP_RE` matched the second one first and hardest, and I still walked past it three times because I was reaching for the pattern only right after fixing something, not when I noticed myself doing the same manual check for the third time. A blocklist regex that's already needed two corrections is exactly the kind of code that earns a permanent test before the third correction, not after it.
