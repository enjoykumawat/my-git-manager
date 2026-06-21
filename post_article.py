#!/usr/bin/env python3
"""Post article_draft.md to DEV.to as an unpublished draft."""
import os, json, urllib.request


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


load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "article_draft.md")) as f:
    body = f.read()

# strip the H1 title — dev.to uses the `title` field separately
lines = body.splitlines()
title = lines[0].lstrip("# ").strip()
body_md = "\n".join(lines[1:]).lstrip("\n")

payload = json.dumps({
    "article": {
        "title": title,
        "body_markdown": body_md,
        "tags": ["git", "python", "ai", "devtools"],
        "published": False,  # draft — review before publishing
    }
}).encode()

req = urllib.request.Request("https://dev.to/api/articles", method="POST")
req.add_header("api-key", os.environ["DEV_TO_API"])
req.add_header("Content-Type", "application/json")
req.add_header("User-Agent", "developer-presence-mcp/1.0")
req.data = payload

with urllib.request.urlopen(req) as r:
    result = json.loads(r.read())

print(f"Draft created: {result.get('url')}")
print(f"Edit at: https://dev.to/{result.get('slug', '')}/edit")
