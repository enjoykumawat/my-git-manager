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
    """Split '---' frontmatter from body. Returns (meta_dict, body_str)."""
    meta = {}
    body = text
    if text.lstrip().startswith("---"):
        _, fm, body = text.lstrip().split("---", 2)
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
    """
    req = urllib.request.Request("https://dev.to/api/articles/me/published?per_page=30")
    req.add_header("api-key", key)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        articles = json.load(urllib.request.urlopen(req, timeout=30))
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None  # can't verify — fall through to the normal publish attempt
    for a in articles:
        if a.get("title") == title:
            return a.get("url")
    return None


def main(md_path):
    here = os.path.dirname(os.path.abspath(__file__))
    load_env(os.path.join(here, ".env"))
    key = os.environ["DEV_TO_API"]

    meta, body = parse(open(md_path, encoding="utf-8").read())
    title = meta.get("title")
    if not title:
        sys.exit("ERROR: no title (frontmatter `title:` or leading `# H1`)")
    if not body.strip():
        sys.exit("ERROR: empty body")

    tags = [t.strip() for t in meta.get("tags", "").replace(",", " ").split() if t.strip()][:4]
    published = meta.get("published", "false").lower() in ("true", "1", "yes")

    if published:
        existing = already_published(key, title)
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
        print("selftest ok")
    elif len(sys.argv) != 2:
        sys.exit(__doc__)
    else:
        main(sys.argv[1])
