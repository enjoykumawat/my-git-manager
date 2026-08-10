---
title: I Ran `claude -p` for One Commit Message. My Whole CLAUDE.md Came Along Uninvited.
published: true
tags: claudecode, ai, python, devtools
---

I have a 20-line script called `git_commit.py` that reads `git diff --staged` and shells out to `claude -p` to turn it into a Conventional Commit message. It's about as narrow a task as an LLM call gets: one diff in, one line out. No file exploration, no tool use, nothing that should care what project it's running in.

```python
raw = subprocess.check_output(
    ["claude", "-p", SYSTEM + "\n\n" + diff],
    text=True,
    timeout=20,
    stderr=subprocess.PIPE,
).strip()
```

I only went looking at this because I was reviewing my repo's `CLAUDE.md` for an unrelated reason and noticed it opens with a block the file itself calls "MANDATORY routing rules" — instructions about routing shell output through sandbox tools, blocking `curl`, indexing web pages before reading them, that kind of thing. None of it applies to a script whose entire job is "here's a diff, give me a commit message." So I assumed it didn't matter: `git_commit.py` calls `claude -p` with a fully self-contained system prompt and a diff string. Why would it load a project instructions file at all?

I checked instead of assuming. From the repo root, I ran the same shape of call `git_commit.py` makes, with a prompt that just asks the model to say whether it saw those rules:

```bash
$ claude -p "Reply with exactly one line: either 'YES-SAW-CTX-RULES' if your \
context includes instructions mentioning ctx_fetch_and_index or context-mode \
MANDATORY routing rules, or 'NO-CTX-RULES' if it does not. Nothing else."
YES-SAW-CTX-RULES
```

It loaded it. A bare `claude -p` invocation with no flags picks up `CLAUDE.md` from whatever directory it's launched in, the same auto-discovery an interactive session does, regardless of whether the prompt has anything to do with the project. `git_commit.py` doesn't pass a `cwd` to `subprocess.check_output`, so it inherits the caller's — which for a script that's supposed to be run from inside the repo, is exactly this directory.

That file is 4,404 bytes, 79 lines. Roughly a thousand tokens of routing rules, output-format constraints, and a project memory-system protocol block, none of which a one-shot "diff → commit message" completion has any use for. It's not incorrect, exactly — the commit message that comes back is still fine. It's just a fixed cost, paid silently, on every single call, for content the task can't act on.

The part that actually worried me wasn't the token cost. It was the coupling. `git_commit.py`'s behavior is nominally defined entirely by the `SYSTEM` string hardcoded at the top of the file:

```python
SYSTEM = (
    "You are a git commit message generator. "
    "Output ONLY the commit message — one line, no explanation, no markdown, no quotes, "
    ...
)
```

But that's not actually true. Whatever `CLAUDE.md` happens to exist in the cwd at call time rides along too, unannounced, and can just as easily change the output. If some future edit to this project's `CLAUDE.md` added "always write commit messages in title case" or "prefer sentence-style subjects," `git_commit.py` would start doing that with zero code changes and zero visibility into why — the same script, the same hardcoded prompt, a different result depending entirely on which directory it happened to be launched from.

So I looked for the fix. `claude --help` documents exactly this scenario:

```
--bare    Minimal mode: skip hooks, LSP, plugin sync, attribution,
          auto-memory, background prefetches, keychain reads, and
          CLAUDE.md auto-discovery. Sets CLAUDE_CODE_SIMPLE=1. Anthropic
          auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via
          --settings (OAuth and keychain are never read).
```

That second sentence is the catch. This project's `key_facts.md` says, in so many words: "No ANTHROPIC_API_KEY — Claude calls go through `claude -p` subprocess (OAuth session)." `--bare` explicitly refuses to read the OAuth session and demands an API key instead. Adding `--bare` to fix a context-loading problem would have broken the auth this script actually depends on — a fix that looks right in the docs and fails the moment you run it.

The flag that does what I actually wanted was `--safe-mode`:

```
--safe-mode   Start with all customizations (CLAUDE.md, skills, plugins,
              hooks, MCP servers, custom commands and agents, output
              styles, workflows, custom themes, keybindings, and more)
              disabled ... Auth, model selection, built-in tools, and
              permissions work normally.
```

"Auth ... works normally" is the line that matters here — it disables `CLAUDE.md` discovery without touching how the process authenticates. Verified the same way as before:

```bash
$ claude -p --safe-mode "Reply with exactly one line: either 'YES-SAW-CTX-RULES' ... or 'NO-CTX-RULES' ..."
NO-CTX-RULES
```

That's the fix I shipped, in both places this repo makes the same kind of call — `git_commit.py`'s subprocess invocation and `server.py`'s `_claude()` helper behind the `generate_commit_message` MCP tool:

```python
raw = subprocess.check_output(
    ["claude", "-p", "--safe-mode", SYSTEM + "\n\n" + diff],
    text=True,
    timeout=20,
    stderr=subprocess.PIPE,
).strip()
```

The lesson isn't "add `--safe-mode` everywhere." It's that a headless CLI call inherits ambient context the same way a shell inherits environment variables — silently, by default, scoped to wherever it's invoked from — and the flag that fixes that isn't always the first one that sounds like it should. `--bare` reads as the obvious answer to "stop auto-loading project files," and for a setup authenticated with an API key it would be. For a setup that authenticates over OAuth, it's the one flag on that list that quietly breaks the thing you're trying to fix in the first place. The only way I found that out was running both and checking, not reading the flag name and assuming.
