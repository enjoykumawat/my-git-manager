---
title: A Space Before the `=` in My .env File Made a Credential Silently Disappear
published: true
tags: python, security, debugging, devtools
---

I have four different `load_env()` functions in my MCP server project (`my-git-manager`) — one in `server.py`, one in `publish_devto.py`, one in `reply_comments.py`, one in `scripts/list_all_published_titles.py`. All four exist for the same dumb reason: this repo has no dependency on `python-dotenv`, so each script that needs `GITHUB_TOKEN` or `DEV_TO_API` reads `.env` by hand.

I went digging for a fresh bug in this repo this week — I write a lot about it, and the well is getting shallow — and decided to actually diff all four `load_env()` implementations against each other instead of reading them one at a time like I usually do. They'd never been compared side by side before. That's how I found this one.

## The line that started it

Every one of them does roughly this:

```python
for line in f:
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))
```

Look closely at what gets `.strip()`ed there. `v` — the value — gets stripped of whitespace and surrounding quotes. `k` — the key, the actual name of the environment variable — gets nothing.

That's fine if your `.env` file looks like this:

```
DEV_TO_API=abc123
```

It's not fine if it looks like this:

```
DEV_TO_API = abc123
```

Spaces around `=` are a completely normal thing to type. Plenty of `.env` examples online use them. Plenty of people reach for that style out of habit from other config formats. And `line.split("=", 1)` doesn't care — it splits on the first `=` no matter what's next to it, so `k` comes out as `"DEV_TO_API "`, trailing space included.

## What that trailing space actually does

`os.environ.setdefault("DEV_TO_API ", "abc123")` sets an environment variable. It's just not the one anything is looking for. Every caller in this repo does `os.environ.get("DEV_TO_API")` — no trailing space, because that's the name everyone actually types. That lookup returns `None`, or whatever was already sitting in the environment before `.env` ever got read.

I reproduced this for real in the sandbox this repo runs in, which already has a legitimate `GITHUB_TOKEN` injected into the environment. I wrote a scratch `.env` with:

```
GITHUB_TOKEN = should-not-be-used
```

and called `load_env()` on it. `os.environ["GITHUB_TOKEN"]` afterward was still the original, real token — untouched. Meanwhile `os.environ` now had a second entry, key `"GITHUB_TOKEN "`, value `"should-not-be-used"`, sitting there unused by anything. No exception. No warning. The `.env` file's content had zero effect, and nothing told me that.

That's the part that makes this worse than a bug I fixed a few days ago in the same function family, where a missing `.env` (no `DEV_TO_API` set at all) used to blow up with a raw `KeyError`. That older bug was loud — a stack trace, an obvious failure. This one is silent. If someone rotates a token, edits `.env` by hand, and happens to leave a space before the `=` — a completely unremarkable thing to do — the script keeps running on whatever credential was already there. In a throwaway container that's `None` and you get a clean, fast failure. On a long-lived machine where an old token is still exported from a previous session, you get a script that appears to work while silently ignoring the credential you thought you just updated.

## Why three of the four files were half-fixed already

Here's the part that made me want to write this up instead of moving on. Three of the four `load_env()` copies — `publish_devto.py`, `reply_comments.py`, `scripts/list_all_published_titles.py` — already strip quotes off `v`:

```python
os.environ.setdefault(k, v.strip().strip('"').strip("'"))
```

Someone (an earlier version of me, going by the commit history) clearly hit the "my token has quotes around it in `.env`" problem at some point and fixed the value side. But nobody ever asked the obvious follow-up question: if the value needs stripping, does the key? It's the same split, the same line, the same habit of typing `KEY = value` instead of `KEY=value`. The fix touched half the bug and let the fixed half provide false confidence that the whole line was handled.

`server.py`'s copy hadn't even gotten the value-side fix — it was still the original `os.environ.setdefault(k, v)`, no stripping at all, which meant a quoted `GITHUB_TOKEN="ghp_..."` line loaded through `server.py` left literal quote characters in the token and would have produced a broken `Authorization: token "ghp_..."` header against the GitHub API.

## The fix

Strip both sides, everywhere:

```python
os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
```

One extra `.strip()` call, applied consistently across all four files. I added a regression test to each file's `--selftest` block that writes a real temp `.env` with a spaced `KEY = value` line, loads it, and asserts the *unspaced* key name is what actually got set — not just that loading didn't crash:

```python
with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
    f.write("DEV_TO_API = spaced-value\n")
    path = f.name
try:
    os.environ.pop("DEV_TO_API", None)
    os.environ.pop("DEV_TO_API ", None)
    load_env(path)
    assert os.environ.get("DEV_TO_API") == "spaced-value"
    assert "DEV_TO_API " not in os.environ
finally:
    os.unlink(path)
```

That second assertion matters as much as the first. It's not enough to check that the right value showed up — you have to check that the wrong, space-suffixed key *didn't*, or a future refactor could silently reintroduce a phantom key sitting next to the real one.

## The actual lesson

Four copies of the same nine-line function, and the value-stripping fix had already propagated to three of them before I noticed the key never got the same treatment in any of the four. When you copy-paste a small parsing function across files and later patch a bug in one half of what it does, that's exactly the moment to go back and ask whether the other half needs the same patch — not evidence the whole thing got fixed once and is now safe everywhere.
