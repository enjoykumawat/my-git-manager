#!/usr/bin/env python3
"""Score this account's own published articles per tag, the same formula
Step 2 of the scheduled publishing task uses to rank trending dev.to posts
(reactions + 3*comments).

Why this exists: the 2026-08-11 run turned that formula back on this
account's own history and found no visible relationship between "cleared
the distinct-angle filter" and actual reader response (median reactions 0,
median comments 1 across the most recent 30 articles) — but stopped at a
one-off measurement and flagged "per-category score tracking via
list_articles, tags kept on published articles" as a concrete next step,
never built. This is that script. See docs/project_notes/issues.md
2026-08-11 and decisions.md / bugs.md for the follow-through.

Usage: python3 scripts/score_published.py
Reads DEV_TO_API from .env next to this script (or the environment).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)


def load_env():
    try:
        f = open(os.path.join(REPO_ROOT, ".env"), encoding="utf-8")
    except FileNotFoundError:
        return
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def score(article):
    """article uses this script's own normalized keys (reactions/comments),
    set by all_published() below — not dev.to's raw
    positive_reactions_count/comments_count field names."""
    return article.get("reactions", 0) + 3 * article.get("comments", 0)


def all_published(key, per_page=30):
    """Every published article's {tags, reactions, comments, title, url},
    walked page by page the same way scripts/list_all_published_titles.py
    does (bugs.md 2026-08-04: a single per_page call silently truncates)."""
    out = []
    page = 1
    while True:
        req = urllib.request.Request(
            f"https://dev.to/api/articles/me/published?per_page={per_page}&page={page}"
        )
        req.add_header("api-key", key)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            batch = json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"dev.to API error {e.code}: {e.read().decode()[:400]}") from e
        if not batch:
            break
        for a in batch:
            out.append({
                "title": a["title"],
                "url": a.get("url"),
                "tags": a.get("tag_list") or [],
                "reactions": a.get("positive_reactions_count", 0),
                "comments": a.get("comments_count", 0),
            })
        page += 1
    return out


def score_by_tag(articles):
    """{tag: {count, total_score, mean_score, articles: [...]}}, sorted by
    mean_score descending. Mean, not total — a tag used on 40 articles will
    always out-total a tag used on 4 even if every one of the 4 outperforms
    every one of the 40; the question this script exists to answer is "does
    writing about X tend to land," not "how much volume has X gotten.\""""
    by_tag = defaultdict(list)
    for a in articles:
        s = score(a)
        for t in a["tags"]:
            by_tag[t].append((s, a["title"], a["url"]))

    result = {}
    for tag, entries in by_tag.items():
        scores = [s for s, _, _ in entries]
        result[tag] = {
            "count": len(entries),
            "total_score": sum(scores),
            "mean_score": sum(scores) / len(scores),
            "top": sorted(entries, reverse=True)[0],
        }
    return dict(sorted(result.items(), key=lambda kv: kv[1]["mean_score"], reverse=True))


def main():
    load_env()
    key = os.environ.get("DEV_TO_API")
    if not key:
        sys.exit("ERROR: DEV_TO_API not set")
    articles = all_published(key)
    by_tag = score_by_tag(articles)
    print(f"{len(articles)} published articles, {len(by_tag)} distinct tags\n")
    print(f"{'tag':<15} {'n':>4} {'mean':>8} {'total':>7}  top scorer")
    for tag, d in by_tag.items():
        top_score, top_title, _ = d["top"]
        print(f"{tag:<15} {d['count']:>4} {d['mean_score']:>8.1f} {d['total_score']:>7}  "
              f"({top_score}) {top_title[:60]}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        fixture = [
            {"title": "a", "url": "u1", "tags": ["mcp", "ai"], "reactions": 10, "comments": 2},
            {"title": "b", "url": "u2", "tags": ["mcp"], "reactions": 0, "comments": 0},
            {"title": "c", "url": "u3", "tags": ["productivity"], "reactions": 5, "comments": 5},
        ]
        by_tag = score_by_tag(fixture)
        # mcp: scores [16, 0] -> mean 8.0; ai: [16] -> mean 16.0;
        # productivity: [20] -> mean 20.0
        assert by_tag["productivity"]["mean_score"] == 20.0, by_tag["productivity"]
        assert by_tag["ai"]["mean_score"] == 16.0, by_tag["ai"]
        assert by_tag["mcp"]["mean_score"] == 8.0, by_tag["mcp"]
        assert by_tag["mcp"]["count"] == 2, by_tag["mcp"]
        # sorted by mean_score descending
        assert list(by_tag.keys()) == ["productivity", "ai", "mcp"], list(by_tag.keys())
        # top scorer within a tag is the highest-scoring article, not the first
        assert by_tag["mcp"]["top"][1] == "a", by_tag["mcp"]["top"]

        # missing DEV_TO_API must exit cleanly, not KeyError — same convention
        # as publish_devto.py and list_all_published_titles.py (bugs.md 2026-08-09)
        _saved = os.environ.pop("DEV_TO_API", None)
        try:
            try:
                main()
                assert False, "missing DEV_TO_API must exit"
            except SystemExit as e:
                assert "DEV_TO_API not set" in str(e.code), e.code
        finally:
            if _saved is not None:
                os.environ["DEV_TO_API"] = _saved

        print("selftest ok")
    else:
        main()
