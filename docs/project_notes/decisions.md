# Architectural Decision Records

---

### ADR-001: stdlib-only for update_profile.py (2026-06-21) — **update_profile.py never existed in this repo, see correction below (2026-08-05)**

**Context:**
- Script needs to run on Windows without pip dependencies
- Only task: push a README to GitHub via REST API

**Decision:** Use Python stdlib only (`urllib.request`, `base64`, `json`) — no `requests` or third-party libs.

**Alternatives Considered:**
- `requests` → rejected (requires pip install, adds friction)
- `httpx` → rejected (same reason)

**Consequences:** Zero-dependency script; slight verbosity in HTTP call setup.

**Correction (2026-08-05):** `bugs.md` 2026-07-28 already proved `update_profile.py` and `template.md` were never committed to this repo in any commit (`git rev-list --all --count` is non-trivial, non-shallow, `git log --all --diff-filter=A -- update_profile.py template.md` is empty) and removed both from `key_facts.md`'s Project Files table. This ADR was never updated to match — it kept reasoning about a script's design as if it were a real, applicable part of the codebase, and `scripts/check_key_facts.py`'s phantom-file check (built the same day, for the same bug) only ever scanned `key_facts.md`, not `decisions.md`. The underlying decision this ADR actually documents (stdlib-only HTTP calls, no `requests`/`httpx`) is real and still in force — it lives on in `publish_devto.py`, `reply_comments.py`, and `server.py`'s shared `urllib`-only pattern (see ADR-002) — but its title and Context/Decision text should be read as describing that pattern in the abstract, not a script this repo ever shipped. `scripts/check_key_facts.py` now also scans `decisions.md` for phantom file references.

---

### ADR-002: FastMCP for MCP server (2026-06-21)

**Context:**
- Building a Developer Presence MCP server combining GitHub + DEV.to APIs
- User is already a contributor to `modelcontextprotocol/python-sdk`

**Decision:** Use `FastMCP` from `mcp.server.fastmcp` with `@mcp.tool()` decorators. HTTP calls via stdlib `urllib` (the same stdlib-only HTTP pattern as ADR-001 — see ADR-001's 2026-08-05 correction for what that pattern is actually grounded in; the phrase "same pattern as" here should not be read as pointing at a real, separately-shipped script).

**Alternatives Considered:**
- Low-level MCP server → rejected (unnecessary complexity for this use case)
- `requests` for HTTP → rejected (already have urllib pattern established)

**Consequences:** `mcp[cli]` is the only dependency. Server is runnable via `python server.py` or `mcp dev server.py`.

---

### ADR-003: Hardcode GitHub username, don't read from .env (2026-06-21)

**Context:**
- `.env` `GITHUB_USERNAME=enjoy_kumawat` is the DEV.to username (with underscore)
- GitHub username is `enjoykumawat` (no underscore) — reading from `.env` caused 404s

**Decision:** Hardcode `GITHUB_USERNAME = 'enjoykumawat'` and `DEV_USERNAME = 'enjoy_kumawat'` as constants in each script.

**Consequences:** Scripts are explicit about which platform's username they use. No accidental cross-platform key reuse.

---

### ADR-004: Use `claude -p` subprocess instead of direct Anthropic HTTP API (2026-06-21)

**Context:**
- User runs Claude via Claude Code OAuth — no `ANTHROPIC_API_KEY` available
- Original `_claude()` called `https://api.anthropic.com/v1/messages` with `x-api-key` header, which requires a paid API key

**Decision:** Shell out to `claude -p "prompt"` via `subprocess.check_output`. The Claude CLI uses the existing OAuth session automatically — no credential management needed.

**Alternatives Considered:**
- Read OAuth token from `~/.claude/session-env/` and use `Authorization: Bearer` + `anthropic-beta: oauth-2025-04-20` → rejected: file access was denied; fragile
- Keep direct HTTP and document that users need an API key → rejected: user explicitly does not have one

**Consequences:**
- ✅ Works with Claude Code OAuth (no API key needed)
- ✅ Zero new dependencies
- ✅ Model version managed by Claude CLI defaults
- ❌ Requires `claude` CLI to be in PATH
- ❌ Slightly slower (subprocess spawn per call)

---

### ADR-005: `drafts/` stays local-only; the log entry + live URL is the permanent record (2026-07-18) — **superseded in practice, see correction below (2026-08-04)**

**Context:**
- The scheduled publishing task's instructions say to commit `drafts/<slug>.md` alongside the `issues.md` log entry
- `.gitignore` has excluded `drafts/` since the repo's first commit — every run's "commit drafts + the log" has actually only ever committed the log entry (verified: `git log --all -- drafts/` is empty across 30+ published articles)

**Decision:** Keep `drafts/` gitignored. Treat the `issues.md` log entry (topic rationale, tag choices, source filenames for context) plus the live DEV.to URL as the permanent record of each article. Draft markdown files are ephemeral working files, not archived.

**Exception (2026-07-18):** `drafts/comment_replies.md` is un-ignored (`!drafts/comment_replies.md`). Unlike article drafts it is not a duplicate of published content — it is shared working state between the local machine and the comment-reply-drafter cloud routine (pending replies to paste + the drafted-state marker the `pending` command keys off), so it must live in the repo.

**Alternatives Considered:**
- Force-add drafts going forward (`git add -f`) → rejected: would silently accumulate hundreds of full-article markdown files into repo history over months for a blog-publishing side task, with no reader (the live URL already is the canonical published version)
- Un-ignore `drafts/` entirely → rejected, same reason

**Consequences (as originally believed):**
- ✅ Repo stays small; no duplicate copies of published content drifting from the live version
- ✅ Matches what has actually been happening for 30+ articles, now documented instead of accidental
- ❌ A draft's exact pre-publish markdown isn't recoverable after the fact — only the log's rationale and the live (post-DEV.to-formatting) article are

**Correction (2026-08-04):** This ADR's stated exception was never actually what `.gitignore` implements. The real pattern is:
```
drafts/*
!drafts/*.md
```
`!drafts/*.md` un-ignores *every* `.md` file in `drafts/`, not just `comment_replies.md` — the "exception" section above describes an intent the pattern never encoded. `git add -A` on any new `drafts/<slug>.md` article draft stages it cleanly; nothing rejects it. This wasn't caught for weeks because "commit drafts + the log" kept "succeeding" either way — silently no-op if a stricter pattern had actually been in place, silently including drafts under the pattern that's actually there — and no run's log entry was ever checked against `git show --stat` on the resulting commit. Checked recent history: starting around the 2026-08-01 run (commit `c933c0a` onward), article drafts *have* been getting committed alongside each fix, matching what the pattern actually does, not what this ADR describes. Updated decision: stop treating this as accidental. `drafts/*.md` (article drafts and `comment_replies.md` alike) are tracked and committed going forward — this matches both the actual `.gitignore` pattern and the actual practice of the last several days of runs, and gives a draft's exact pre-publish markdown a recoverable history the original ADR assumed was permanently lost. See `bugs.md` 2026-08-04.

---

### ADR-006: `logs/article_updates.jsonl` stays local-only and undocumented-as-durable, on purpose (2026-08-14)

**Context:**
- `update_article`'s 2026-07-27 fix added a JSONL audit log specifically so a bad overwrite would leave a trace (bugs.md 2026-07-27)
- The 2026-07-31 run audited whether that trace actually persists anywhere and found it doesn't: `git log --all --oneline -- 'logs/*'` was empty across 50+ commits, `logs/` wasn't even in `.gitignore`, and the directory didn't exist on disk between runs. Root cause: `update_article` is an MCP tool invoked only through Claude Desktop on the user's own machine; the scheduled publishing routine that does the actual scheduled work runs in a separate, fresh-per-session cloud container that calls `publish_devto.py` directly and never touches this tool. Two machines, one of which never runs long enough to accumulate a log at all.
- That run explicitly named two fix shapes — a shared log location both environments could read, or narrowing the tool's own claim to match what it actually delivers — and shipped neither, logging it as an open gap instead (issues.md 2026-07-31).
- Two weeks later (2026-08-14) the gap was still open: no commit anywhere in this repo's history touches `logs/`, and the docstring still read "so a bad write would leave a trace" with no qualification.

**Decision:** Narrow the claim instead of building shared infrastructure for it. `update_article`'s docstring and the code comment above `_ARTICLE_UPDATE_LOG` now say plainly that this is a local-only debug trail on whatever machine runs the MCP server, not a durable or cross-environment audit log. `.gitignore` now lists `logs/` explicitly, replacing the previous accidental omission (it was never committed, but only because no run's `git add` ever happened to catch it — not because the repo said so).

**Alternatives Considered:**
- Shared log location both environments read (e.g. commit the JSONL, or ship it to a location the cloud container can also reach) → rejected: `update_article` writes fire from a single-user interactive session; committing a growing per-write log has the same downside ADR-005 already rejected for `drafts/` before its own correction (unbounded history growth for a file with effectively no reader), and the two environments (a user's own machine vs. a fresh disposable container) don't share a filesystem or a natural sync point to build one around without inventing infrastructure this project doesn't otherwise need.
- Leave the docstring as-is and just add the `.gitignore` line → rejected: the actual failure mode was never "a file that should be tracked isn't" — it's a tool telling its caller "this write is traceable" when that's only true for one of the two ways this repo's articles get written to.

**Consequences:**
- ✅ The tool's own claim now matches what it actually delivers — closes a gap that had been described twice (2026-07-31, and again implicitly by every run since) without a code change
- ✅ `logs/` being untracked is now a documented decision, not a 50-commit-long accident
- ❌ `update_article` writes made through Claude Desktop still have no record visible to the cloud publishing routine, or to anyone auditing this repo's git history alone — that asymmetry is now honestly scoped, not fixed at the infrastructure level
- ❌ If `update_article` usage ever grows beyond occasional manual edits, this decision should be revisited — the "effectively no reader" premise is what makes local-only acceptable, same as ADR-005's original (later corrected) reasoning for `drafts/`
