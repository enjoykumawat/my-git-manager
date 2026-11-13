---
title: "A One-Line Comma Import Is All It Took to Break My Grep-Based Dependency Scanner"
published: true
tags: python, devtools, debugging, productivity
---

A post about running three different Claude Code architecture-diagram tools against the same repo and comparing what each one got right made me want to check something closer to home. I don't own any of those tools. When I want a quick sense of what a file in my own project depends on, I do the laziest thing possible: `grep -n "^import\|^from" file.py` and eyeball it. I've never actually checked whether that's accurate. So I built the two-line regex version and the proper `ast`-based version and ran both against every Python file in my repo (`my-git-manager` — a small MCP server plus a handful of scripts for GitHub/DEV.to automation) to see where they disagreed.

They disagreed more than I expected, and the reason is dumber than I expected.

## The two scanners

The regex version is what I actually type at the command line most days, just turned into a script so I could run it in bulk:

```python
import re

def grep_imports(path):
    mods = set()
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*import\s+([\w\.]+)", line)
        if m:
            mods.add(m.group(1).split(".")[0])
        m = re.match(r"\s*from\s+([\w\.]+)\s+import", line)
        if m:
            mods.add(m.group(1).split(".")[0])
    return mods
```

The `ast` version parses the file for real instead of pattern-matching lines:

```python
import ast

def ast_imports(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src, filename=path)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mods.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    return mods
```

I ran both against the seven Python files in this repo (`server.py`, `git_commit.py`, `publish_devto.py`, `reply_comments.py`, and three scripts under `scripts/`) and diffed the two module sets per file.

## Where they diverged

Four of the seven files matched exactly. Three didn't:

```
publish_devto.py                   ast={json, os, sys, tempfile, urllib}   grep={json, tempfile}
reply_comments.py                  ast={html, json, os, re, sys, tempfile, time, urllib}   grep={html, tempfile}
scripts/list_all_published_titles.py   ast={io, json, os, sys, urllib}      grep={io, json}
```

In each case the regex version silently dropped most of the real dependencies. Not flagged as uncertain — just gone, as if `publish_devto.py` only imported `json` and `tempfile` and had no use for `os`, `sys`, or `urllib.request` at all. If I'd been using this as an actual "what does this script touch" check before changing something, I'd have had a confidently wrong answer.

The cause turned out to be one line in `publish_devto.py`:

```python
import json, os, sys, urllib.request, urllib.error
```

`re.match(r"\s*import\s+([\w\.]+)", line)` captures exactly one group. On a comma-separated import line it grabs the first name (`json`) and stops — there's nothing in the pattern that says "and keep going after a comma." The regex isn't wrong about what it was written to do; it was written assuming one module per `import` line, and this project's own stdlib-only style (every HTTP call goes through `urllib` by design — see this repo's own `decisions.md`, which rejected `requests`/`httpx` specifically to stay dependency-free) means several of these scripts open with exactly the kind of multi-name import line that assumption doesn't survive. The second `import tempfile` later in the same file, on its own line, got picked up fine by both scanners — it's only the comma form that breaks the regex.

`reply_comments.py` and `list_all_published_titles.py` have the identical pattern: one `import a, b, c` line at the top, everything after the first name invisible to grep.

## The part no import scanner catches

Fixing the regex to split on commas would close that gap, but there's a second, more interesting blind spot that neither scanner — regex or `ast` — can see at all. I also walked each file's call expressions looking for `subprocess.check_output` / `subprocess.run` targets:

```python
if name in ("check_output", "run", "Popen", "call"):
    if node.args and isinstance(node.args[0], ast.List) and node.args[0].elts:
        first = node.args[0].elts[0]
        if isinstance(first, ast.Constant):
            calls.append(first.value)
```

`git_commit.py` shells out to `git` and `claude`. `server.py` shells out to `claude`. Neither of those shows up as a Python import, obviously, because they aren't one — `claude` is an external CLI binary invoked through `subprocess.check_output(["claude", "-p", "--safe-mode", ...])`. But it's arguably the single most load-bearing dependency `git_commit.py` has: this repo's own `decisions.md` (ADR-004) explains that it shells out to `claude -p` specifically *instead of* calling the Anthropic API directly, because the OAuth session managed by Claude Code's CLI is the only auth this environment has. If that binary isn't on `PATH`, the script fails — and no import-graph tool, however correct, would ever tell you that, because "depends on an external CLI being installed" isn't a relationship either `ast` or `grep` is looking for. It's not a bug in the comparison; it's just outside the question "what does this file `import`."

## What this actually changes

I'm not switching every one-off dependency check to a real AST walk — for a single file, eyeballing is still faster than writing a script. But I stopped trusting multi-file grep-based summaries of what a batch of scripts depends on, because the exact style this project standardized on (comma-separated stdlib imports, to keep everything dependency-free per ADR-001/002) is precisely the shape that breaks a one-group regex. And if the question is "does this script depend on something external that could be missing," the answer isn't in the import graph at all — it's in the subprocess call sites, which need their own, separate pass.

The honest version of "I ran some tools against my repo and compared them" here is small: four files agreed, three didn't, and the three that didn't all failed the same way, for a reason that took about two minutes to find once I looked. That's a more useful result than it sounds — a scanner that's wrong in one consistent, explainable way is much easier to trust (or stop using) than one that's wrong unpredictably.
