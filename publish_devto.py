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
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


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

    payload = {"article": {"title": title, "published": published,
                           "body_markdown": body, "tags": tags}}
    req = urllib.request.Request("https://dev.to/api/articles",
                                 data=json.dumps(payload).encode(), method="POST")
    req.add_header("api-key", key)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")  # dev.to 403s the default urllib UA
    try:
        r = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")
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
