# Bug Log

## Format
Each entry: date, issue, root cause, solution, prevention.

---

### 2026-06-21 - GitHub Token Missing `delete_repo` Scope
- **Issue**: `403 Must have admin rights to Repository` when trying to delete a repo via API
- **Root Cause**: GitHub personal access token lacked `delete_repo` OAuth scope
- **Solution**: Delete repos manually via GitHub Settings UI → Danger Zone
- **Prevention**: When creating tokens, include `delete_repo` scope if repo management is needed

### 2026-06-21 - ANTHROPIC_API_KEY Not Available with Claude Code OAuth
- **Issue**: `_claude()` in `server.py` and `git_commit.py` used `urllib` + `x-api-key: ANTHROPIC_API_KEY` — fails for users running Claude via OAuth (Claude Code subscription), not a raw API key
- **Root Cause**: Direct API calls require `ANTHROPIC_API_KEY`; OAuth users don't have one
- **Solution**: Replace the urllib block with `subprocess.check_output(["claude", "-p", prompt], text=True)` — the `claude` CLI uses the existing OAuth session automatically
- **Prevention**: Any new AI call in this project should use `claude -p` subprocess, not direct HTTP

### 2026-06-21 - Username Underscore Mismatch
- **Issue**: API calls to GitHub failed when reading `GITHUB_USERNAME` from `.env` (value: `enjoy_kumawat`)
- **Root Cause**: `.env` stores DEV.to username (`enjoy_kumawat`), GitHub username has no underscore (`enjoykumawat`)
- **Solution**: Hardcode `GITHUB_USERNAME = 'enjoykumawat'` in Python scripts rather than reading from `.env`
- **Prevention**: Keep `.env` key names explicit — `DEV_TO_USERNAME` vs `GITHUB_USERNAME` to avoid ambiguity
