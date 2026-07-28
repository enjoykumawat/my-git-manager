import os
import json
import re
import subprocess
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

GITHUB_USERNAME = "enjoykumawat"
DEV_USERNAME = "enjoy_kumawat"


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


load_env()

mcp = FastMCP("developer-presence")


def _gh(path, method="GET", data=None):
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Authorization", f"token {os.environ['GITHUB_TOKEN']}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


# dev.to blocks any User-Agent containing "urllib" (case-insensitive) — this
# string happens to avoid it, but nothing enforced that until the assert below.
# See docs/project_notes/bugs.md 2026-07-25.
_DEV_UA = "developer-presence-mcp/1.0"
assert "urllib" not in _DEV_UA.lower(), "dev.to blocks any UA containing 'urllib' — see bugs.md 2026-07-25"


def _dev(path, method="GET", data=None):
    req = urllib.request.Request(f"https://dev.to/api{path}", method=method)
    req.add_header("api-key", os.environ["DEV_TO_API"])
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", _DEV_UA)
    if data:
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


# Bare substrings ("llm", "claude", "anthropic") over-matched: any commit
# genuinely about this project's own AI-calling code (e.g. "retry llm calls
# on 429") got erased entirely. These patterns target actual attribution
# signatures instead — see docs/project_notes/bugs.md 2026-07-22 / 2026-07-26.
_STRIP_PATTERNS = [
    r"co-authored-by\s*:",
    r"generated (with|by)\s+claude",
    r"\bclaude code\b",
    r"\bwritten by (an )?(ai|llm|claude|chatgpt|copilot)\b",
    r"\bai-generated\b",
    r"🤖",
]
_STRIP_RE = re.compile("|".join(_STRIP_PATTERNS), re.IGNORECASE)

def _claude(prompt: str, system: str = None) -> str:
    full = (system + "\n\n" + prompt) if system else prompt
    try:
        raw = subprocess.check_output(
            ["claude", "-p", full], text=True, timeout=20, stderr=subprocess.PIPE
        ).strip()
    except subprocess.TimeoutExpired:
        return "ERROR: claude -p timed out after 20s"
    except subprocess.CalledProcessError as e:
        return f"ERROR: claude -p exited {e.returncode}: {(e.stderr or '').strip()[:200]}"
    except FileNotFoundError:
        return "ERROR: claude CLI not found on PATH"
    return "\n".join(
        l for l in raw.splitlines()
        if not _STRIP_RE.search(l)
    ).strip()


# ── GitHub tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def get_github_profile() -> dict:
    """Fetch public GitHub profile for enjoykumawat."""
    u = _gh(f"/users/{GITHUB_USERNAME}")
    return {
        "login": u["login"],
        "name": u.get("name"),
        "bio": u.get("bio"),
        "public_repos": u["public_repos"],
        "followers": u["followers"],
        "following": u["following"],
        "url": u["html_url"],
    }


@mcp.tool()
def list_repos(sort: str = "updated", limit: int = 10) -> list:
    """List public repos. sort: updated|stars|forks. limit: 1-100."""
    repos = _gh(f"/users/{GITHUB_USERNAME}/repos?sort={sort}&per_page={min(limit, 100)}")
    return [
        {
            "name": r["name"],
            "description": r.get("description"),
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "language": r.get("language"),
            "url": r["html_url"],
            "updated_at": r["updated_at"],
        }
        for r in repos
    ]


@mcp.tool()
def get_repo_stats(repo: str) -> dict:
    """Get stars, forks, watchers, open issues for enjoykumawat/<repo>."""
    r = _gh(f"/repos/{GITHUB_USERNAME}/{repo}")
    return {
        "name": r["name"],
        "stars": r["stargazers_count"],
        "forks": r["forks_count"],
        "watchers": r["watchers_count"],
        "open_issues": r["open_issues_count"],
        "language": r.get("language"),
        "description": r.get("description"),
    }


# ── DEV.to tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_articles(per_page: int = 10) -> list:
    """List your published DEV.to articles."""
    articles = _dev(f"/articles/me?per_page={min(per_page, 30)}")
    return [
        {
            "id": a["id"],
            "title": a["title"],
            "published": a.get("published"),
            "url": a.get("url"),
            "reactions": a.get("positive_reactions_count", 0),
            "comments": a.get("comments_count", 0),
            "page_views": a.get("page_views_count", 0),
        }
        for a in articles
    ]


@mcp.tool()
def create_article(title: str, body_markdown: str, tags: list[str] = None, published: bool = False) -> dict:
    """Create a new DEV.to article. Returns id and url."""
    payload = {"article": {"title": title, "body_markdown": body_markdown, "published": published}}
    if tags:
        payload["article"]["tags"] = tags
    result = _dev("/articles", method="POST", data=payload)
    return {"id": result["id"], "url": result.get("url"), "published": result.get("published")}


_ARTICLE_UPDATE_LOG = "logs/article_updates.jsonl"


def _log_article_update(article_id, before, fields_changed, after):
    os.makedirs(os.path.dirname(_ARTICLE_UPDATE_LOG), exist_ok=True)
    entry = {
        "article_id": article_id,
        "fields_changed": sorted(fields_changed),
        "title_before": before.get("title"),
        "title_after": after.get("title"),
        "published_before": before.get("published"),
        "published_after": after.get("published"),
        "url": after.get("url"),
    }
    with open(_ARTICLE_UPDATE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


@mcp.tool()
def update_article(article_id: int, title: str = None, body_markdown: str = None, published: bool = None) -> dict:
    """Update an existing DEV.to article by id. Fetches the article's current
    state first so the diff is known and logged before the write lands —
    a wrong or hallucinated article_id used to silently overwrite whatever
    it pointed at with no trace. See bugs.md 2026-07-27."""
    before = _dev(f"/articles/{article_id}")
    article = {}
    if title is not None:
        article["title"] = title
    if body_markdown is not None:
        article["body_markdown"] = body_markdown
    if published is not None:
        article["published"] = published
    result = _dev(f"/articles/{article_id}", method="PUT", data={"article": article})
    _log_article_update(article_id, before, article.keys(), result)
    return {
        "id": result["id"],
        "url": result.get("url"),
        "published": result.get("published"),
        "diff": {
            "title": {"before": before.get("title"), "after": result.get("title")},
            "published": {"before": before.get("published"), "after": result.get("published")},
        },
    }


@mcp.tool()
def get_article_stats(article_id: int) -> dict:
    """Get reactions, comments, and page views for a DEV.to article."""
    a = _dev(f"/articles/{article_id}")
    return {
        "id": a["id"],
        "title": a["title"],
        "reactions": a.get("positive_reactions_count", 0),
        "comments": a.get("comments_count", 0),
        "page_views": a.get("page_views_count", 0),
        "published": a.get("published"),
    }


@mcp.tool()
def generate_commit_message(diff: str) -> str:
    """Generate a Conventional Commits message from a git diff string."""
    if not diff.strip():
        return "ERROR: empty diff — nothing to generate a commit message from."
    return _claude(
        diff,
        system=(
            "You are a git commit message generator. "
            "Output ONLY the commit message — no explanation, no markdown, no quotes. "
            "Follow Conventional Commits: type(scope): subject. "
            "Types: feat, fix, docs, style, refactor, test, chore. "
            "Subject: imperative, lowercase, max 72 chars."
        ),
    )


if __name__ == "__main__":
    mcp.run()
