#!/usr/bin/env python3
"""Publish a markdown file to DEV.to. Stdlib only.

Usage: python publish_devto.py <file.md>

File format (frontmatter + body):
    ---
    title: My Article Title
    tags: ai, claudecode, llm, productivity
    published: true        # false (default) = draft
    ---
    ...markdown body...

Reads DEV_TO_API from .env next to this script. Prints the live URL.
"""
import json, os, sys, urllib.request, urllib.error


def parse(text):
    """Split '---' frontmatter from body. Returns (meta_dict, body_str).

    Raises ValueError if a '---' frontmatter block is opened but never
    closed with a second '---' delimiter (e.g. truncated LLM-generated
    draft output, or a hand-edited draft missing the closing fence) — the
    unguarded 3-way unpack this replaced raised a bare, unexplained
    `ValueError: not enough values to unpack` straight out of parse(), the
    only error path in this script that didn't get a clean ERROR: message.
    See docs/project_notes/bugs.md 2026-08-06.
    """
    meta = {}
    body = text
    if text.lstrip().startswith("---"):
        parts = text.lstrip().split("---", 2)
        if len(parts) < 3:
            raise ValueError(
                "frontmatter opened with '---' but never closed with a second '---' delimiter"
            )
        _, fm, body = parts
        for line in fm.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        body = body.lstrip("\n")
    # strip a leading H1 — dev.to uses the title field separately
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        meta.setdefault("title", lines[0][2:].strip())
        body = "\n".join(lines[1:]).lstrip("\n")
    return meta, body


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


def already_published(key, title):
    """URL of an already-live article with this exact title, or None.

    A POST can succeed server-side and still leave the client with nothing
    but a timeout/URLError (the ack never arrives) — the failure mode this
    script's own except clauses were hardened for. Without this check, a
    retry (this task's own "if 429, wait and retry" step, or any agent-level
    retry after an ambiguous failure) blindly re-POSTs and creates a second
    live article for one intended publish. See docs/project_notes/issues.md
    2026-08-03.

    Walks every page (not just the newest 30) so the check covers this
    account's full published history, not just its most recent page — see
    docs/project_notes/bugs.md 2026-08-08.

    A URLError here is exactly the failure class this whole check exists to
    survive — silently returning None on it would let a caller publish blind
    into the one condition where the previous attempt might already have
    landed. So it's raised, not swallowed; an HTTPError (the server actually
    responded) falls through instead, since that's a definite "verification
    unavailable" rather than an ambiguous one.
    """
    page = 1
    articles = []
    while True:
        req = urllib.request.Request(
            f"https://dev.to/api/articles/me/published?per_page=30&page={page}"
        )
        req.add_header("api-key", key)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            batch = json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError:
            return None  # server responded with an error — nothing to verify against
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"already_published() could not verify against dev.to ({e.reason}) "
                "— refusing to publish blind"
            ) from e
        if not batch:
            break
        articles.extend(batch)
        page += 1
    for a in articles:
        if a.get("title") == title:
            return a.get("url")
    return None


def main(md_path):
    here = os.path.dirname(os.path.abspath(__file__))
    load_env(os.path.join(here, ".env"))
    key = os.environ["DEV_TO_API"]

    try:
        meta, body = parse(open(md_path, encoding="utf-8").read())
    except ValueError as e:
        sys.exit(f"ERROR: {e}")
    title = meta.get("title")
    if not title:
        sys.exit("ERROR: no title (frontmatter `title:` or leading `# H1`)")
    if not body.strip():
        sys.exit("ERROR: empty body")

    tags = [t.strip() for t in meta.get("tags", "").replace(",", " ").split() if t.strip()][:4]
    published = meta.get("published", "false").lower() in ("true", "1", "yes")

    if published:
        try:
            existing = already_published(key, title)
        except RuntimeError as e:
            sys.exit(f"ERROR: {e}")
        if existing:
            print("ALREADY PUBLISHED (skipped duplicate) ->", existing)
            return {"url": existing, "already_published": True}

    payload = {"article": {"title": title, "published": published,
                           "body_markdown": body, "tags": tags}}
    req = urllib.request.Request("https://dev.to/api/articles",
                                 data=json.dumps(payload).encode(), method="POST")
    req.add_header("api-key", key)
    req.add_header("Content-Type", "application/json")
    # dev.to blocks any User-Agent containing "urllib" (case-insensitive), not
    # just the literal default — see docs/project_notes/bugs.md 2026-07-25.
    # Any string avoiding that substring works; it doesn't need to look like a browser.
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        r = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")
    except urllib.error.URLError as e:
        sys.exit(f"URLError: {e.reason}")
    print(("PUBLISHED" if published else "DRAFTED"), "->", r.get("url"))
    return r


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        m, b = parse("---\ntitle: T\ntags: a, b\npublished: true\n---\n# T\nhello")
        assert m["title"] == "T" and m["tags"] == "a, b" and m["published"] == "true", m
        assert b == "hello", repr(b)
        m2, b2 = parse("# Only H1\nbody")  # no frontmatter
        assert m2["title"] == "Only H1" and b2 == "body", (m2, b2)

        # The 2026-08-06 fix (unclosed '---' frontmatter raising a clean
        # ValueError instead of a bare unpack error) and the 2026-08-08 fix
        # (already_published() paginating + distinguishing HTTPError from
        # URLError) were both verified live with a one-off stubbed repro at
        # the time, then never turned into a permanent case here — unlike
        # every other fix in this repo's --selftest blocks. See
        # docs/project_notes/bugs.md 2026-08-09.
        try:
            parse("---\ntitle: T\nno closing fence")
            assert False, "unclosed frontmatter must raise ValueError"
        except ValueError as e:
            assert "never closed" in str(e), e

        class _FakeResp:
            def __init__(self, data):
                self._data = json.dumps(data).encode()
            def read(self):
                return self._data

        _PAGE1 = [{"title": f"old-{i}"} for i in range(30)]
        _PAGE2 = [{"title": "the-target", "url": "https://x/t"}]
        _orig_urlopen = urllib.request.urlopen

        def _fake_paginate(req, timeout=30):
            url = req.full_url
            if "page=1" in url:
                return _FakeResp(_PAGE1)
            if "page=2" in url:
                return _FakeResp(_PAGE2)
            return _FakeResp([])

        urllib.request.urlopen = _fake_paginate
        try:
            assert already_published("k", "the-target") == "https://x/t", (
                "must walk to page 2, not stop at the first 30"
            )
            assert already_published("k", "nope") is None
        finally:
            urllib.request.urlopen = _orig_urlopen

        def _fake_http_error(req, timeout=30):
            raise urllib.error.HTTPError(req.full_url, 500, "err", None, None)

        urllib.request.urlopen = _fake_http_error
        try:
            assert already_published("k", "anything") is None, (
                "HTTPError means the server answered — fall through, don't block a legit publish"
            )
        finally:
            urllib.request.urlopen = _orig_urlopen

        def _fake_url_error(req, timeout=30):
            raise urllib.error.URLError("timed out")

        urllib.request.urlopen = _fake_url_error
        try:
            try:
                already_published("k", "anything")
                assert False, "URLError is the ambiguous case — must raise, not return None"
            except RuntimeError:
                pass
        finally:
            urllib.request.urlopen = _orig_urlopen

        print("selftest ok")
    elif len(sys.argv) != 2:
        sys.exit(__doc__)
    else:
        main(sys.argv[1])
