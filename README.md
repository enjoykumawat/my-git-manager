# my-git-manager

FastMCP server that exposes your GitHub profile and DEV.to articles as MCP tools, plus a one-liner AI commit message generator.

## What's inside

| File | Purpose |
|------|---------|
| `server.py` | Developer Presence MCP server — 8 tools over GitHub + DEV.to + AI |
| `git_commit.py` | 20-line CLI: reads staged diff, outputs a Conventional Commit via `claude -p` |
| `requirements.txt` | Single dependency: `mcp[cli]` |
| `.env` | API keys (not committed) |

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env with your credentials
echo "GITHUB_TOKEN=ghp_..." >> .env
echo "DEV_TO_API=..."       >> .env

# 3a. Run with MCP Inspector (recommended for dev)
mcp dev server.py

# 3b. Or run directly
python server.py
```

No `ANTHROPIC_API_KEY` needed — Claude calls go through `claude -p` using your existing OAuth session (requires Claude Code installed).

## MCP tools

### GitHub
| Tool | Description |
|------|-------------|
| `get_github_profile` | Fetch public profile (bio, repos, followers) for `enjoykumawat` |
| `list_repos` | List public repos; sort by `updated`, `stars`, or `forks` |
| `get_repo_stats` | Stars, forks, watchers, open issues for a given repo |

### DEV.to
| Tool | Description |
|------|-------------|
| `list_articles` | List your published articles with reaction/comment/view counts |
| `create_article` | Create a new article (draft or published) |
| `update_article` | Update title, body, or publish status by article id |
| `get_article_stats` | Reactions, comments, and page views for one article |

### AI
| Tool | Description |
|------|-------------|
| `generate_commit_message` | Takes a raw git diff string, returns a Conventional Commit message |

## git_commit.py — standalone AI commit

Reads `git diff --staged` and prints a ready-to-use commit message:

```bash
git add -p
python git_commit.py        # prints: feat(auth): add JWT refresh token logic
git commit -m "$(python git_commit.py)"
```

### git alias

Add this once to skip the extra step:

```bash
git config --global alias.ai '!git commit -m "$(python d:/codes/my_git_manger/git_commit.py)"'
```

Then just:

```bash
git add -p && git ai
```

## Claude Desktop config

```json
"developer-presence": {
  "command": "python",
  "args": ["d:/codes/my_git_manger/server.py"],
  "env": {
    "GITHUB_TOKEN": "...",
    "DEV_TO_API": "..."
  }
}
```

## Requirements

- Python 3.10+
- `mcp[cli]` (`pip install mcp[cli]`)
- Claude Code (for `claude -p` OAuth — no API key required)
- GitHub personal access token with `repo` + `user` scopes
- DEV.to API key from [dev.to/settings/extensions](https://dev.to/settings/extensions)
