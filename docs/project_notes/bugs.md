# Bug Log

## Format
Each entry: date, issue, root cause, solution, prevention.

---

### 2026-07-01 - pnpm-workspace pre-commit hook broken on Windows (misleading `ENOENT: git`)
- **Issue**: While committing a fix in `vercel/eve` (a pnpm/Turborepo workspace), `git commit` failed every time with `Error: spawnSync git ENOENT`, seemingly unable to find `git` even though it was on PATH (verified from both git-bash and PowerShell).
- **Root Cause**: The repo's `simple-git-hooks` pre-commit script (`scripts/pre-commit-fmt.mjs`) computed its working directory with `resolve(new URL("..", import.meta.url).pathname)`. On Windows, a `file://` URL's `.pathname` keeps a leading `/` before the drive letter (`/D:/codes/eve/`), so `path.resolve()` produces a bogus `D:\D:\codes\eve`. `spawnSync("git", ..., { cwd: <bogus path> })` then fails with `ENOENT`, and Node blames the command name instead of the invalid `cwd`.
- **Solution**: Manually ran `oxfmt`/`oxlint` on the changed files to replicate what the hook would have done, confirmed clean, then committed with the repo's own `SKIP_SIMPLE_GIT_HOOKS=1` env var (its documented escape hatch — not `git commit --no-verify`).
- **Prevention**: When a Node-based git hook throws `ENOENT` for a command that's clearly on PATH, suspect a bad `cwd`/path derived from `import.meta.url` on Windows (should use `fileURLToPath()`, not `.pathname`) before assuming a PATH problem. Applies to any pnpm/Turborepo-style repo with home-rolled Node hook scripts.

### 2026-06-23 - GitHub Token Missing `workflow` Scope (fork push/sync blocked)
- **Issue**: `git push` to a fork (and `gh repo sync` / `merge-upstream` API) rejected: "refusing to allow an OAuth App to create or update workflow `.github/workflows/*.yml` without `workflow` scope" — even though the local commit touched no workflow files
- **Root Cause**: The fork (`enjoykumawat/gemini-cli`) was stale; a branch based on current `upstream/main` carries upstream's newer workflow files. Bringing those into the fork requires the `workflow` OAuth scope, which the active `enjoykumawat` token lacks (has `repo, gist, read:org`). A second account `enjoyriversandlabs-cmd` has `workflow` but can't push to enjoykumawat's fork. Fresh `--fork-name` forks are also stale, so they don't help.
- **Solution**: `gh auth refresh -h github.com -s workflow` (interactive browser, run by user), then `gh repo sync` + push. Or contribute from the workflow-scoped account.
- **Prevention**: Create the GitHub token with `workflow` scope upfront for OSS-contribution work; keep forks synced so branches don't drag in upstream workflow changes. Sibling of the `delete_repo` scope gap below.

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
