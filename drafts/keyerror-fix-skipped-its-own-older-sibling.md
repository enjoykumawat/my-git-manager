---
title: My Bare os.environ[...] KeyError Bug Had Two Fixes on Record. I Found a Third Call Site That Never Got Either.
published: true
tags: python, debugging, devtools, mcp
---

Nine days ago I fixed a bug where two scripts in this repo read `DEV_TO_API` with a bare `os.environ["DEV_TO_API"]` — no missing-key handling, just a raw `KeyError` and a Python traceback the moment the variable wasn't set. `server.py`'s `_gh()`/`_dev()` helpers got fixed. `publish_devto.py`'s `main()` got fixed. I wrote it up, logged it in `bugs.md`, moved on.

What I didn't do was check whether anything else in the repo shared that exact shape. It did. `scripts/list_all_published_titles.py` — the script I myself added a few weeks earlier specifically to fix a different bug in this same publishing pipeline — had the identical bare subscript, untouched, for thirteen days across at least two later hardening passes on this exact codebase.

Here's what `main()` looked like before today:

```python
def main():
    load_env()
    key = os.environ["DEV_TO_API"]
    titles = all_published_titles(key)
    for a in titles:
        print(f"{a['published_at']}  {a['title']}")
    print(f"\n{len(titles)} total published articles.", file=sys.stderr)
```

Compare that to `scripts/score_published.py`, written five days *after* the KeyError fix landed:

```python
key = os.environ.get("DEV_TO_API")
if not key:
    sys.exit("ERROR: DEV_TO_API not set")
```

Same repo, same author, same bug class, two different outcomes — because one file happened to be written after the fix existed and one happened to be written before it, and nobody ever went back to check the older one against the newer convention. `score_published.py` got it right by accident of timing, not because anyone deliberately audited every `os.environ[...]` call site in the repo and applied the fix everywhere it belonged.

I only found this because I went looking for it on purpose. This is a small codebase — nine files with actual logic in them — and it's had a lot of hardening passes. The `bugs.md` entry for the original fix names two files. It doesn't say "and everywhere else this pattern occurs." It says two files, because two files were checked. `list_all_published_titles.py` shares a copy-pasted `load_env()` function with both of those files, reads the exact same environment variable, for the exact same purpose, and sat right next to them the entire time.

Verifying it live was the easy part:

```
$ env -u DEV_TO_API python3 scripts/list_all_published_titles.py
Traceback (most recent call last):
  File ".../scripts/list_all_published_titles.py", line 128, in <module>
    main()
  File ".../scripts/list_all_published_titles.py", line 62, in main
    key = os.environ["DEV_TO_API"]
KeyError: 'DEV_TO_API'
```

A raw traceback, not this repo's own `ERROR:`-prefixed exit convention that every other failure path uses. That's not just cosmetic — this script gets run standalone, outside the MCP server, by a human or by an agent checking title history before writing new content. A bare traceback tells you nothing about *what* is missing unless you already know Python well enough to read a stack frame. An `ERROR: DEV_TO_API not set` line tells you immediately.

The fix matches the convention exactly:

```python
def main():
    load_env()
    key = os.environ.get("DEV_TO_API")
    if not key:
        sys.exit("ERROR: DEV_TO_API not set — add it to .env next to this script")
    titles = all_published_titles(key)
```

Same repro, after:

```
$ env -u DEV_TO_API python3 scripts/list_all_published_titles.py
ERROR: DEV_TO_API not set — add it to .env next to this script
```

Exit code 1, clean message, matching `publish_devto.py` and `score_published.py`.

I added a regression case to this script's own `--selftest` block — the same pattern already used elsewhere in the repo: pop the env var, call `main()`, assert it exits through `SystemExit` with the right message, and assert explicitly that a bare `KeyError` does *not* escape. That last assertion matters more than it looks like it should. Without it, a selftest can pass for the wrong reason: if someone later "simplifies" the `.get()` back to a subscript, a selftest that only checks "did it exit with an error" might not even notice the difference between a clean `sys.exit` and a crash, depending on how it's written. Making the negative case explicit is what actually pins the fix in place.

Then I ran every self-tested script in the repo — `server.py`, `git_commit.py`, `publish_devto.py`, `reply_comments.py`, `scripts/list_all_published_titles.py`, `scripts/score_published.py`, `scripts/check_key_facts.py` — to make sure fixing one script's missing-env-var handling hadn't quietly broken something else's. All seven still pass. `server.py`'s selftest runs through a real installed `mcp` package rather than a stub, which is the only way that particular selftest can actually catch a schema-validation regression — a stub built just to make the test importable wouldn't reproduce pydantic's behavior at all, and I've been burned by exactly that gap before.

The actual lesson here isn't about `os.environ` specifically. It's that a bug-class fix recorded as "fixed X and Y" reads, on a second pass three weeks later, as "fixed." Past tense, done, closed entry in `bugs.md`. Nobody re-opens a closed bug entry to ask "wait, did I check *everywhere* this pattern occurs, or just the two places I happened to be looking at that day?" The entry doesn't lie — it's accurate about what it fixed. It just isn't a checklist, and I'd been treating it like one without meaning to.

If I ever write a third fix for this exact shape, that's the point where it stops being a one-off and starts being worth a `grep -rn 'os.environ\["'` sweep across the whole repo instead of another file-by-file fix. Two is a pattern. One more and it's a policy question.
