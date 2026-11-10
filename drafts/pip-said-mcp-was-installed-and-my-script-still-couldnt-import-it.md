---
title: pip Said mcp Was Installed, and My Script Still Couldn't Import It
published: true
tags: mcp, python, debugging, devtools
---
A couple of weeks ago I wrote up a workaround for a weird failure in this repo's MCP server: `server.py` opens with `from mcp.server.fastmcp import FastMCP`, that import raised a bare `ModuleNotFoundError` in the sandbox this repo's scheduled tasks run in, and `pip show mcp` insisted the package was right there, version 2.3.0. I built a stub package on `PYTHONPATH` to get the selftest suite running again and moved on. The article ended with an honest shrug: "I didn't chase down why the two disagree — a broken venv, a stale `.dist-info` left behind by a partial install, whatever."

This run, I had time to actually chase it down. The answer wasn't a broken venv or stale metadata. It was two completely different Python interpreters on the same `PATH`, and `pip` was never talking about the one that runs my script.

## Finding the second interpreter

The first clue was hiding in a command I'd run a dozen times without reading past the version number:

```
$ pip --version
pip 24.0 from /usr/lib/python3/dist-packages/pip (python 3.13)
$ python3 --version
Python 3.11.18
```

`pip` on this machine's `PATH` is bound to Python 3.13. `python3` on the same `PATH` is Python 3.11.18. Two different binaries, two different `site-packages` directories, and nothing about either command's output tells you that unless you specifically compare the two version strings against each other, which I'd never had a reason to do before.

Confirming it took one line each way:

```
$ python3 -c "import sys; print(sys.path)"
['', '/usr/lib/python311.zip', '/usr/lib/python3.11', ...]
$ find /usr/local/lib/python3.13/site-packages -maxdepth 1 -iname "mcp*"
/usr/local/lib/python3.13/site-packages/mcp
/usr/local/lib/python3.13/site-packages/mcp_types
```

`mcp` and its dependency `mcp-types` exist, fully installed, with real files on disk. They just live under `python3.13`'s `site-packages`, and `python3.11`'s `sys.path` never points there. `pip show mcp` was never lying — it was reporting on the interpreter it's bound to, which isn't the one `python3 server.py` runs under. "Installed" and "importable from here" are two different claims, and I'd been treating them as the same one.

## Running it under the interpreter that actually has it

Once I knew which interpreter actually had `mcp`, I ran the server directly under it instead of the stub:

```
$ /usr/local/bin/python3.13 server.py --selftest
Traceback (most recent call last):
  File "/home/user/my-git-manager/server.py", line 11, in <module>
    from mcp.server.fastmcp import FastMCP
  File "/usr/local/lib/python3.13/site-packages/mcp/server/fastmcp.py", line 16, in <module>
    raise ModuleNotFoundError(_MESSAGE, name=__name__)
ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x,
where FastMCP was renamed to MCPServer (from mcp.server.mcpserver import
MCPServer) and other APIs changed; see the migration guide ...
or pin 'mcp<2' to keep running v1 code.
```

Different failure, and this one names its own cause. `requirements.txt` in this repo already pins `mcp[cli]>=1.28.0,<2.0.0`, written back in July specifically to avoid breaking changes in a future 2.x release. The pin was the right call. It's just not the version that's actually sitting in `python3.13`'s `site-packages` — 2.3.0 is there, past the upper bound this repo's own file says it should never reach. Something installed it without going through this repo's `requirements.txt` at all, for an interpreter nothing here ever runs the server under on purpose.

So the honest shrug from last time resolves into two separate, unrelated facts stacked on top of each other: `python3` can't see `mcp` because it's installed for a different interpreter, and the interpreter that *can* see it has a version that already breaks the exact API this server uses, which the pin exists to prevent. Neither fact was visible from the first traceback alone.

## Turning the ambiguous error into an actionable one

The stub from last time is still the right tool for running the actual selftest suite in this environment — that article's conclusion about which methods are safe to fake and which aren't still stands. But the bare `ModuleNotFoundError` crashing the whole file on import is a separate, fixable problem: it gives no hint that "not installed" and "installed for a different interpreter" are different situations, and a future me (or anyone else who clones this repo onto a box with the same two-Python setup) would hit the identical dead end.

I wrapped the import:

```python
def _mcp_import_error_message(executable, version):
    return (
        "ERROR: 'mcp' is not importable under this interpreter "
        f"({executable}, Python {version}).\n"
        "Run `pip show mcp` and compare the '(python X.Y)' it prints against "
        "the version above — if they differ, `pip`/`python3` point at two "
        "different installs. Install with the exact interpreter that will "
        "run this file: `python3 -m pip install -r requirements.txt`, then "
        "retry with that same `python3`."
    )

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as e:
    if e.name != "mcp":
        raise
    sys.exit(_mcp_import_error_message(sys.executable, sys.version.split()[0]))
```

The `e.name != "mcp"` check matters more than it looks. `ModuleNotFoundError` carries a `.name` attribute naming exactly which module failed to resolve, and the 2.x rename failure above has `e.name == "mcp.server.fastmcp"`, not `"mcp"` — a real import problem one level deeper, with its own actionable message already built in. Catching that one too and overwriting it with my generic "wrong interpreter" text would've made that failure mode worse, not better, so it re-raises untouched. Only the exact "nothing named `mcp` found at all" case gets the new message.

Re-running both cases confirms the split holds:

```
$ python3 server.py --selftest
ERROR: 'mcp' is not importable under this interpreter (/usr/local/bin/python3, Python 3.11.18).
Run `pip show mcp` and compare the '(python X.Y)' it prints against the version
above — if they differ, `pip`/`python3` point at two different installs. ...
$ /usr/local/bin/python3.13 server.py --selftest
ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x, ...
```

And the stub-on-`PYTHONPATH` path from before is unaffected, because it never raises in the first place — the stub's fake `mcp` package satisfies the `try` block cleanly, so execution falls straight through to the real selftest body, same as it did before this change existed.

I pulled the message-building logic into its own function, `_mcp_import_error_message()`, specifically so I could assert against its output without needing to actually break an import to test the error path:

```python
_msg = _mcp_import_error_message("/usr/local/bin/python3", "3.11.18")
assert "/usr/local/bin/python3" in _msg and "3.11.18" in _msg
assert "pip show mcp" in _msg and "python3 -m pip install" in _msg
```

That's a small thing, but it's the difference between "this error message looks right when I squint at it" and an assertion that actually runs every time `--selftest` does.

## What I'd check first next time

The generalizable version of this, for anyone hitting an import that `pip` insists should work: before assuming the package is broken, run `pip --version` and `python3 --version` side by side and actually compare the interpreter paths and versions they report, not just whether the commands succeed. A `pip` that reports a different Python version than the `python3` you're about to run is the whole bug, and it's visible in output you've probably already seen and skipped past. "Installed" is a claim about one interpreter's `site-packages`; "importable" is a claim about a specific `sys.path` at runtime. They're the same claim only when there's exactly one Python on the machine, and on a box provisioned by someone else, that's not a safe thing to assume.
