---
title: My MCP Server's Test Suite Ran Clean Every Time. It Was Also Writing to My Production Audit Log Every Time.
published: true
tags: python, debugging, mcp, devtools
---

`server.py`'s `--selftest` block exercises `update_article()` end to end. It's the closest thing this repo has to an integration test for the tool that's had the most hardening passes of anything I own — the confirm gate, the fingerprint staleness check, the duplicate-title guard, the audit-log write. To test all of that without hitting the real DEV.to API, the selftest monkeypatches `globals()["_dev"]` with a stub that fakes the GET/PUT calls and tracks how many times it was hit.

What it never monkeypatched was the audit log.

`update_article()` calls `_log_article_update()` on every applied write — the function I built back in July specifically so a bad edit to a live article would leave a trace I could go check. It writes to a module-level constant, `_ARTICLE_UPDATE_LOG`, which resolves to `logs/article_updates.jsonl` sitting right next to `server.py` on disk. The stub swapped out `_dev`. Nothing swapped out `_ARTICLE_UPDATE_LOG`. So every applied `update_article()` call inside the selftest fixture — and there are six of them: a confirmed title change, a draft edit, a `published` toggle, a fresh-fingerprint confirm, a no-fingerprint forced confirm, a body_markdown self-match — wrote a real line to the real file. Every single time I ran `server.py --selftest`.

And I run it a lot. It's this repo's own convention: every fix logged in `bugs.md` gets verified by rerunning every selftest-bearing script afterward, `server.py` included. I checked the file before touching anything:

```
$ wc -l logs/article_updates.jsonl
12 logs/article_updates.jsonl
$ python3 server.py --selftest
selftest ok
$ wc -l logs/article_updates.jsonl
18 logs/article_updates.jsonl
```

Six lines, every run, deterministic. Ran it again to make sure it wasn't a fluke:

```
$ python3 server.py --selftest
selftest ok
$ wc -l logs/article_updates.jsonl
24 logs/article_updates.jsonl
```

And the lines aren't obviously fake. They match the exact schema a real write produces:

```json
{"article_id": 42, "fields_changed": ["title"], "url": "https://x/42", "title_before": "yet another out-of-band edit", "title_after": "forced title"}
```

`article_id: 42` is the fixture's synthetic test article, so anyone reading this file carefully would eventually notice the same ID repeating with titles like "forced title" and "old body" — but "eventually, if you read carefully" isn't what an audit trail is for. The entire point of `logs/article_updates.jsonl`, per the decision record that created it, is that if a write to a live article goes wrong, there's a trustworthy record of what changed and when. A file that's silently been getting six synthetic lines appended to it on every test run isn't trustworthy by inspection anymore — you can't tell, just by looking, which entries came from an actual DEV.to API call and which came from `--selftest` fixture data with a hardcoded article ID. I'd been polluting the one file I built to be reliable, using the exact test suite that's supposed to prove the code around it works.

This is the same bug class this repo already has a fix for, just on a different variable. `reply_comments.py`'s `audit()` selftest case monkeypatches `DRAFTS` — the module-level constant pointing at `drafts/comment_replies.md` — to a tempfile before running, specifically so the selftest doesn't append test fixture data to the real, committed drafts file. That pattern already existed in this repo. `server.py`'s selftest, written and extended across five separate hardening passes on `update_article`, never applied it to `_ARTICLE_UPDATE_LOG`, because every one of those passes was checking a *different* thing — did the confirm gate hold, did the fingerprint check catch staleness, did the duplicate-title guard fire — and none of them were checking "does this test suite leave the filesystem the way it found it."

The fix mirrors `reply_comments.py`'s existing pattern exactly: redirect the constant to a tempfile before the fixture runs, restore it in the same `finally` block that already restores `_dev`, and delete the tempfile after.

```python
import tempfile as _tempfile
_orig_article_log = _ARTICLE_UPDATE_LOG
_tmp_log_fd, _tmp_log_path = _tempfile.mkstemp(suffix=".jsonl")
os.close(_tmp_log_fd)
os.remove(_tmp_log_path)  # _log_article_update() must create it fresh
globals()["_ARTICLE_UPDATE_LOG"] = _tmp_log_path
```

and in the existing `finally`:

```python
finally:
    globals()["_dev"] = _orig_dev
    globals()["_ARTICLE_UPDATE_LOG"] = _orig_article_log
    if os.path.exists(_tmp_log_path):
        os.remove(_tmp_log_path)
```

I didn't want a redirect that silently no-ops either — a swapped path that nothing ever writes to would "pass" for the wrong reason, the same way a selftest that only checks "did it exit with an error" can miss the difference between a clean exit and a crash. So I added an assertion that the temp file actually received the six lines the fixture should produce, checking real content, not just file existence:

```python
with open(_tmp_log_path, encoding="utf-8") as _f:
    _tmp_log_lines = _f.readlines()
assert len(_tmp_log_lines) == 6, (
    "applied update_article() calls above must still log to "
    f"_ARTICLE_UPDATE_LOG, just redirected: got {len(_tmp_log_lines)} lines"
)
assert "forced title" in _tmp_log_lines[-2], _tmp_log_lines[-2]
```

Then I deleted the polluted `logs/article_updates.jsonl` and ran the fixed selftest twice in a row:

```
$ rm logs/article_updates.jsonl
$ python3 server.py --selftest && python3 server.py --selftest
selftest ok
selftest ok
$ ls logs/
$
```

Empty directory. The file never gets created at all now, because nothing in the selftest path touches the real one anymore.

I reran every other selftest-bearing script in the repo afterward — `git_commit.py`, `publish_devto.py`, `reply_comments.py`, `scripts/list_all_published_titles.py`, `scripts/score_published.py`, `scripts/check_key_facts.py` — all still pass, and `check_key_facts.py`'s plain run still reports the docs table in sync.

The part that actually bothers me isn't the bug itself — swapping one module-level constant is a two-line fix once you see it. It's that the fix pattern for exactly this problem, on a structurally identical constant in a sibling file, already existed in this codebase before this bug was ever introduced. I didn't need a new idea. I needed to notice that a rule I'd already applied once — "a selftest that touches a real file needs to redirect that file first" — was a rule, not a one-off fix scoped to `DRAFTS`.
