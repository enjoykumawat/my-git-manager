---
title: "Claude Code's PreToolUse Hook Only Blocks a Tool Call on Exit Code 2, and Every Other Failure Mode Lets It Run Anyway"
published: true
tags: claudecode, security, devtools, python
---

I run a scheduled publishing routine against a `my-git-manager` repo that writes dev.to articles and commits to git on a fixed cadence. Every run spins up a fresh Claude Code session in a disposable container, and every run is supposed to hold to the same guardrails: a particular git identity, a particular commit convention, no AI attribution in certain fields. I'd been assuming a `PreToolUse` hook that errors out is a safe failure — worst case, the guardrail just doesn't fire and I notice later from the log. I'd never actually tested what "errors out" means to Claude Code, as opposed to what it means to me.

So I tested it, with two throwaway project directories and nothing more exotic than `.claude/settings.json`.

**Setup 1 — an actual crash.** A `PreToolUse` hook on the `Bash` matcher that raises an unhandled Python exception:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -c \"raise Exception('deliberate hook crash for test')\""
          }
        ]
      }
    ]
  }
}
```

Then a headless run: `claude -p "Run this exact bash command using the Bash tool, nothing else: echo HOOK_TEST_MARKER_12345" --output-format json`.

The command ran. `HOOK_TEST_MARKER_12345` printed. The session transcript (`~/.claude/projects/.../*.jsonl`) shows exactly why — there's an attachment the CLI writes for a failed hook that never surfaces in the terminal output at all:

```json
{
  "type": "hook_non_blocking_error",
  "hookName": "PreToolUse:Bash",
  "hookEvent": "PreToolUse",
  "stderr": "Failed with non-blocking status code: Traceback (most recent call last):\n  File \"<string>\", line 1, in <module>\nException: deliberate hook crash for test",
  "exitCode": 1
}
```

`exitCode: 1`, labeled `non-blocking` right in the field Claude Code writes about its own failure. The next entry in the transcript is the tool result: `"HOOK_TEST_MARKER_12345"`, `is_error: false`, `permissionDecision: {"decision":"accept","source":"config"}`. The crash left a trace in the transcript if you go looking for it, but nothing stopped the Bash call, and nothing in the final assistant message mentioned a hook ever ran.

**Setup 2 — a deliberate block**, same matcher, same marker pattern, different hook body:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'deliberate block: not allowed' >&2; exit 2"
          }
        ]
      }
    ]
  }
}
```

Same prompt, different outcome. `HOOK_TEST_MARKER_BLOCK_999` never printed. The run's `permission_denials` array now has an entry for the `Bash` call, and the model's own final message says it plainly: *"The command didn't run. A PreToolUse hook on Bash blocked it... I haven't tried it again or found another way around the hook."*

Same matcher, same shell-command hook type, same `Bash` tool target. The only difference between "silently skipped, tool runs anyway" and "actually stops the agent" was `exit 1` versus `exit 2`. That's the documented convention — exit code 2 means "blocking," anything else non-zero is reported but doesn't block — but a convention you have to already know to read correctly is exactly the kind of thing that's invisible until you deliberately break it. An uncaught exception, a missing dependency, a typo'd shell command inside the hook script, a `jq` call against malformed stdin — none of those are going to politely `exit 2` on your behalf. They're going to crash with whatever exit code the interpreter happens to use, and in Python's case (and most others) that's `1`.

Which means the actual security property of a `PreToolUse` guardrail hook isn't "does it correctly detect the bad command," it's "does it crash in a way that happens to equal 2." Those are different claims, and only one of them usually gets tested. I'd been writing hooks and checking that the *matching logic* was right — does the regex catch `rm -rf`, does it catch the MCP-tool equivalent — without ever asking what happens when the hook itself is the thing that's broken.

This repo already has a real example of the alternative design, just in a different hook system. `hooks/prepare-commit-msg` wraps a call to `git_commit.py`, which shells out to `claude -p` to turn a staged diff into a commit message. The fix recorded for it on 2026-07-23 was specifically about this failure shape: capture the AI output into a variable *first*, and only overwrite git's own commit-message template if that capture actually succeeded. A failed `claude -p` call leaves the editor showing git's default template — an empty-ish, obviously-unfinished message a human has to notice and fill in — instead of silently writing nothing, or writing a stack trace into the commit message. That's fail-closed by construction: the failure mode is loud and inconvenient rather than invisible.

A `PreToolUse` hook that exits 1 on a crash is the opposite shape by default, and nothing about writing the hook tells you that's what you got. If you're using one of these hooks as an actual control — blocking force-pushes, blocking writes outside a sandboxed directory, enforcing a commit identity before a tool runs — the fix isn't "write better hook logic," it's making sure the hook script itself cannot exit anything but `0` or `2`. Concretely, that means wrapping the real check in something like this instead of trusting the script to behave:

```bash
#!/usr/bin/env bash
set -o pipefail
if ! output=$(run_real_check "$@" 2>&1); then
  echo "$output" >&2
  exit 2   # always 2 on any failure, never whatever the real check happened to exit with
fi
exit 0
```

One line (`exit 2`, not `exit $?`) is the entire difference between a hook that fails closed under its own bugs and one that fails open under them. I hadn't written that line into any of my own hooks before running this test, because I'd never had a reason to think the two exit paths behaved differently enough to matter.
