---
title: I Ran Every --selftest Block in This Repo and Found One Bug They'd All Miss
published: true
tags: python, debugging, devtools, ai
---

I kept seeing "Detecting Flaky Tests and Finding Their Root Causes" show up in my feed this week. I don't have flaky tests, though. I have something plainer and, it turns out, less trustworthy: six scripts in my git-manager repo that each carry a `--selftest` block instead of a real test framework. I run them by hand before I push, not in CI. I'd never actually asked how much they catch.

So I counted them, then I broke one of the things they're supposed to guard, on purpose, and watched what happened.

### What's actually in these blocks

Every script that talks to the DEV.to API in this repo (`publish_devto.py`, `reply_comments.py`, `scripts/list_all_published_titles.py`, `scripts/score_published.py`, `git_commit.py`, `server.py`) ends with an `if "--selftest" in sys.argv:` block of hand-written assertions. No pytest, no fixtures, just `assert` statements that run against fakes or small inline inputs. Counting them:

```
reply_comments.py                 : 30 asserts, 553 lines
scripts/score_published.py        : 8 asserts,  151 lines
scripts/list_all_published_titles.py : 9 asserts, 162 lines
scripts/check_key_facts.py        : 10 asserts, 277 lines
git_commit.py                     : 4 asserts,  203 lines
publish_devto.py                  : 14 asserts, 297 lines
server.py                         : 62 asserts, 1189 lines
```

`publish_devto.py`'s block is the most interesting one, because almost every assertion in it is a named regression test for a bug that actually happened and actually broke a live publish. There's one for an unclosed frontmatter fence raising a clean `ValueError` instead of a bare unpack error. One for `already_published()` walking every page of `/api/articles/me/published` instead of stopping at the first 30. One for a missing `DEV_TO_API` exiting cleanly instead of raising `KeyError`. One for `.env` lines with spaces around `=` not leaving a trailing space baked into the variable name. Running it:

```
$ python3 publish_devto.py --selftest
selftest ok
```

That's a genuinely well-maintained safety net for everything it tests.

### The bug it doesn't test for

Buried in the same file is this, right next to the two places it calls `req.add_header("User-Agent", ...)`:

```python
# dev.to blocks any User-Agent containing "urllib" (case-insensitive), not
# just the literal default — see docs/project_notes/bugs.md 2026-07-25.
# Any string avoiding that substring works; it doesn't need to look like a browser.
req.add_header("User-Agent", "Mozilla/5.0")
```

This is a documented bug that already broke publishing once. Python's default `User-Agent` is something like `Python-urllib/3.11`, and DEV.to's API rejects any request whose UA contains "urllib," case-insensitively. Without this header, every `urlopen()` call in this script — the quota check, the duplicate-title check, the publish itself — 403s.

I went looking for the assertion that protects it. There isn't one. I grepped every `--selftest` block in the repo for anything mentioning `User-Agent`, `add_header`, or the urllib substring check:

```
$ for f in reply_comments.py scripts/score_published.py \
    scripts/list_all_published_titles.py git_commit.py \
    publish_devto.py server.py; do
    awk '/--selftest/,0' "$f" | grep -i "user-agent\|add_header"
done
# (no output, across all six files)
```

Zero matches. So I did a small mutation test: copy the file, delete the two `add_header("User-Agent", ...)` lines with a regex that respects leading whitespace, and run the existing selftest against the mutated copy.

```python
import re
s = open("publish_devto.py").read()
pattern = re.compile(r'^[ \t]*req\.add_header\("User-Agent", "Mozilla/5\.0"\)\n', re.M)
s2, n = pattern.subn('', s)   # n == 2
open("mutated.py", "w").write(s2)
```

```
$ python3 mutated.py --selftest
selftest ok
```

Fourteen assertions, all green, on a copy of the script that would 403 on every real HTTP call it makes. I repeated the same mutation on `reply_comments.py` (one occurrence there) and got the identical result: `selftest ok`.

### Why the gap exists

It's not that these scripts are untested in general — `publish_devto.py`'s 14 assertions are doing real work, and they'd catch a regression in `parse()`, in pagination, in credential handling. The gap is specific: everything that got an assertion is pure logic you can exercise against a fake `urllib.request.urlopen`. The UA header isn't logic in that sense — it's a side effect on an outgoing request, checked against nothing, because nothing in the test ever inspects what headers actually left the function. The fakes stub out `urlopen` entirely, so the `Request` object's headers are invisible to the test even though they're sitting right there on `req`.

That's an easy gap to miss, because it only shows up if you ask "what does my test actually touch," not "how many asserts does it have." Sixty-two assertions in `server.py` sounds thorough. It says nothing about whether any of them look at request headers.

### What I'd actually change

Not "write more tests" as a vague goal — that's the kind of advice that produces more assertions of the same kind, missing the same class of gap. The concrete fix is one assertion per file, right next to the comment that already explains the bug:

```python
assert "urllib" not in req.get_header("User-agent", "").lower()
```

`urllib.request.Request` exposes exactly this on the object the fakes already have access to; it doesn't need a real network call. I'm not landing that in the repo in this pass — this was a measurement, not a maintenance run — but it's now logged as a concrete, reproducible gap rather than a vague feeling that the tests are "pretty good." If a future edit ever touches those two lines, right now nothing but a live 403 at 3am would tell me.
