---
title: I Pass Git Diffs to My AI Commit Generator as a Command-Line Argument. A Big Enough One Breaks It.
published: true
tags: python, ai, mcp, debugging
---

Same project as usual: a small MCP server and a standalone script that both turn a git diff into a Conventional Commit message by shelling out to `claude -p`. Both call sites build the same shape of command:

```python
raw = subprocess.check_output(
    ["claude", "-p", "--safe-mode", full],  # full = system prompt + diff, one argv element
    text=True,
    timeout=20,
    stderr=subprocess.PIPE,
)
```

`full` is the whole prompt — instructions plus the entire staged diff — packed into a single item in that list. `subprocess` hands that list to `execve` more or less as-is. I'd fixed timeouts on this call, added `--safe-mode` so it doesn't drag in this repo's `CLAUDE.md`, hardened the exception handling around it more than once. What I'd never asked is: how big can `full` actually get before something breaks, and what breaks when it does?

## finding the ceiling

The kernel caps how much data you can hand to `execve` in one call — argv plus environment combined. On Linux you can check it directly:

```
$ getconf ARG_MAX
2097152
```

Two mebibytes, on the machine I'm running this on. That sounds like plenty for a text diff. It is, for a typical commit. It is not, for a lockfile regeneration, a big generated-code refactor, or a vendored dependency getting bumped — any of which can produce a diff in the hundreds of KB to multiple MB range without anyone doing anything unusual.

I reproduced the failure directly, without needing a huge real diff, by matching the exact call shape and just making the payload big:

```python
import subprocess
big = "x" * (3 * 1024 * 1024)  # 3 MiB, comfortably over ARG_MAX
subprocess.check_output(["true", big])
```

```
OSError: [Errno 7] Argument list too long: 'true'
```

That's `E2BIG` — the same error class you'd get from `claude -p --safe-mode <huge string>`. I checked both call sites' exception handling against it:

```python
except subprocess.TimeoutExpired:
    ...
except subprocess.CalledProcessError as e:
    ...
except FileNotFoundError:
    ...
```

None of those is `OSError`. `TimeoutExpired` and `CalledProcessError` are subclasses of `subprocess.SubprocessError`, not `OSError`; `FileNotFoundError` is a specific `OSError` subclass for a missing executable, and doesn't catch a different one. `E2BIG` sails straight past all three, exactly like it did in my repro.

## two call sites, one uncaught error, two different blast radii

The standalone script, `git_commit.py`, is invoked from a `prepare-commit-msg` git hook. Its stderr gets thrown into `/dev/null` by the hook itself, so a crash here just silently produces no AI commit message — annoying, but you notice and write your own.

The MCP tool version, `server.py`'s `_claude()`, backs `generate_commit_message` — a tool a connected agent can call directly. An uncaught `OSError` there doesn't quietly do nothing; it propagates as a raw, unhandled error back through the MCP layer to whatever's driving the tool call. Same root cause, worse failure mode, because the caller here is a program, not a human staring at a blank commit message wondering what happened.

## the fix I didn't ship

My first instinct was to switch the prompt to stdin instead of argv — `claude -p` would read it from a pipe, no argv limit to hit at all. I went looking at `claude --help` to confirm the CLI actually supports that, and came away not fully sure it does without testing an actual authenticated call, which I didn't want to do just to confirm a flag's behavior. I'd rather ship something I've verified than something I'm guessing about, so I didn't make that change.

What I shipped instead is a bound, checked before the argv is even built, in both files:

```python
_MAX_DIFF_BYTES = 200_000  # comfortably under the 2 MiB ARG_MAX on this machine

if len(diff.encode()) > _MAX_DIFF_BYTES:
    print(
        f"Staged diff is {len(diff.encode())} bytes, over the "
        f"{_MAX_DIFF_BYTES}-byte limit for a claude -p argv. Write your own commit message.",
        file=sys.stderr,
    )
    raise SystemExit(1)
```

and the MCP-server equivalent, inside `_claude()`:

```python
if len(full.encode()) > _MAX_CLAUDE_ARG_BYTES:
    return f"ERROR: prompt is {len(full.encode())} bytes, over the {_MAX_CLAUDE_ARG_BYTES}-byte claude -p argv limit."
```

200 KB is nowhere near the actual 2 MiB ceiling — deliberately, since the ceiling also has to fit the environment block, not just argv, and I'd rather fail predictably with headroom than find a second, tighter edge case later. Neither function silently truncates the diff and asks for a commit message anyway; a summary generated from a chopped-off diff is worse than no summary, since it looks complete and isn't.

I verified the fix against the same repro shape — a prompt just over the new bound, run through `_claude()` directly:

```python
result = _claude("x" * (_MAX_CLAUDE_ARG_BYTES + 1))
assert result.startswith("ERROR:") and "argv limit" in result
```

That case is now a permanent part of `server.py --selftest`, so it's not just a one-time check — regressing this bound will fail the test suite, not just wait to be rediscovered live. `git_commit.py`'s check has the same top-level-script limitation the UTF-8 fix in this same file has (no function boundary to stub around), so that half is verified live but not automated — an honest gap, not a hidden one.

## the actual lesson

Every prior fix to this call site was about *how* the subprocess gets invoked — with a timeout, with `--safe-mode`, with the right exception types for network- and process-level failures. None of them asked how much data was safe to hand it as a literal command-line argument, because argv has always just been "the way you pass a prompt to a CLI tool" — an implementation detail, not something with its own failure mode. It has one anyway. If you're piping arbitrary-length data — a diff, a file, anything without a hard size cap — into a subprocess via `argv` instead of `stdin`, that's worth checking before a big enough input finds the ceiling for you.
