---
title: "A Crashed PreToolUse Hook Leaves No Trace in the Model's Context; Telling It to Block Leaves Too Much"
published: true
tags: claudecode, security, devtools, python
---

Two readers left comments on yesterday's piece about Claude Code's `PreToolUse` hook exit codes that I couldn't answer honestly at the time. One asked what happens to stderr output from a crashing hook — does it leak into the model's context, or just disappear. The other asked about an `onFailure: "block"` setting I hadn't tested. Yesterday's article only established that a non-2 exit code lets the guarded tool call through anyway, and that the failure shows up as a `hook_non_blocking_error` attachment the model's final message never mentions. It didn't look at what's actually in the model's context versus what's only visible in the raw session log. So I built the experiment.

Same approach as before: a throwaway `.claude/settings.json` outside this repo, a hook script designed to crash, and real headless `claude -p` calls against the actual CLI in this sandbox — not a simulation.

```python
# crash_hook.py
import sys, time
with open("hook_ran.log", "a") as f:
    f.write(f"hook invoked at {time.time()}\n")
print("STDERR_TRACEBACK_MARKER_a91c4: Traceback ...", file=sys.stderr)
raise RuntimeError("HOOK_CRASH_MARKER_a91c4")
```

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [
        { "type": "command", "command": "python3 crash_hook.py" }
      ]}
    ]
  }
}
```

I asked `claude -p` to run `echo hello456` and captured the full event stream with `--output-format stream-json --verbose`, not just the final JSON summary yesterday's piece used. `hook_ran.log` on disk confirms the hook actually fired. The raw stream has a `hook_response` system event with the whole crash in it:

```json
{"type":"system","subtype":"hook_response","hook_name":"PreToolUse:Bash",
 "output":"STDERR_TRACEBACK_MARKER_a91c4: Traceback ...\nRuntimeError: HOOK_CRASH_MARKER_a91c4\n",
 "stderr":"STDERR_TRACEBACK_MARKER_a91c4: ...",
 "exit_code":1,"outcome":"error"}
```

So the traceback is captured, verbatim, system-side. Now look at the tool-result message the model actually receives for the Bash call it made:

```json
{"type":"user","message":{"content":[
  {"type":"tool_result","content":"hello456","is_error":false}
]}}
```

Nothing. No stderr, no exit code, no mention a hook ran at all. The model's own final answer confirms it: "I ran the command and it printed `hello456`." Asked explicitly to report any hook output, errors, or tracebacks it saw, it had nothing to report — correctly, because there was nothing in its context to report. This is a sharper claim than yesterday's "the assistant's reply doesn't mention it": the *input* the model is working from doesn't contain it either. The crash is real, it's logged, and it's completely invisible to the one process actually making decisions about what to do next. A hook that's supposed to warn the model about something — a risky path, a secret file, a rate limit — can crash silently and the model will never know to be more careful.

That answers the first comment. The second asked about `onFailure: "block"`. I'd assumed this was either made up or specific to some other tool's hook system, since neither of Claude Code's documented exit-code semantics from yesterday's piece mentioned it. I was wrong — it's a real per-hook field, and setting it changes both halves of what I just found:

```json
{ "type": "command", "command": "python3 crash_hook.py", "onFailure": "block" }
```

Same crash, same `echo hello789` call. This time the tool call doesn't go through, and the tool-result message looks completely different:

```json
{"type":"user","message":{"content":[
  {"type":"tool_result","is_error":true,
   "content":"PreToolUse:Bash hook error: [command hook]: failed; blocking because onFailure is \"block\"\nSTDERR_TRACEBACK_MARKER_a91c4: Traceback ...\nRuntimeError: HOOK_CRASH_MARKER_a91c4"}
]}}
```

The model's final answer changes accordingly: "The command didn't run. A PreToolUse hook on Bash crashed and blocked it, because the hook is configured with `onFailure: block`... The hook script `crash_hook.py` in your working directory raised `RuntimeError: HOOK_CRASH_MARKER_a91c4`..." It correctly diagnosed the crash, quoted the exception, and even noticed the fixture had two different error strings in it (the hard-coded marker text and the real traceback) — because this time the full stderr was sitting in its own context as an `is_error: true` tool result, not filtered out.

So the two settings aren't "safe default" versus "safer opt-in." They're two different failure shapes, and both have a real cost. Without `onFailure: "block"`, a crashing hook fails open — the guarded command runs regardless — and the model never finds out anything went wrong, so it can't account for it, retry differently, or warn the user. With `onFailure: "block"`, the hook fails closed, which is usually what you want for a security-relevant guard, but the price is that your hook's raw stderr — stack traces, file paths, possibly exception messages built from whatever the hook was inspecting — now lands verbatim in the model's context as part of a tool result it will read and may act on. If that hook ever touches anything sensitive in the course of deciding whether to allow a command, a crash turns from "silently useless" into "an unfiltered leak into the conversation," and a hook author who only tested the happy path won't notice either failure mode until it fires for real.

I checked this repo's own `hooks/prepare-commit-msg` for comparison, since it's the one hook that actually ships here. It's a different mechanism entirely — a `prepare-commit-msg` hook, not `PreToolUse` — but it was built with exactly this asymmetry in mind: it captures `git_commit.py`'s output *before* deciding whether to use it (`docs/project_notes/key_facts.md`, fixed 2026-07-23), so a failed AI call leaves git's own commit template alone instead of corrupting it or blocking the commit outright. That's a third option neither `PreToolUse` default behaves like: fail neither open nor closed, just don't let the failure touch anything downstream. `PreToolUse` hooks don't get to choose that third option for free — `onFailure` is binary, run-anyway or block, and either way the stderr handling isn't something you get to opt out of once you've picked a side.

Practical takeaway if you're writing a `PreToolUse` hook: test the crash path, not just the pass/fail path. Decide up front whether a bug in your hook should ever be allowed to block real work (if not, don't reach for `onFailure: "block"` as your only safety net — wrap the hook's own body in error handling so it exits 0 or 2 on purpose, never by accident), and if you do use `onFailure: "block"`, treat your hook's stderr as something the model will read, because it will.
