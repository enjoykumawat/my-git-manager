import hashlib
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
                    # publish_devto.py / reply_comments.py / list_all_published_titles.py's
                    # load_env() all strip() both sides and strip surrounding quotes off
                    # the value (v.strip().strip('"').strip("'")) — this one only ever
                    # did os.environ.setdefault(k, v), keeping this file the one sibling
                    # that neither quote-strips the value nor whitespace-strips the key.
                    # A quoted `KEY="value"` .env line (a common convention the other
                    # three files were clearly hardened for) left the literal quote
                    # characters in GITHUB_TOKEN/DEV_TO_API here, breaking the
                    # Authorization/api-key header; `KEY = value` (spaces around `=`)
                    # put a trailing space in the environment variable NAME, so
                    # os.environ.get("GITHUB_TOKEN") never finds what was just set.
                    # See docs/project_notes/bugs.md 2026-08-12.
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
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
    # A missing/unset GITHUB_TOKEN (no .env in this container, a typo'd key
    # name, a fresh clone that never got one) used to reach straight into
    # `os.environ['GITHUB_TOKEN']` and blow up with a bare, unhandled
    # KeyError — the only failure path on this call that didn't exit through
    # the same clean RuntimeError convention the HTTPError/URLError branches
    # below already use. Flagged as an open gap in
    # docs/project_notes/issues.md 2026-08-05 ("left for another run") and
    # never fixed until now. See docs/project_notes/bugs.md 2026-08-09.
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set — add it to .env next to server.py (see key_facts.md)")
    req = urllib.request.Request(f"https://api.github.com{path}", method=method)
    req.add_header("Authorization", f"token {token}")
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
    # Same gap as _gh() above, same fix — see docs/project_notes/issues.md
    # 2026-08-05 and docs/project_notes/bugs.md 2026-08-09.
    key = os.environ.get("DEV_TO_API")
    if not key:
        raise RuntimeError("DEV_TO_API not set — add it to .env next to server.py (see key_facts.md)")
    req = urllib.request.Request(f"https://dev.to/api{path}", method=method)
    req.add_header("api-key", key)
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
    # See git_commit.py's twin copy of this list — the patterns above only
    # ever covered the "Co-Authored-By:" trailer spelling; a Signed-off-by:/
    # Reviewed-by:/Assisted-by: trailer naming an AI, or the bare
    # noreply@anthropic.com address, bypassed this filter entirely. See
    # docs/project_notes/bugs.md 2026-08-12.
    r"\b(signed-off-by|reviewed-by|acked-by|tested-by|reported-by|co-developed-by|assisted-by)\s*:\s*(claude|chatgpt|copilot|anthropic|ai|llm)\b",
    r"noreply@anthropic\.com",
]
_STRIP_RE = re.compile("|".join(_STRIP_PATTERNS), re.IGNORECASE)

_MAX_CLAUDE_ARG_BYTES = 200_000

# subprocess.check_output with no env= kwarg hands the child the FULL
# parent environment — including GITHUB_TOKEN (repo+user scope, full write)
# and DEV_TO_API, which claude -p has no use for at all; its one job here is
# turning a diff string into a commit-message string. --safe-mode (below)
# only drops CLAUDE.md/skills/plugins/hooks/MCP-server auto-discovery — it
# says nothing about ambient environment variables, a completely separate
# isolation axis. Verified live: a stub "claude" binary invoked with this
# exact call shape (no env=) could read both credentials straight out of
# its own os.environ. See docs/project_notes/bugs.md 2026-08-14.
_CLAUDE_SUBPROCESS_ENV_EXCLUDE = ("GITHUB_TOKEN", "DEV_TO_API")


def _claude_subprocess_env():
    return {k: v for k, v in os.environ.items() if k not in _CLAUDE_SUBPROCESS_ENV_EXCLUDE}


def _claude(prompt: str, system: str = None) -> str:
    full = (system + "\n\n" + prompt) if system else prompt
    # Same argv-size ceiling as git_commit.py's twin call: claude -p takes
    # the prompt as one argv element, and the OS caps total argv+environ
    # size (2 MiB via getconf ARG_MAX on this machine). A large enough diff
    # passed to generate_commit_message crashes with an uncaught OSError —
    # none of the except clauses below is OSError. See
    # docs/project_notes/bugs.md 2026-08-11.
    if len(full.encode()) > _MAX_CLAUDE_ARG_BYTES:
        return f"ERROR: prompt is {len(full.encode())} bytes, over the {_MAX_CLAUDE_ARG_BYTES}-byte claude -p argv limit."
    try:
        # Same fix as git_commit.py's twin call — --safe-mode drops
        # CLAUDE.md/skills/plugins/hooks/MCP-server auto-discovery without
        # requiring ANTHROPIC_API_KEY (--bare does, and this server has none;
        # see key_facts.md). See docs/project_notes/bugs.md 2026-08-10.
        # env=_claude_subprocess_env() below closes the separate ambient-
        # credential-leak gap — see docs/project_notes/bugs.md 2026-08-14.
        raw = subprocess.check_output(
            ["claude", "-p", "--safe-mode", full], text=True, timeout=20,
            stderr=subprocess.PIPE, env=_claude_subprocess_env(),
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
#
# This file is deliberately local-only — see decisions.md ADR-006. update_article
# is only ever invoked through Claude Desktop on the machine this server runs on;
# the scheduled publishing routine is a separate, fresh-per-container cloud
# session that calls publish_devto.py directly and never touches this tool or
# this file. Nothing in this repo's workflow ships logs/ anywhere else, so
# "the log" means "this one machine's disk," not a durable, cross-environment
# audit trail. See docs/project_notes/issues.md 2026-07-31 for the gap this
# closes: that finding was logged as open and never turned into a fix until now.
_ARTICLE_UPDATE_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "article_updates.jsonl"
)


# The 2026-08-15 confirm gate (bugs.md, this same date) stops an UNCONFIRMED
# write to a published article — it never asked whether the article the
# confirmed write is about to fire against is still the article the diff
# was actually reviewed on. A real reader comment on this exact article, the
# same day it published (mads_hansen_27b33ebfee4c9, comment 3d3hj), named
# the gap live: "the preview is computed from version A, another editor
# changes the article to B, and the agent then sends the approved write...
# the diff a person reviewed is no longer necessarily the write that
# lands." Verified: a preview call, a live edit landing in between (someone
# else, or a different tool call, changing title/body_markdown out of
# band), then the originally-approved confirm=True call still fires —
# `before` is re-fetched fresh on that call, so the tool *has* the
# information the content moved, but nothing ever compared it against what
# was shown during the preview, so the intervening edit is silently
# clobbered with no warning. This fingerprint lets a caller that captured
# the preview's `fingerprint` prove, on the later confirm=True call, that
# nothing changed underneath it in the meantime. Deliberately optional
# (`expected_fingerprint=None` skips the check) rather than mandatory: a
# caller that never previewed at all — confirm=True on the first call,
# knowingly forcing a specific title/body regardless of current live
# content — is a legitimate, different use case this shouldn't block.
def _article_fingerprint(before):
    basis = "\x1f".join(f"{f}={before.get(f)!r}" for f in ("title", "body_markdown"))
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


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
def update_article(article_id: int, title: str = None, body_markdown: str = None,
                    published: bool = None, confirm: bool = False,
                    expected_fingerprint: str = None) -> dict:
    """Update an existing DEV.to article by id. Fetches the article's current
    state first so the diff is known and logged before the write lands —
    a wrong or hallucinated article_id used to silently overwrite whatever
    it pointed at with no trace. See bugs.md 2026-07-27.

    The trace lands in logs/article_updates.jsonl next to this file, on
    whatever machine runs this MCP server — it is NOT committed to git and
    is NOT visible to the separate cloud container that publishes articles
    on a schedule. Treat it as local debugging history, not a durable or
    cross-environment audit log. See decisions.md ADR-006.

    Overwriting title/body_markdown on an article that is CURRENTLY LIVE
    (published=true) is irreversible in any meaningful sense — DEV.to keeps
    no version history, and the diff/log above only records that a change
    happened, after it already has. That write requires confirm=True; a
    call without it returns the proposed diff instead of sending the PUT,
    same shape as the real return value minus "applied". Writes that don't
    touch live content (drafts, or published/title/body all None-equivalent
    no-ops) never needed a gate and don't get one. See bugs.md 2026-08-15.

    confirm=True on its own only proves the CALLER meant to write — it says
    nothing about whether the article itself is still in the state that
    write decision was actually made about. The preview response (the one
    returned when confirm=False) includes a "fingerprint" of the article's
    current title/body_markdown; pass that back as expected_fingerprint on
    the later confirm=True call and a live edit that landed in between
    (someone else editing the article on-site, a different tool call, a
    second concurrent session) is caught and blocked instead of silently
    overwritten — the write is refused as stale and a fresh diff/fingerprint
    is returned instead. Omitting expected_fingerprint skips this check
    entirely (e.g. a caller that never previewed and is knowingly forcing a
    specific title/body regardless of current content) — this is opt-in,
    not mandatory. See bugs.md 2026-08-15 (second entry)."""
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
    live_content_write = before.get("published") and ("title" in article or "body_markdown" in article)
    fingerprint = _article_fingerprint(before)
    if live_content_write and expected_fingerprint is not None and expected_fingerprint != fingerprint:
        # The confirm=True call re-fetches `before` fresh, same as any other
        # call — it HAS the evidence the article changed since the caller's
        # last preview, it just never compared against it before this fix.
        # A mismatch here means whatever diff was reviewed and approved no
        # longer describes the live article; proceeding would silently
        # clobber whatever changed it, so this fails closed regardless of
        # confirm.
        return {
            "id": article_id,
            "url": before.get("url"),
            "applied": False,
            "reason": "stale — the live article changed since the diff you approved was "
                      "generated (expected_fingerprint doesn't match the current article); "
                      "re-preview (call again without confirm) and re-approve against the "
                      "current content before writing",
            "fingerprint": fingerprint,
            "diff": {
                field: {"before": before.get(field), "after": article.get(field)}
                for field in article
            },
        }
    if live_content_write and not confirm:
        return {
            "id": article_id,
            "url": before.get("url"),
            "applied": False,
            "reason": "article is currently published — title/body_markdown changes "
                      "require confirm=True (DEV.to has no version history to undo this)",
            "fingerprint": fingerprint,
            "diff": {
                field: {"before": before.get(field), "after": article.get(field)}
                for field in article
            },
        }
    result = _dev(f"/articles/{article_id}", method="PUT", data={"article": article})
    _log_article_update(article_id, before, article.keys(), result)
    return {
        "id": result["id"],
        "url": result.get("url"),
        "published": result.get("published"),
        "applied": True,
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
            # Trailer/signature spellings the old pattern list never covered —
            # see docs/project_notes/bugs.md 2026-08-12.
            ("Signed-off-by: Claude <noreply@anthropic.com>", True),
            ("Reviewed-by: Claude <noreply@anthropic.com>", True),
            ("Co-Developed-By: Claude", True),
            ("Assisted-by: AI", True),
            ("noreply@anthropic.com", True),
            ("docs: add reviewed-by field to PR template generator", False),
            ("feat: signed-off-by trailer support for DCO bot", False),
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

        # _gh()/_dev() used to read os.environ['GITHUB_TOKEN']/['DEV_TO_API']
        # directly — a missing credential (no .env, a typo'd key name, a
        # fresh container) surfaced as a bare, unhandled KeyError instead of
        # this file's own clean RuntimeError convention. Flagged as an open
        # gap in docs/project_notes/issues.md 2026-08-05, never fixed until
        # docs/project_notes/bugs.md 2026-08-09.
        _saved_gh_token = os.environ.pop("GITHUB_TOKEN", None)
        _saved_dev_key = os.environ.pop("DEV_TO_API", None)
        try:
            try:
                _gh("/users/x")
                assert False, "missing GITHUB_TOKEN must raise, not silently proceed"
            except KeyError:
                assert False, "must raise a clean RuntimeError, not a bare KeyError"
            except RuntimeError as e:
                assert "GITHUB_TOKEN" in str(e), e

            try:
                _dev("/articles/me/published")
                assert False, "missing DEV_TO_API must raise, not silently proceed"
            except KeyError:
                assert False, "must raise a clean RuntimeError, not a bare KeyError"
            except RuntimeError as e:
                assert "DEV_TO_API" in str(e), e
        finally:
            if _saved_gh_token is not None:
                os.environ["GITHUB_TOKEN"] = _saved_gh_token
            if _saved_dev_key is not None:
                os.environ["DEV_TO_API"] = _saved_dev_key

        # _gh()'s read-only guard (line ~42) is the only thing standing
        # between an over-scoped GITHUB_TOKEN (`repo, user` — full write,
        # see key_facts.md) and a real write landing on GitHub, since no
        # GitHub tool in this file ever passes method= or data= on purpose.
        # The guard itself had never been exercised by this selftest block —
        # every other guard added to this file got a regression case in the
        # same run it was written, this one didn't. See
        # docs/project_notes/bugs.md 2026-08-11.
        try:
            _gh("/users/x", method="POST")
            assert False, "_gh must reject a non-GET method, not silently send it"
        except ValueError as e:
            assert "read-only" in str(e), e

        try:
            _gh("/users/x", data={"a": 1})
            assert False, "_gh must reject a data payload, not silently attach it to a GET"
        except ValueError as e:
            assert "read-only" in str(e), e

        # update_article's fetch-before-write diff/log (bugs.md 2026-07-27)
        # records that a live article's content changed, after the PUT that
        # changed it already landed — nothing upstream of the PUT ever asked
        # whether that write should happen. A wrong article_id or a stale
        # cached title still overwrites a published post with zero chance to
        # back out, same as before that fix. confirm=True is now required to
        # write title/body_markdown onto an article the API reports as
        # already published; the unconfirmed call must return the proposed
        # diff instead of touching the network. See bugs.md 2026-08-15.
        _live_article = {"id": 42, "url": "https://x/42", "published": True,
                          "title": "old title", "body_markdown": "old body"}
        _put_calls = {"n": 0}

        def _fake_dev_update(path, method="GET", data=None):
            if method == "GET":
                return dict(_live_article)
            _put_calls["n"] += 1
            return {"id": 42, "url": "https://x/42", "published": True, **data["article"]}

        globals()["_dev"] = _fake_dev_update
        try:
            unconfirmed = update_article(42, title="new title")
            assert unconfirmed["applied"] is False, "unconfirmed write to a live article must not apply"
            assert _put_calls["n"] == 0, "unconfirmed write must never reach the PUT"
            assert unconfirmed["diff"]["title"] == {"before": "old title", "after": "new title"}

            confirmed = update_article(42, title="new title", confirm=True)
            assert confirmed["applied"] is True
            assert _put_calls["n"] == 1, "confirmed write must actually PUT"

            # A draft (published=False) is never gated — nothing live to lose.
            _live_article["published"] = False
            _put_calls["n"] = 0
            draft_write = update_article(42, title="draft edit")
            assert draft_write["applied"] is True, "unpublished drafts must not require confirm"
            assert _put_calls["n"] == 1

            # Toggling `published` alone (no title/body change) isn't a
            # content overwrite either — must not require confirm.
            _live_article["published"] = True
            _put_calls["n"] = 0
            publish_toggle = update_article(42, published=False)
            assert publish_toggle["applied"] is True, "a published-flag-only write must not require confirm"
            assert _put_calls["n"] == 1

            # confirm=True stops an UNCONFIRMED write — it says nothing about
            # whether the article is still what the caller actually reviewed.
            # A reader comment on this exact article the same day it
            # published (mads_hansen_27b33ebfee4c9, comment 3d3hj) named the
            # gap live: preview computed from version A, someone else edits
            # it to B, the originally-approved write still lands and
            # silently clobbers B. expected_fingerprint closes it: captured
            # from the preview, it must still match the article's CURRENT
            # state (re-fetched fresh on every call, confirmed or not) or
            # the write is refused as stale, even with confirm=True. See
            # bugs.md 2026-08-15 (second entry).
            _live_article["published"] = True
            _live_article["title"] = "reviewed title"
            _put_calls["n"] = 0
            preview = update_article(42, title="agent's proposed title")
            assert preview["applied"] is False
            stale_fp = preview["fingerprint"]

            # Someone/something else edits the article out of band, after
            # the preview but before the caller's approved confirm=True call.
            _live_article["title"] = "a manual edit that landed in between"

            stale_confirmed = update_article(
                42, title="agent's proposed title", confirm=True,
                expected_fingerprint=stale_fp,
            )
            assert stale_confirmed["applied"] is False, (
                "a confirmed write against a stale fingerprint must be refused, "
                "not silently overwrite whatever changed in between"
            )
            assert "stale" in stale_confirmed["reason"].lower(), stale_confirmed
            assert _put_calls["n"] == 0, "a stale confirm must never reach the PUT"

            # Re-preview against the now-current state, then approve with the
            # fresh fingerprint — this must go through.
            fresh_preview = update_article(42, title="agent's proposed title")
            fresh_confirmed = update_article(
                42, title="agent's proposed title", confirm=True,
                expected_fingerprint=fresh_preview["fingerprint"],
            )
            assert fresh_confirmed["applied"] is True
            assert _put_calls["n"] == 1

            # Omitting expected_fingerprint entirely must behave exactly as
            # before this fix — opt-in, not mandatory (bugs.md 2026-08-15,
            # second entry: a caller that never previewed is a legitimate,
            # different case, e.g. knowingly forcing a title regardless of
            # current content).
            _live_article["title"] = "yet another out-of-band edit"
            _put_calls["n"] = 0
            no_fingerprint_confirm = update_article(42, title="forced title", confirm=True)
            assert no_fingerprint_confirm["applied"] is True, (
                "confirm=True with no expected_fingerprint must still apply, unchanged behavior"
            )
            assert _put_calls["n"] == 1
        finally:
            globals()["_dev"] = _orig_dev

        # claude -p takes its prompt as a single argv element; a diff large
        # enough to push the combined prompt over the OS's ARG_MAX previously
        # crashed with an uncaught OSError (no except clause in _claude()
        # catches OSError). See docs/project_notes/bugs.md 2026-08-11.
        _oversized = "x" * (_MAX_CLAUDE_ARG_BYTES + 1)
        result = _claude(_oversized)
        assert result.startswith("ERROR:") and "argv limit" in result, (
            "an oversized prompt must fail through the ERROR: convention, not reach subprocess"
        )

        # load_env() was the one sibling among four (publish_devto.py,
        # reply_comments.py, scripts/list_all_published_titles.py all already
        # strip both sides) that neither quote-stripped the value nor
        # whitespace-stripped the key. A quoted `KEY="value"` line left the
        # literal quotes in the credential; a `KEY = value` line (spaces
        # around `=`) put a trailing space in the environment variable NAME,
        # so a later os.environ.get("KEY") never finds it. See
        # docs/project_notes/bugs.md 2026-08-12.
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as _f:
            _f.write('GITHUB_TOKEN="quoted-token-value"\n')
            _f.write("DEV_TO_API = spaced-key-value\n")
            _env_path = _f.name
        try:
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("DEV_TO_API", None)
            os.environ.pop("DEV_TO_API ", None)
            load_env(_env_path)
            assert os.environ.get("GITHUB_TOKEN") == "quoted-token-value", (
                "quotes around a .env value must be stripped, not left in the credential: "
                + repr(os.environ.get("GITHUB_TOKEN"))
            )
            assert os.environ.get("DEV_TO_API") == "spaced-key-value", (
                "whitespace around '=' must not leave a trailing space in the env var NAME: "
                + repr(os.environ.get("DEV_TO_API"))
            )
            assert "DEV_TO_API " not in os.environ, (
                "the key must be stripped — a 'DEV_TO_API ' (trailing space) key means "
                "the real DEV_TO_API lookup silently misses what .env just set"
            )
        finally:
            os.unlink(_env_path)
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("DEV_TO_API", None)
            os.environ.pop("DEV_TO_API ", None)

        # _claude() used to call subprocess.check_output with no env= kwarg,
        # so the claude -p child inherited the FULL parent environment —
        # including GITHUB_TOKEN/DEV_TO_API, which it has no legitimate use
        # for. --safe-mode isolates config discovery, not ambient env vars.
        # See docs/project_notes/bugs.md 2026-08-14.
        _saved_gh = os.environ.get("GITHUB_TOKEN")
        _saved_dev = os.environ.get("DEV_TO_API")
        os.environ["GITHUB_TOKEN"] = "selftest-fake-gh-token"
        os.environ["DEV_TO_API"] = "selftest-fake-dev-key"
        try:
            _child_env = _claude_subprocess_env()
            assert "GITHUB_TOKEN" not in _child_env, (
                "GITHUB_TOKEN must not be handed to the claude -p subprocess"
            )
            assert "DEV_TO_API" not in _child_env, (
                "DEV_TO_API must not be handed to the claude -p subprocess"
            )
            # Everything else claude -p needs to actually run (PATH, HOME,
            # etc.) must still be present — this isn't a blank env=None.
            assert "PATH" in _child_env, "PATH must still be inherited"
        finally:
            if _saved_gh is not None:
                os.environ["GITHUB_TOKEN"] = _saved_gh
            else:
                os.environ.pop("GITHUB_TOKEN", None)
            if _saved_dev is not None:
                os.environ["DEV_TO_API"] = _saved_dev
            else:
                os.environ.pop("DEV_TO_API", None)

        print("selftest ok")
        raise SystemExit(0)
    mcp.run()
