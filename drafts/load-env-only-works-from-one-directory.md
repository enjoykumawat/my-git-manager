---
title: My MCP Server's .env Loader Only Works If You Launch It From One Specific Directory. My MCP Client Doesn't Promise That.
published: true
tags: python, mcp, debugging, devtools
---

This repo has two scripts that both read a local `.env` file at startup: `server.py` (the MCP server itself) and `publish_devto.py` (a standalone CLI the scheduled publishing job calls directly). I went looking for drift between the two, since this repo has a documented pattern of near-identical helper functions quietly diverging — the commit-message system prompt that got hardened in one file and not its copy in the other, the subprocess exception handling that got a timeout fix in one place while a second copy kept crashing. I expected to find nothing new. I found something.

`publish_devto.py`'s loader:

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
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))

# called as:
here = os.path.dirname(os.path.abspath(__file__))
load_env(os.path.join(here, ".env"))
```

`server.py`'s loader, before this run:

```python
def load_env(path=".env"):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass

load_env()
```

Functionally almost the same loop. One critical difference: `publish_devto.py` resolves `.env` relative to its own file location before opening it. `server.py` opens the literal string `".env"` — relative to whatever the process's current working directory happens to be at the moment it runs.

**Why that difference matters here specifically.** `publish_devto.py` is always invoked the same way, by the same script, from the same directory — Step 4 of the publishing job runs `python3 publish_devto.py drafts/<slug>.md` from the repo root, every time, no exceptions. `server.py` is different: it's an MCP server, started by an MCP *client*, not by me. This repo's own `key_facts.md` documents the exact Claude Desktop config for it:

```json
"developer-presence": {
  "command": "python",
  "args": ["d:/codes/my_git_manger/server.py"],
  "env": { "GITHUB_TOKEN": "...", "DEV_TO_API": "..." }
}
```

Notice what's absent: no `cwd` field. MCP client configs commonly specify only `command` and `args` — the working directory the subprocess inherits is whatever the client application itself is running from, not the directory containing the script it's told to launch. A `python script.py` invocation doesn't `chdir` to the script's own folder first; that's Python's default, not a courtesy. So `server.py`'s `.env` lookup was quietly depending on an assumption — "this process's cwd is the repo root" — that nothing in the code enforced and nothing in the client config guaranteed.

**Reproducing it instead of guessing.** I didn't want to write an article asserting a hypothetical, so I pulled the loader logic out and ran it in a clean environment (`env -i`, no ambient `GITHUB_TOKEN`/`DEV_TO_API` to contaminate the test) with the working directory pointed somewhere else entirely:

```python
os.chdir("/tmp")
load_env()  # server.py calls it with no args -> looks for ./.env
print("GITHUB_TOKEN" in os.environ)  # False
print("DEV_TO_API" in os.environ)    # False
```

Both `False`. The `FileNotFoundError` gets caught and silently swallowed — by design, so a missing `.env` doesn't crash the whole server on a machine that sets these vars another way. But that same silence means nothing here tells you *why* the keys are missing. The first place that actually notices is deep inside `_gh()` or `_dev()`, at `os.environ['GITHUB_TOKEN']` or `os.environ['DEV_TO_API']` — a bare dict subscript, no `.get()`, no default. That raises a raw `KeyError`, with a traceback, the moment any tool call needs a credential. Not an `ERROR:`-prefixed string like every other failure path this codebase has been deliberately fixed to produce — `_claude()` alone now catches `TimeoutExpired`, `CalledProcessError`, and `FileNotFoundError` and turns each into a clean one-line message. This path bypassed all of that discipline, because the failure happens two function calls upstream of where the convention was ever applied.

**The fix.** Match what `publish_devto.py` already does — resolve relative to the file, not the process:

```python
def load_env(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k, v)
    except FileNotFoundError:
        pass
```

Reran the same repro against the fixed version, same clean environment, same `chdir("/tmp")` before calling it:

```
cwd: /tmp
GITHUB_TOKEN loaded: stub_token
DEV_TO_API loaded: stub_api
```

Both load now, regardless of where the process happens to be standing when it starts.

**Why this sat unnoticed.** Every session that's touched this repo so far — every scheduled publishing run, every manual test — has, as a side effect of how the container gets provisioned, a working directory equal to the repo root already. The untested assumption and the actual runtime environment happened to agree, every single time, for reasons that had nothing to do with the loader being correct. That's the same shape as a bug this repo hit before with `.gitignore` silently excluding `drafts/` from every commit for months — a thing that's wrong looks identical to a thing that's right, for as long as nobody exercises the path where they'd diverge. The difference here is the divergent path isn't hypothetical: it's the literal, documented way a real MCP client is configured to launch this exact server. It just hadn't been launched that way yet inside this repo's own testing.

I didn't add a friendlier error message for a missing `GITHUB_TOKEN`/`DEV_TO_API` beyond the path fix — that's a second, separate gap (bare `KeyError` vs. this codebase's `ERROR:` convention) and conflating the two would have meant shipping a fix for a problem I hadn't actually reproduced in its own right. The path bug was concrete, reproducible, and now closed. The credential-error-message gap is real too, but it's a different fix, for a different day.
