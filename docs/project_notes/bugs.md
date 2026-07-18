# Bug Log

## Format
Each entry: date, issue, root cause, solution, prevention.

---

### 2026-07-18 - Detached HEAD recurs on session start/resume (misdiagnosed on 2026-07-15)
- **Issue**: At least 4 separate DEV.to publishing runs (2026-07-15, 2026-07-16, 2026-07-17→18, 2026-07-18 second run) started with `git status` showing `HEAD detached from refs/heads/main`, with the previous run's own commits floating unreachable from any local branch (though already present on `origin/main` — pushes had succeeded).
- **Root Cause**: The 2026-07-15 article ("My Agent's Git Checkout Left Two Commits Floating in Nowhere") diagnosed this as concurrent agents fighting over one shared working tree's HEAD, and prescribed `git worktree` isolation as the fix. That diagnosis doesn't hold up against the recurrence pattern: this is a single session resuming across scheduled firings, not concurrent sessions. The actual mechanism is environment provisioning — the container that runs each firing is checked out to a specific commit SHA (for reproducibility) rather than the `main` ref, so a fresh or resumed session can start in detached HEAD regardless of how the previous session ended. No amount of "remember to switch back to main before ending the session" discipline prevents this, because it isn't caused by session-end behavior at all.
- **Solution**: `git checkout main && git merge --ff-only <detached-sha>` when the detached commit is a descendant of `main` (verified safe every time so far — pure additions to `issues.md`). Automated as `scripts/sync-main.sh`, safe to run unconditionally at the start of any session that will make new commits.
- **Prevention**: Run `scripts/sync-main.sh` before any git-writing work in this repo. Treat "I fixed it once and wrote it up" as a hypothesis, not a close — a fix that keeps recurring after being documented means the write-up targeted the wrong layer.

### 2026-07-18 - `drafts/` is gitignored, so "commit drafts + the log" has been a silent no-op since day one
- **Issue**: The scheduled publishing task's Step 5 instructs committing `drafts/<slug>.md` alongside the `issues.md` log entry. Checked `git log --all -- drafts/` after 30+ published articles across 10+ runs: zero commits ever touched `drafts/`. Confirmed live: `git add drafts/<file>` fails silently into a "paths are ignored by one of your .gitignore files" hint (not an error that stops a script piping into `git commit` without checking `git status` first).
- **Root Cause**: The repo's `.gitignore` (present since the first commit, `d76ecb4`) lists `drafts/` — almost certainly written for local drafting before `publish_devto.py` existed, since drafts were meant to be ephemeral scratch files. Nobody re-checked that assumption against the later instruction to commit them, and no run's log entry claiming "committed drafts + the log" was ever verified against what `git status` actually staged.
- **Solution**: Made it a deliberate decision instead of an accidental gap — see `decisions.md` ADR-005: drafts stay local/ephemeral; the permanent record is the `issues.md` log entry (with source filenames for context) plus the live DEV.to URL, not the source markdown.
- **Prevention**: When an instruction says "commit X," check `git status`/`git show --stat` on the resulting commit before logging success — a `git add` that silently no-ops on a gitignored path leaves no error to catch downstream.

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
