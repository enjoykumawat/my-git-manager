import os
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error
from mcp.server.fastmcp import FastMCP

GITHUB_USERNAME = "enjoykumawat"
DEV_USERNAME = "enjoy_kumawat"


def load_env(path=None):
    # Resolve relative to this file, not the process's cwd — an MCP client
    # spawning this as a subprocess (command+args only, no cwd) can launch it
    # from anywhere. publish_devto.py already does this; this one didn't.
    # See docs/project_notes/bugs.md 2026-07-31.
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
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
    # No GitHub tool in this server writes anything — GITHUB_TOKEN is scoped
    # `repo, user` (full write access, see key_facts.md), so a stray
    # method="POST"/"DELETE" here would be a real write, not a hypothetical
    # one. Enforced, not just true by convention. See bugs.md 2026-07-30.
    if method != "GET":
        raise ValueError(f"_gh is read-only — got method={method!r}")
    # The old guard only checked the verb — a data payload attached to a GET
    # call was silently allowed through (didn't escalate the verb, but was
    # never rejected either). See docs/project_notes/issues.md 2026-08-01
    # comment-reply audit.
    if data is not None:
        raise ValueError("_gh is read-only — got a data payload on a GET call")
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Authorization", f"token {os.environ['GITHUB_TOKEN']}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        # Previously uncaught — a bad repo name, an expired token, or a rate
        # limit surfaced as a raw urllib traceback to the MCP client, unlike
        # every failure path _claude() has (ERROR:-prefixed strings).
        raise RuntimeError(f"GitHub API error {e.code}: {e.read().decode()[:400]}") from e
    except urllib.error.URLError as e:
        # HTTPError (above) only covers responses that got an HTTP status
        # code back. A timeout, DNS failure, or connection-refused on this
        # call's own `timeout=30` never reaches that branch — it's a plain
        # URLError, HTTPError's own superclass, and was still an uncaught
        # raw traceback even after the 2026-08-01 HTTPError fix.
        # publish_devto.py's `main()` got this exact sibling fix 2026-08-03;
        # this call site and reply_comments.py's `api()` didn't, flagged
        # live-verified-but-unfixed in issues.md 2026-08-04, still open
        # until now. See docs/project_notes/bugs.md 2026-08-08.
        raise RuntimeError(f"GitHub API network error: {e.reason}") from e


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
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        # Previously uncaught — a bad article_id, an expired key, or a 422
        # (e.g. too many tags) surfaced as a raw urllib traceback to the MCP
        # client instead of a clean error, unlike publish_devto.py's own
        # `except urllib.error.HTTPError` around the same call shape.
        raise RuntimeError(f"DEV.to API error {e.code}: {e.read().decode()[:400]}") from e
    except urllib.error.URLError as e:
        # HTTPError (above) is itself a URLError subclass and only covers
        # responses with an actual HTTP status — a timeout, DNS failure, or
        # connection-refused on this call's `timeout=30` raises the plainer
        # URLError instead, which was still an uncaught raw traceback here.
        # See docs/project_notes/bugs.md 2026-08-08.
        raise RuntimeError(f"DEV.to API network error: {e.reason}") from e


# Bare substrings ("llm", "claude", "anthropic") over-matched: any commit
# genuinely about this project's own AI-calling code (e.g. "retry llm calls
# on 429") got erased entirely. These patterns target actual attribution
# signatures instead — see docs/project_notes/bugs.md 2026-07-22 / 2026-07-26.
_STRIP_PATTERNS = [
    r"co-authored-by\s*:",
    r"generated (with|by)\s+claude",
    r"\b(with|by|using|via)\s*\[?\s*claude code\]?",
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


# GitHub's `GET /users/{username}/repos` only accepts sort=created|updated|pushed|full_name
# (docs.github.com REST API, "List repositories for a user") — stars/forks aren't a
# server-side sort on this endpoint, unlike the separate /search/repositories endpoint.
# This tool used to pass sort straight through unvalidated: sort="stars" silently fell
# back to GitHub's own default with no error, nothing telling the caller it was ignored.
_REPO_API_SORTS = {"created", "updated", "pushed", "full_name"}
_REPO_CLIENT_SORT_KEYS = {"stars": "stargazers_count", "forks": "forks_count"}


@mcp.tool()
def list_repos(sort: str = "updated", limit: int = 10) -> list:
    """List public repos. sort: updated|created|pushed|full_name|stars|forks. limit: 1-100."""
    api_sort = sort if sort in _REPO_API_SORTS else "updated"
    # The docstring claims "limit: 1-100" but nothing enforced it — a negative
    # limit wasn't rejected or clamped to empty, it fed straight into Python's
    # own negative-index slice semantics (repos[:-1] drops only the last item,
    # it doesn't mean "zero items"). A caller passing limit=-1 (e.g. from a
    # miscomputed "remaining slots" value) silently got back nearly every repo
    # instead of an error or an empty list. See docs/project_notes/bugs.md
    # 2026-08-07.
    limit = max(0, min(limit, 100))
    # stars/forks need every repo pulled before ranking, not just `limit` of them,
    # or truncation happens before the sort that was supposed to decide it.
    fetch_limit = 100 if sort in _REPO_CLIENT_SORT_KEYS else min(limit, 100) or 1
    repos = _gh(f"/users/{GITHUB_USERNAME}/repos?sort={api_sort}&per_page={fetch_limit}")
    if sort in _REPO_CLIENT_SORT_KEYS:
        repos = sorted(repos, key=lambda r: r[_REPO_CLIENT_SORT_KEYS[sort]], reverse=True)[:limit]
    else:
        repos = repos[:limit]
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
    # /articles/me (no suffix) returns ALL of the caller's articles, not just
    # published ones — Forem's docs describe it as "a list of all articles",
    # with unpublished drafts sorted first (creation order) ahead of published
    # ones (publication order). This tool's docstring promises "published
    # articles" only; the un-suffixed endpoint doesn't honor that, and with
    # per_page truncating the response, enough drafts silently crowd every
    # real published article out of the result. /articles/me/published is the
    # endpoint that actually matches what this tool claims to return. See
    # docs/project_notes/bugs.md 2026-08-07.
    articles = _dev(f"/articles/me/published?per_page={min(per_page, 30)}")
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


def _all_published_titles():
    # publish_devto.py's already_published() was fixed 2026-08-08 to walk
    # every page instead of trusting a single per_page=30 call — this
    # function was a single per_page=30 call, unfixed, checking only the
    # 30 most recent of 91+ published articles. Mirrors that fix here.
    # See docs/project_notes/bugs.md 2026-08-09.
    page = 1
    articles = []
    while True:
        batch = _dev(f"/articles/me/published?per_page=30&page={page}")
        if not batch:
            break
        articles.extend(batch)
        page += 1
    return articles


@mcp.tool()
def create_article(title: str, body_markdown: str, tags: list[str] = None, published: bool = False) -> dict:
    """Create a new DEV.to article. Returns id and url."""
    if published:
        # A POST can succeed server-side and still leave the caller with
        # nothing but a timeout/network error — the exact failure shape
        # _dev()'s own except clause was hardened for. Without this check,
        # an MCP client retrying the same tool call after an ambiguous
        # error blindly creates a second live article for one intended
        # publish. Mirrors publish_devto.py's own fix for the same gap.
        # See docs/project_notes/issues.md 2026-08-03.
        for a in _all_published_titles():
            if a.get("title") == title:
                return {"id": a["id"], "url": a.get("url"), "published": True, "already_published": True}
    payload = {"article": {"title": title, "body_markdown": body_markdown, "published": published}}
    if tags:
        # dev.to rejects more than 4 tags. publish_devto.py already truncates
        # (`[:4]`) before posting; this tool didn't, so a caller passing more
        # than 4 tags previously sent them all through unmodified.
        payload["article"]["tags"] = tags[:4]
    result = _dev("/articles", method="POST", data=payload)
    return {"id": result["id"], "url": result.get("url"), "published": result.get("published")}


# Resolved relative to this file, not the process's cwd — same reasoning as
# load_env() above (bugs.md 2026-07-31). An MCP client launches this as a
# subprocess with no guaranteed cwd, so a bare "logs/..." path scatters this
# audit log into whatever directory the process happened to start in.
_ARTICLE_UPDATE_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "article_updates.jsonl"
)


def _log_article_update(article_id, before, fields_changed, after):
    os.makedirs(os.path.dirname(_ARTICLE_UPDATE_LOG), exist_ok=True)
    entry = {"article_id": article_id, "fields_changed": sorted(fields_changed), "url": after.get("url")}
    # only log before/after for fields that were actually part of this write —
    # a fixed title/published pair told you nothing when body_markdown was the
    # field that changed. See docs/project_notes/bugs.md 2026-07-29.
    for field in fields_changed:
        entry[f"{field}_before"] = before.get(field)
        entry[f"{field}_after"] = after.get(field)
    with open(_ARTICLE_UPDATE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


@mcp.tool()
def update_article(article_id: int, title: str = None, body_markdown: str = None, published: bool = None) -> dict:
    """Update an existing DEV.to article by id. Fetches the article's current
    state first so the diff is known and logged before the write lands —
    a wrong or hallucinated article_id used to silently overwrite whatever
    it pointed at with no trace. See bugs.md 2026-07-27."""
    article = {}
    if title is not None:
        article["title"] = title
    if body_markdown is not None:
        article["body_markdown"] = body_markdown
    if published is not None:
        article["published"] = published
    if not article:
        raise ValueError(
            "update_article called with no fields to update "
            "(title/body_markdown/published all None)"
        )
    before = _dev(f"/articles/{article_id}")
    result = _dev(f"/articles/{article_id}", method="PUT", data={"article": article})
    _log_article_update(article_id, before, article.keys(), result)
    return {
        "id": result["id"],
        "url": result.get("url"),
        "published": result.get("published"),
        # only the fields actually written show up here — previously this was
        # a fixed {title, published} pair regardless of what changed, so a
        # body_markdown-only write showed an all-unchanged diff. See bugs.md
        # 2026-07-29.
        "diff": {
            field: {"before": before.get(field), "after": result.get(field)}
            for field in article
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
            "Output ONLY the commit message — one line, no explanation, no markdown, no quotes, "
            "no co-author lines, no signatures, no AI references. "
            "Follow Conventional Commits: type(scope): subject. "
            "Types: feat, fix, docs, style, refactor, test, chore. "
            "Subject: imperative, lowercase, max 72 chars."
        ),
    )


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        # Same regression cases as git_commit.py's --selftest — this file
        # carries its own copy of _STRIP_RE, not an import, so a passing
        # test here doesn't imply the other file still passes too.
        _CASES = [
            ("co-authored-by: claude <noreply@anthropic.com>", True),
            ("🤖 generated with [claude code](https://claude.ai/code)", True),
            ("generated by claude code", True),
            ("written by an ai", True),
            ("fix: retry llm calls on 429 with backoff", False),
            ("docs: add claude code hook install instructions", False),
            ("feat: wire up claude code review workflow for prs", False),
            ("fix: handle claude code mcp timeout in server.py", False),
        ]
        for line, expect_stripped in _CASES:
            got = bool(_STRIP_RE.search(line))
            assert got == expect_stripped, (line, got, expect_stripped)

        # list_repos's docstring claims "limit: 1-100" but the value was never
        # validated — a negative limit fed straight into Python's own
        # negative-index slicing (repos[:-1] means "all but the last one",
        # not "zero"). See docs/project_notes/bugs.md 2026-08-07.
        _FAKE_REPOS = [
            {"name": f"repo{i}", "description": None, "stargazers_count": i,
             "forks_count": i, "language": "Python", "html_url": f"https://x/{i}",
             "updated_at": "2026-01-01"}
            for i in range(5)
        ]
        _orig_gh = _gh
        globals()["_gh"] = lambda path: list(_FAKE_REPOS)
        try:
            assert [r["name"] for r in list_repos(limit=-1)] == [], "negative limit must return nothing, not repos[:-1]"
            assert [r["name"] for r in list_repos(limit=-3)] == []
            assert [r["name"] for r in list_repos(limit=0)] == []
            assert [r["name"] for r in list_repos(limit=999)] == [f"repo{i}" for i in range(5)]
            assert [r["name"] for r in list_repos(limit=-1, sort="stars")] == []
        finally:
            globals()["_gh"] = _orig_gh

        # create_article's duplicate-title check used a single per_page=30
        # call — a title sitting on page 2 or later of published history was
        # invisible to it, so a retry of an older title would re-POST instead
        # of detecting the existing article. See docs/project_notes/bugs.md
        # 2026-08-09.
        _PAGE1 = [{"id": i, "title": f"old-{i}", "url": f"https://x/{i}"} for i in range(30)]
        _PAGE2 = [{"id": 30, "title": "the-target-title", "url": "https://x/30"}]
        _orig_dev = _dev
        _calls = {"n": 0}

        def _fake_dev(path):
            _calls["n"] += 1
            if "page=1" in path:
                return _PAGE1
            if "page=2" in path:
                return _PAGE2
            return []

        globals()["_dev"] = _fake_dev
        try:
            found = _all_published_titles()
            assert any(a["title"] == "the-target-title" for a in found), (
                "paginated walk must reach page 2, not stop at the first 30"
            )
            assert _calls["n"] == 3, "must walk page=1, page=2, then the empty page=3"
        finally:
            globals()["_dev"] = _orig_dev

        print("selftest ok")
        raise SystemExit(0)
    mcp.run()
