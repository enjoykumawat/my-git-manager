# Key Facts

> **Security:** Never store actual secrets here. Reference where they live, not the values.

---

## Credentials (location only)

- **GITHUB_TOKEN** → `d:\codes\my_git_manger\.env` (protected by `.gitignore`)
- **DEV_TO_API** → same `.env` file
- Token scopes needed: `repo`, `user` — add `delete_repo` if repo deletion via API is required, add `workflow` if you'll ever push a branch that pulls in upstream `.github/workflows/*.yml` changes (fork OSS contributions) — see `bugs.md` 2026-06-23
- **No ANTHROPIC_API_KEY** — Claude calls go through `claude -p` subprocess (OAuth session)

## Usernames

- **GitHub:** `enjoykumawat` (no underscore)
- **DEV.to:** `enjoy_kumawat` (with underscore)
- **Twitter:** `enjoykumawat`
- **Profile README repo:** `enjoykumawat/enjoykumawat`

## Project Files

| File | Purpose |
|------|---------|
| `server.py` | Developer Presence MCP server (8 tools) |
| `git_commit.py` | Standalone CLI — reads staged diff, outputs Conventional Commit via `claude -p` |
| `reply_comments.py` | Lists unreplied+undrafted DEV.to comments as JSON (`pending`) |
| `drafts/comment_replies.md` | Drafted comment replies awaiting manual paste (id_code presence = drafted) |
| `article_draft.md` | Source for DEV.to article (published 2026-06-21) — `post_article.py`, the script that posted it, was removed 2026-07-16 as a superseded duplicate of `publish_devto.py` |
| `publish_devto.py` | Publishes a `drafts/<slug>.md` file (frontmatter + body) to DEV.to. Called directly by the scheduled publishing task's Step 4 — does not go through the MCP server's `create_article` tool |
| `scripts/sync-main.sh` | Fast-forwards a detached-HEAD session back onto `origin/main`; safe to run unconditionally at the start of any git-writing session (`bugs.md` 2026-07-18) |
| `hooks/prepare-commit-msg` | Git hook: captures `git_commit.py`'s output before writing it to the commit editor, so a failed AI call leaves git's own template alone instead of wiping it (`bugs.md` 2026-07-23) |
| `scripts/check_key_facts.py` | Flags any top-level/`scripts/`/`hooks/` script not referenced anywhere in this table — added 2026-07-25 after this table itself went stale (see `issues.md` same date) |
| `scripts/list_all_published_titles.py` | Paginates `/api/articles/me/published` to print every title this account has ever published, not just the first `per_page` page — the scheduled publishing task's own Step 1 URL returns only the most recent page and Step 2 treats it as "the full list" (`bugs.md` 2026-08-04) |
| `scripts/install-hooks.sh` | Copies `hooks/*` into `.git/hooks/` for the current clone — `hooks/` alone has no effect on git; `core.hooksPath`/`.git/hooks/` are machine-local and don't survive a fresh clone or container checkout. Run once per fresh clone/container before relying on `hooks/prepare-commit-msg` (`bugs.md` 2026-07-26) |
| `requirements.txt` | Only dep: `mcp[cli]` |
| `.env` | API keys — never committed |

## MCP Server Tools

**GitHub:** `get_github_profile`, `list_repos`, `get_repo_stats`
**DEV.to:** `list_articles`, `create_article`, `update_article`, `get_article_stats`
**AI:** `generate_commit_message(diff: str)` — returns Conventional Commit via `claude -p`

## External APIs

- **GitHub REST API:** `https://api.github.com` — auth via `Authorization: token <GITHUB_TOKEN>`
- **DEV.to API:** `https://dev.to/api` — auth via `api-key` header
- **DEV.to API write limits (verified 2026-07-18):** cannot create comments (`POST /api/comments` → 404) and cannot create reactions as a normal user (`POST /api/reactions` → 401 even with valid key + Forem v1 Accept header). Comment replies must be pasted manually — hence the draft-only pipeline.
- **Comment `id_code`** = numeric comment id in base 26; comment URL is `https://dev.to/enjoy_kumawat/comment/<id_code>`

## Running the Server

```powershell
# Dev mode (with MCP Inspector)
mcp dev server.py

# Direct
python server.py
```

## Commit Conventions

- **No AI attribution** — never add `Co-Authored-By:` or any Claude/AI reference to commit messages (global rule in `~/.claude/CLAUDE.md`)
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:` etc.

## Claude Desktop Config

```json
"developer-presence": {
  "command": "python",
  "args": ["d:/codes/my_git_manger/server.py"],
  "env": { "GITHUB_TOKEN": "...", "DEV_TO_API": "..." }
}
```
