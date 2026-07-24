#!/usr/bin/env python3
"""DEV.to comment pipeline. Stdlib only.

Usage:
    python reply_comments.py pending   # JSON of unreplied comments not yet drafted
    python reply_comments.py audit     # JSON: drafted replies never actually posted on-site

Skips comments already replied to on-site by ME, and comments whose id_code
already appears in drafts/comment_replies.md (= reply already drafted).
The dev.to API cannot post comments or reactions for normal users (verified
2026-07-18: POST /api/comments is 404, POST /api/reactions is 401), so drafted
replies are pasted manually via each comment_url.

`drafted` is not `posted`: the paste step is manual and this pipeline runs
unattended, so `audit` cross-checks every id_code in drafts/comment_replies.md
against the live on-site thread and reports which ones still have no reply
from ME — the file's growth is otherwise invisible to the pipeline itself.

Reads DEV_TO_API from .env next to this script.
"""
import json, os, re, sys, urllib.request

ME = "enjoy_kumawat"
HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(HERE, "drafts", "comment_replies.md")


def load_env():
    try:
        f = open(os.path.join(HERE, ".env"), encoding="utf-8")
    except FileNotFoundError:
        return
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def api(path):
    req = urllib.request.Request("https://dev.to/api" + path)
    req.add_header("api-key", os.environ.get("DEV_TO_API", ""))
    req.add_header("User-Agent", "Mozilla/5.0")  # dev.to 403s the default urllib UA
    return json.load(urllib.request.urlopen(req, timeout=30))


def strip_html(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


def replied_by_me(comment):
    return any(c["user"]["username"] == ME or replied_by_me(c)
               for c in comment["children"])


def pending():
    try:
        drafted = open(DRAFTS, encoding="utf-8").read()
    except FileNotFoundError:
        drafted = ""
    out = []
    for a in api(f"/articles?username={ME}&per_page=100"):
        if not a["comments_count"]:
            continue
        for c in api(f"/comments?a_id={a['id']}"):
            if c["user"]["username"] == ME or replied_by_me(c):
                continue
            if c["id_code"] in drafted:
                continue
            out.append({
                "id_code": c["id_code"],
                "author": c["user"]["username"],
                "article": a["title"],
                "comment_url": f"https://dev.to/{ME}/comment/{c['id_code']}",
                "body": strip_html(c["body_html"]),
            })
    return out


def audit():
    try:
        drafted_text = open(DRAFTS, encoding="utf-8").read()
    except FileNotFoundError:
        drafted_text = ""
    drafted_codes = set(re.findall(r"^## (\S+)", drafted_text, re.M))
    unposted = []
    for a in api(f"/articles?username={ME}&per_page=100"):
        if not a["comments_count"]:
            continue
        for c in api(f"/comments?a_id={a['id']}"):
            if c["id_code"] not in drafted_codes:
                continue
            if not any(ch["user"]["username"] == ME for ch in c["children"]):
                unposted.append({
                    "id_code": c["id_code"],
                    "article": a["title"],
                    "comment_url": f"https://dev.to/{ME}/comment/{c['id_code']}",
                })
    return {"drafted": len(drafted_codes), "never_posted": unposted}


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        me = {"user": {"username": ME}, "children": []}
        other = {"user": {"username": "x"}, "children": []}
        assert replied_by_me({"user": {"username": "x"}, "children": [{"user": {"username": "y"}, "children": [me]}]})
        assert not replied_by_me({"user": {"username": "x"}, "children": [other]})
        print("selftest ok")
    elif sys.argv[1:2] == ["pending"]:
        load_env()
        print(json.dumps(pending(), indent=2))
    elif sys.argv[1:2] == ["audit"]:
        load_env()
        print(json.dumps(audit(), indent=2))
    else:
        sys.exit(__doc__)
