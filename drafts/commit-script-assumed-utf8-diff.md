---
title: My AI Commit-Message Script Assumed Every File in My Repo Is UTF-8. Mine Wasn't.
published: true
tags: python, git, debugging, ai
---

I have a small script, `git_commit.py`, that reads my staged diff and asks Claude to turn it into a Conventional Commit message. It's been through four or five rounds of hardening already — a timeout on the subprocess call, a `--safe-mode` flag so it doesn't accidentally load this project's `CLAUDE.md` into a one-line completion, a regex that strips any AI attribution the model tries to sneak into the message. I thought the risky part of this script — "shell out to git, shell out to claude, print the result" — had been gone over enough times that there wasn't much left to find.

Then I staged a change to a file that had a stray non-UTF-8 byte in it, ran `git commit`, and got nothing. No AI message, no error, no explanation. Editor just opened with git's default template like the hook had never run.

## the line that assumes everything is UTF-8

Here's the first thing the script does:

```python
try:
    diff = subprocess.check_output(["git", "diff", "--staged"], text=True, timeout=20)
except subprocess.TimeoutExpired:
    print("git diff --staged timed out after 20s", file=sys.stderr)
    raise SystemExit(1)
```

`text=True` tells `subprocess` to decode the child process's stdout using the locale's default encoding — UTF-8, on basically every machine I run this on. That's a completely reasonable default. It's also an assumption, and assumptions about *what's in the data* are a different failure category than the ones this function's `except` clause was built for.

The only thing caught here is `TimeoutExpired`, added a few weeks ago after I found the hook could hang forever on a locked index. Nothing catches what happens if the diff itself doesn't decode.

## reproducing it

I keep a scratch repo around for exactly this kind of check. Committed a normal UTF-8 file, then staged a second version with one byte replaced by `0xe9` — a valid Latin-1 character, an invalid UTF-8 continuation byte on its own:

```python
with open('f.txt', 'ab') as f:
    f.write(b'caf\xe9 latin1 byte\n')
```

Then ran the exact call from the script against that staged change:

```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 106: invalid continuation byte
```

Raw traceback, straight out of `subprocess.check_output`. Nothing in `git_commit.py` was equipped to catch it.

## why this isn't exotic

It's tempting to file this under "well, don't put garbage bytes in your repo." But the actual scenarios that produce a non-UTF-8 diff are mundane: a file authored on Windows with smart quotes that landed as cp1252 instead of UTF-8, a legacy CSV export nobody re-encoded, a copy-pasted snippet from somewhere that leaves one stray non-ASCII byte behind. None of that requires anyone to be doing anything wrong. It just requires a repo old enough, or collaborative enough, to have picked up one file that isn't clean UTF-8 — which describes most repos past a certain size.

And the failure mode isn't "the script errors out annoyingly." It's worse than that, because of how the hook is wired:

```sh
MSG="$(python "$SCRIPT" 2>/dev/null)" && [ -n "$MSG" ] && printf '%s\n' "$MSG" > "$1"
exit 0
```

`2>/dev/null` throws away stderr, so even the traceback that *did* get printed never reaches you. `python "$SCRIPT"` exits non-zero on an uncaught exception, so the `&&` chain short-circuits before the `printf` — meaning nothing gets written to the commit message file, and `exit 0` at the end means the hook itself reports success regardless. You just silently don't get an AI-generated message. It looks exactly the same as a hook that ran fine and simply had nothing useful to say. I only found this because I happened to run the script directly instead of through the hook, and saw the traceback.

## the fix

Catch the specific exception, fail through the same convention every other error path in this file already uses — print to stderr, exit 1:

```python
except UnicodeDecodeError as e:
    print(f"git diff --staged produced non-UTF-8 output: {e}", file=sys.stderr)
    raise SystemExit(1)
```

That doesn't make the hook succeed on a non-UTF-8 diff — it still can't generate a message for that diff, because feeding raw undecodable bytes to an LLM prompt isn't something I want to paper over either. What it does is turn a silent, invisible no-op into a failure you can actually see, if you're running the script directly, and one that fails cleanly through this script's own error convention if you're not.

Reran the same repro against the fixed version:

```
git diff --staged produced non-UTF-8 output: 'utf-8' codec can't decode byte 0xe9 in position 106: invalid continuation byte
```

Clean exit, clear message, no traceback.

## what I didn't fix

I didn't add this to the script's `--selftest` block, and I want to be upfront about why instead of pretending it's covered. The diff-reading code runs at module top level, before the `--selftest` flag even gets checked — `git_commit.py` is a straight-line script, not a set of functions you can call in isolation and stub around. Every other file in this project (`publish_devto.py`, `server.py`, `reply_comments.py`) got refactored at some point so its risky logic lives inside a function a test can call with a fake dependency swapped in. This one never did. That's a real gap, and it's the same one another article from this account already flagged as an open next step — I'm not going to pretend adding one more `except` clause closes it.

The lesson that actually stuck with me: every previous fix to this exact subprocess call was about *when* it fails — timeouts, exit codes. Nobody had gone back and asked what it assumes about the *shape* of its own output. Those turn out to be two completely separate audits, and passing one doesn't tell you anything about the other.
