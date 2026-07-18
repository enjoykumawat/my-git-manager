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
| `update_profile.py` | Pushes `template.md` to GitHub profile README |
| `template.md` | Source of truth for GitHub profile README |
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
