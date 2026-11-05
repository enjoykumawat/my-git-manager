---
title: What a Regex-Based Claude Code Hook Can and Can't Block
published: true
tags: claudecode, security, devtools, python
---

Claude Code lets you register a `PreToolUse` hook in `settings.json`: a shell command that runs before a tool call, receives the tool name and its input as JSON on stdin, and can approve or block the call before it happens. There's a trending dev.to post this week about writing a hook that "cannot steer your agent," and it got me thinking about something I'd never actually verified for my own setup: when I write a guard hook to stop an agent from running a destructive command, what exactly am I buying? I run an MCP server and a couple of autonomous publishing routines out of this repo, and "an agent can run arbitrary bash" is a live concern, not a hypothetical one. So instead of assuming a guard hook does what I want, I built a minimal one and tested it against inputs it should catch and inputs I suspected it wouldn't.

## The hook

Here's the whole thing — a `PreToolUse` hook that reads the proposed tool call, checks `Bash` commands against a pattern of known-destructive operations, and blocks or approves:

```python
#!/usr/bin/env python3
import json, re, sys

payload = json.load(sys.stdin)
tool_name = payload.get("tool_name", "")
tool_input = payload.get("tool_input", {})

DANGEROUS = re.compile(
    r"\brm\s+-rf\b|\bgit\s+push\s+--force\b|\bgit\s+reset\s+--hard\b"
)

if tool_name == "Bash":
    cmd = tool_input.get("command", "")
    if DANGEROUS.search(cmd):
        print(json.dumps({
            "decision": "block",
            "reason": f"guard_hook: destructive pattern matched: {cmd!r}"
        }))
        sys.exit(0)

print(json.dumps({"decision": "approve"}))
sys.exit(0)
```

Wired into `settings.json` under `hooks.PreToolUse`, this runs on every `Bash` call before it executes. That much is genuinely useful — it's a real gate, enforced outside the model's own judgment, which is the whole point of putting it in a hook instead of a CLAUDE.md instruction the model could ignore or forget under context pressure.

## What it actually catches

I didn't want to trust that description, so I fed the hook the same JSON shape the harness sends it, directly, and checked what came back for four cases.

A safe command:

```bash
$ echo '{"tool_name": "Bash", "tool_input": {"command": "ls -la"}}' | python3 guard_hook.py
{"decision": "approve"}
```

The exact destructive command the regex was written for:

```bash
$ echo '{"tool_name": "Bash", "tool_input": {"command": "rm -rf /important/data"}}' | python3 guard_hook.py
{"decision": "block", "reason": "guard_hook: destructive pattern matched: 'rm -rf /important/data'"}
```

So far, exactly what I wanted. Then the two cases I actually cared about.

The same destructive intent, with the flag built from a variable instead of typed literally:

```bash
$ echo '{"tool_name": "Bash", "tool_input": {"command": "x=rf; rm -$x /important/data"}}' | python3 guard_hook.py
{"decision": "approve"}
```

And the same destructive intent routed through a tool the hook never looks at:

```bash
$ echo '{"tool_name": "mcp__some-server__delete_everything", "tool_input": {"target": "/important/data"}}' | python3 guard_hook.py
{"decision": "approve"}
```

Both slipped straight through. Not because the hook is badly written — because a `PreToolUse` hook, as I'd built it, is a pattern match on one tool's string input. It has no idea what `rm -$x` expands to, because it never runs the command, it only reads the text of the proposed call. And it has no opinion at all about a tool it wasn't told to check, because the hook only fires its destructive-pattern logic inside an `if tool_name == "Bash"` branch I wrote myself.

## Why "cannot steer" is the right framing

This is the part that matches the trending post's title better than I expected going in: the hook doesn't steer anything. It's a yes/no gate on a specific call, evaluated once, with no memory of why the model wanted to run that command or what it's trying to accomplish. It can't redirect the agent toward a safer approach, can't ask a clarifying question, can't even see the two commands I tested back to back and notice they were obviously trying to do the same thing. All it can do is block or approve the literal string it was handed, against whatever pattern you gave it in advance.

That's a meaningfully different security property than "the agent can't do destructive things," and conflating the two is the actual risk. A `PreToolUse` regex hook is good for exactly one thing: catching the destructive command shaped the way you anticipated it being shaped. It's not a semantic safety layer, and treating it like one — "I have a guard hook, so I'm covered" — is how you end up with a false sense of coverage. My four-test matrix caught the gap in about five minutes; I'd rather find that in a scratch sandbox than find out in production that `mcp__some-server__delete_everything` was never on the hook's radar at all.

## What I changed because of this

I'm not deleting the hook — catching the literal `rm -rf` case is still worth having, because plenty of destructive commands really do get typed the obvious way. But I stopped treating it as the control, and started treating it as one layer: the pattern match for the common case, plus actually restricting what tools and MCP servers a given session has access to in the first place, since the hook can only defend territory it's watching. If a tool isn't checked by any hook, the hook isn't a reason to trust it — it's just a tool nobody wrote a check for yet. Worth testing yours the same way before you rely on it: feed it the input you're actually worried about, not just the one you wrote the regex against.
