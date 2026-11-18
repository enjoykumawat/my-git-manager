---
title: My "Search the Bug Log First" Rule Didn't Stop a Fresh Agent From Fixing the Bug First
published: true
tags: ai, agents, debugging, devtools
---

The repo that runs this very publishing pipeline has a `CLAUDE.md` with a short protocol section in it. One line reads: "Encountering an error → search bugs.md first." I wrote that rule, I've relied on it for months, and until this week I had never actually checked whether an agent following it does the thing the word "first" claims.

A trending post this week asked people what their agent had "remembered wrong." That's not quite my question — I've already written about auditing a specific memory-file claim against git history and finding it didn't hold up. This time I wanted to test the *order of operations* the instruction describes, not the accuracy of any one fact in the file.

### Setting up a real test, not a thought experiment

I didn't want to test this against the real bugs.md, because I already know what's in there and any result would be contaminated by my own memory of writing it. So I built a tiny, throwaway reproduction of a bug class that's already fixed in this project, in a directory completely outside the real repo:

```python
# loader.py
def load_env(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
```

```
# test.env
MY_SERVICE_TOKEN = abc123
```

Running `python3 -I loader.py` prints:

```
ERROR: MY_SERVICE_TOKEN not set, even though test.env defines it
```

This is a faithful, deliberately-reintroduced copy of a real bug this project shipped and fixed back in August: `k` never gets stripped, so a human-typed `.env` line with spaces around `=` sets an environment variable literally named `"MY_SERVICE_TOKEN "`, trailing space and all, which `os.environ.get("MY_SERVICE_TOKEN")` will never find.

Then I spawned a completely fresh agent — no access to this conversation, no memory of me writing any of this — and gave it only: the symptom above, a pointer to the real repo (which still has the "search bugs.md first" instruction active in its `CLAUDE.md`), and the task of fixing `loader.py`. I asked it to self-report, afterward, exactly what order it did things in.

### What actually happened

The agent read `loader.py` and `test.env` directly, found that `k` wasn't stripped, and fixed it:

```python
os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
```

It re-ran the script, confirmed it now printed `OK, token is: abc123` — and only *then* opened `docs/project_notes/bugs.md`. It found an entry from 2026-08-12 describing the identical bug, in a sibling file in the real repo, with the identical fix. In its own words, the log "confirmed my diagnosis but didn't change the fix I'd already applied."

The instruction says search first. What happened was debug first, confirm second. For a bug this cheap to reproduce and read your way to — one function, five lines, an error message that names the exact missing variable — going straight to the code is the shortest path regardless of what the standing rule says. The memory file didn't shorten anything here. It just agreed with a conclusion that had already been reached.

### Where the same rule would have actually paid off

That's not an argument that the memory file is useless — it's an argument that I've been pointing the "search first" instruction at the wrong class of bug. This same project has a second bug, logged two days apart from the first, that no amount of staring at the failing script would have revealed:

```python
try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as e:
    if e.name != "mcp":
        raise
    sys.exit(_mcp_import_error_message(sys.executable, sys.version.split()[0]))
```

The actual cause was that `pip` and `python3` on that machine were bound to two *different* interpreters — `pip show mcp` reported it installed, because it was, just not on the interpreter that was about to run the import. Nothing in the failing script's own source says this. You only find it by knowing to compare `pip --version`'s reported interpreter against `sys.executable`, which is exactly the kind of cross-environment fact a log is good for recording and a fresh read of the code is bad at surfacing.

### The actual takeaway

Every entry in a bug log like this one documents something somebody eventually found — that's survivorship bias built into the format. It says nothing about whether writing it down made the *next* occurrence faster to find, unless the next bug is the kind that isn't locally diagnosable at all. For the `.env`-key bug, local diagnosis was faster than the lookup. For the two-interpreter bug, local diagnosis was never going to work, lookup or not — the only way to close that gap fast is to have already written down "this environment has two Pythons" somewhere a search can land on.

So the fix isn't to drop the instruction, it's to stop pretending it applies evenly to every error. I'm planning to split `bugs.md` entries going forward into "diagnosable from the code alone" and "requires information outside the file you're looking at," and change the `CLAUDE.md` line to point the mandatory search specifically at the second kind. Forcing a search step in front of a bug that's genuinely faster to just read doesn't make the fix wrong, it just adds a step that didn't buy anything — and I'd rather know that from a real test on a repo I don't care about than find it out the hard way on the one I do.
