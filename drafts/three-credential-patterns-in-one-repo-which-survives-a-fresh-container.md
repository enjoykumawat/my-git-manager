---
title: Three Credential Patterns in One Repo, and Which One Survives a Fresh Container
published: true
tags: security, python, devtools, agents
---
"How do AI agents authenticate?" keeps coming up as a trending question, and most of the answers I've seen stop at "use OAuth" or "use a secrets manager" as if there's one right pattern. My own repo has three different ones in active use at the same time, for three different credentials, and I only noticed how different they are when I ran the same scheduled task in a fresh cloud sandbox that had none of my usual local setup.

This is `my-git-manager`, a small MCP server plus a couple of standalone scripts that talk to GitHub and DEV.to, and occasionally shell out to `claude -p` to generate commit messages. Three credentials, three different ways of getting them into the process that needs them.

## Pattern 1: a `.env` file next to the script

`GITHUB_TOKEN` and `DEV_TO_API` both live in a `.env` file on my local machine, gitignored, loaded by a small parser every script repeats:

```python
def load_env(path):
    try:
        f = open(path, encoding="utf-8")
    except FileNotFoundError:
        return
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
```

That `setdefault` instead of a plain assignment is the detail that matters later. It means: only set this variable from the file if nothing already put it in the environment. I added it originally just to stop a file-based value from clobbering something set deliberately for a one-off test. It turned out to also be the thing that made this whole pattern survive a completely different deployment model I hadn't designed for yet.

## Pattern 2: an ambient OAuth session, no key at all

The third credential, the one for Claude itself, isn't a credential in this repo's codebase at all. There's no `ANTHROPIC_API_KEY` anywhere, no entry in `.env`. `git_commit.py` just shells out to `claude -p` and relies on whatever session the CLI is already authenticated with on that machine:

```python
result = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=60)
```

This is the cheapest pattern to write and the easiest to get wrong in a way you won't notice until you move machines. It works great on my laptop, where I've run `claude login` once and the session just sits there. It has no story at all for "run this same script somewhere that's never seen that login" — which is exactly the gap that shows up as the "headless agent gets a 401" failure mode I'd already run into and fixed in a different part of this same repo's history. Zero credential surface area, in exchange for an implicit dependency that only reveals itself when the environment changes.

## Pattern 3: an environment variable, full stop

Then there's this scheduled publishing task itself, which I'm running from inside a cloud sandbox right now. There's no `.env` file in this container — I checked, it genuinely isn't there, `.gitignore` excludes it and nothing provisioned one on this machine. `DEV_TO_API` and `GITHUB_TOKEN` are just set directly as environment variables by whatever started the container:

```
$ ls .env
ls: cannot access '.env': No such file or directory
$ python3 -c "import os; print('DEV_TO_API' in os.environ)"
True
```

This is the pattern most write-ups about "agent credentials" actually mean when they say "use environment variables" — but it's rarely presented as one option among several that the *same script* has to tolerate. The reason `publish_devto.py` runs unmodified in both the laptop case (Pattern 1) and this sandbox (Pattern 3) is entirely that `setdefault` line from Pattern 1's loader. `load_env()` tries to open a `.env` file, fails quietly with `FileNotFoundError` if there isn't one, and moves on. The script never branches on "which environment am I in" — it just asks the environment for the variable it needs, after giving a local file a chance to have already supplied it. Whichever pattern actually provided the value, by the time `main()` calls `os.environ.get("DEV_TO_API")`, it's indistinguishable.

## What actually breaks each one

None of these three is "the secure one" in isolation — they fail differently:

- **The `.env` file** fails if it's ever accidentally committed, or if a hand-typed `KEY = value` line (spaces around the `=`) puts a trailing space in the variable name and silently never gets picked up — a real bug I hit and had to fix (`k.strip()` wasn't there originally). It's the most self-contained option and the easiest to leak by accident.
- **The ambient OAuth session** fails the moment the script runs somewhere that session hasn't touched — a fresh container, a CI runner, a second machine. There's nothing to misconfigure because there's nothing visible to configure; the failure is "it just doesn't work here" with no credential to point at.
- **The bare environment variable** fails if whatever's responsible for setting it up front — a secrets manager, a container's env block, a CI job's secret store — gets it wrong, and there's no local fallback to catch the gap. It's also the pattern most exposed to `ps`/`/proc` inspection if your threat model includes other processes on the same box.

The actual lesson, for me, wasn't "pick the right one of these three." It was that a script written to tolerate exactly one of them (as `publish_devto.py` originally was, before the `setdefault` change) breaks the moment it runs somewhere else, and a script written to ask "is this value already present, and if not, is there a local file that might supply it" survives all three without knowing which one it's in. If you're writing a credential loader for anything that might run both on your machine and in someone else's container later, test it with the `.env` file deleted before you assume it works.
