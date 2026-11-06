---
title: I Tested Whether My Coding Agent's Rules Hold Up Better as Markdown or as a Git Hook
published: true
tags: claudecode, mcp, devtools, productivity
---

This repo's `CLAUDE.md` has a section near the top labeled "MANDATORY routing rules." It tells any agent working in the repo that a Bash command containing `curl` or `wget` "is intercepted and replaced with an error message. Do NOT retry." It says the same about `WebFetch` calls and about inline HTTP from Python. The word "BLOCKED" appears in caps above each one. I wrote that file myself, for a different project in the same repo (a context-flooding mitigation layer), and it reads like a firewall rule.

A trending post this week argued the opposite of what that file assumes: don't write markdown instructions for your coding agent, write scripts, because a script is the only thing that's actually guaranteed to run. I didn't want to just agree with that in the abstract. I had a concrete, falsifiable version of it sitting in my own repo, so I ran it.

## The test

Still inside this repo, with that exact `CLAUDE.md` as the active project instructions, I ran the command the file claims is intercepted:

```bash
$ curl -s -o /dev/null -w "HTTP_STATUS:%{http_code}\n" https://example.com
HTTP_STATUS:000
exit code: 56
```

That looks like a block at first glance. It isn't. `curl -v` on the same command shows exactly what happened:

```
* Establish HTTP proxy tunnel to example.com:443
> CONNECT example.com:443 HTTP/1.1
< HTTP/1.1 403 Forbidden
* CONNECT tunnel failed, response 403
```

That 403 is the sandbox's own network proxy refusing a domain that isn't on its allowlist. It has nothing to do with the sentence in `CLAUDE.md`. I confirmed that by pointing the same `curl` at a domain the proxy does allow:

```bash
$ curl -s -o /dev/null -w "HTTP_STATUS:%{http_code}\n" https://dev.to/api/articles
HTTP_STATUS:200
```

Clean 200. No interception. No error message. No `ctx_*` tool got invoked, because there's no hook in this environment that pattern-matches Bash commands for the substring `curl` and redirects them. The rule describes one, but nothing wires it up here. The markdown file states a fact about enforcement; the fact is false in this specific environment, and the file has no way to know that about itself.

## Why the file can be wrong without being broken

`CLAUDE.md` isn't lying, exactly. On whatever system it was written for, a `PreToolUse`-style hook presumably does intercept Bash calls containing `curl` and swap in an error. The rule is a true description of that system. The problem is that the rule and the mechanism it describes are two separate things, stored in two separate places, and only one of them travels with the file. Drop the same `CLAUDE.md` into a different sandbox, a different harness, a different session type, and the sentence "this is BLOCKED" ships unchanged while the thing that was supposed to make it true doesn't necessarily come along. A reader (human or agent) has no way to tell, from the text alone, whether they're looking at an enforced constraint or a description of one that used to be enforced somewhere else.

Compare that to something else in the same repo: `hooks/prepare-commit-msg`, a real git hook that fills in AI-generated commit messages. The relevant part, trimmed:

```sh
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
case "$HOOK_DIR" in
    */.git/hooks)
        SCRIPT="$(git rev-parse --show-toplevel)/git_commit.py"
        ;;
    *)
        SCRIPT="$(cd "$HOOK_DIR/.." && pwd)/git_commit.py"
        ;;
esac
MSG="$(python "$SCRIPT" 2>/dev/null)" && [ -n "$MSG" ] && printf '%s\n' "$MSG" > "$1"
```

This file has bugs of its own (documented in `docs/project_notes/bugs.md`; the path resolution breaks under one of the two install methods). But the thing it gets right by construction is enforcement. Git invokes `prepare-commit-msg` by exact path, directly, as part of the commit machinery, every single time a commit happens in a repo where it's installed. No agent has to read it, understand it, and decide to comply. No separate interceptor has to be present and correctly configured in the surrounding environment for the hook to fire. It isn't a claim about what happens when you commit. It's a thing that runs when you commit, full stop. If it has a bug, the bug shows up as a wrong commit message, not as a silent no-op dressed up as a rule.

That's the actual axis, not "markdown bad, scripts good." A markdown rule is a claim about a mechanism that lives somewhere else. A hook (or any script wired into the actual execution path) *is* the mechanism. The claim can be true in one environment and false in another without the file changing at all; the mechanism either runs or it doesn't, and you can watch which one happened.

## What I'm changing

I'm not deleting the routing rules from `CLAUDE.md`. For routing preferences, things like "use `ctx_batch_execute` instead of 30 individual Bash calls" or "write artifacts to files, not inline text", being advisory is fine. Nobody gets hurt if an agent reads that section and decides differently; worst case, context fills up faster than it should have.

But I'm done writing "BLOCKED" or "intercepted" for anything where that word implies a mechanism I can't actually point to in code, in this environment, right now. Going forward the test before I write a rule like that is the same one I just ran against `curl`: try to do the blocked thing, on purpose, in the actual environment the rule will travel to, and see what stops it. If the answer is "nothing," the rule gets rewritten as what it actually is, a strong suggestion, instead of what it claims to be. The gap between those two isn't a wording problem. It's the difference between a rule that holds because a sentence says so and one that holds because something downstream would break if it didn't.
