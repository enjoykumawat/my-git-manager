---
title: I Crashed My Own Commit Hook on Purpose to See Whether Git Would Still Let the Commit Through
published: true
tags: claudecode, security, devtools, debugging
---

There's a post trending in the claudecode tag this week about a `PreToolUse` hook that crashes and the tool call runs anyway. The hook was supposed to be a gate, it failed, and nothing stopped the thing it was gating. I don't run Claude Code hooks on this project, but I do have a `prepare-commit-msg` git hook that shells out to an AI call on every commit, and the trending post made me realize I'd never actually verified what happens when that call blows up mid-commit. I'd written the hook to survive a crash. I'd never tested it.

### What the hook is supposed to do

`hooks/prepare-commit-msg` in my-git-manager runs `git_commit.py`, which reads the staged diff and asks `claude -p` for a Conventional Commit message, then writes it into the commit message file git is about to open in your editor. The whole point is convenience: prefill a good message, let you edit or accept it. The actual hook body, after all the comments explaining path resolution, is one line:

```sh
MSG="$(python "$SCRIPT" 2>/dev/null)" && [ -n "$MSG" ] && printf '%s\n' "$MSG" > "$1"
exit 0
```

`git_commit.py`'s stderr goes to `/dev/null`. If it produces nothing on stdout, `MSG` is empty, the `&&` chain short-circuits before the `printf`, and the hook falls through to an unconditional `exit 0` either way. That `exit 0` is doing real work: `prepare-commit-msg` is one of the git hooks where a non-zero exit aborts the commit outright. This hook always exits zero regardless of what happened inside it, which means a crash should, in theory, leave you with whatever message was already in the commit file (git's own template, or `-m` if you passed one) instead of either a broken commit or a bare traceback.

I'd never run a crash through it to check.

### Testing it for real

I built a throwaway repo with the real hook copied in and a `git_commit.py` stand-in that always fails:

```python
import sys
sys.exit("boom: simulated crash, no diff available")
```

First, the actual `prepare-commit-msg` flow: commit with `--no-edit` against a pre-existing message, with the hook's AI call crashing underneath it.

```
$ git commit --no-edit -m "TEMPLATE: pre-existing message"
[master (root-commit) 6b4a491] TEMPLATE: pre-existing message
 1 file changed, 1 insertion(+)
 create mode 100644 file.txt
commit exit code: 0
```

The commit landed with the original message untouched. `git_commit.py` exited non-zero, stderr got swallowed, `MSG` stayed empty, and the hook's own `exit 0` meant git never knew anything upstream had gone wrong. Exactly the design intent: a crashed AI call degrades to "no prefill," not "no commit" and not "corrupted commit message."

Then I checked the other side of the contract, because "this hook always exits 0" is only meaningfully a design choice if a non-zero exit would actually have done something different:

```sh
#!/bin/sh
echo "hook: simulating a real crash that also sets a bad exit code" >&2
exit 1
```

```
$ git commit --no-edit -m "second commit"
hook: simulating a real crash that also sets a bad exit code
commit exit code: 1
$ git log --oneline
6b4a491 TEMPLATE: pre-existing message
```

Only the first commit shows up. The second one never happened: git read the hook's exit code, saw non-zero, and aborted before touching the repository. So `prepare-commit-msg`'s default contract genuinely is fail-closed: if a hook's own exit code says "no," git takes that as "stop." `hooks/prepare-commit-msg` in my repo opts out of that default on purpose, with a bare `exit 0` at the bottom that nothing before it can override.

### Why that's the right call here, and wouldn't be everywhere

This is where the comparison to a `PreToolUse` hook crashing actually matters, and where I want to be careful not to overstate it. I didn't test anyone's coding-agent hook, only my own git hook, so I'm reasoning about the shapes, not claiming the same measurement. A `prepare-commit-msg` hook that prefills a message is pure convenience: its failure mode, worst case, is "you type your own commit message," which is the thing you'd be doing anyway if the hook didn't exist. Fail-open costs you nothing you weren't already risking.

A hook whose job is to block a write, a shell command, or a file edit before it happens is a different animal entirely. If that kind of gate crashes and the framework treats "the hook errored" the same as "the hook said yes," fail-open doesn't degrade to "no convenience feature." It degrades to "no gate." The trending post's point was specifically that a crashing `PreToolUse` hook let the tool call proceed, which is the dangerous version of the exact same fail-open behavior I just deliberately tested and was glad to find in my own hook.

The difference isn't the crash. Both hooks can crash; crashes are going to happen to any hook that shells out to something as unreliable as an LLM call. The difference is what "I don't know, something went wrong" is allowed to default to. For a prefill, defaulting to "do nothing extra" is safe, because doing nothing extra is the pre-hook baseline. For a gate, defaulting to "allow" throws away the one thing the hook existed to provide, and it does it silently, in exactly the cases where something was already wrong enough to make the hook fail in the first place.

If you're writing any hook that's meant to stop something rather than just help with it, the question worth testing — not assuming — is: what does *my* framework do when this hook's own code throws an unhandled exception? Mine, for git, aborts the operation unless the hook script itself swallows the error and says otherwise. I don't know offhand whether every hook framework agrees, and "probably" isn't a great answer for a gate. It's a five-minute test to find out, and now I have one I can point to instead of a guess.
