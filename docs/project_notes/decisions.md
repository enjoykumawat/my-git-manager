# Architectural Decision Records

---

### ADR-001: stdlib-only for update_profile.py (2026-06-21)

**Context:**
- Script needs to run on Windows without pip dependencies
- Only task: push a README to GitHub via REST API

**Decision:** Use Python stdlib only (`urllib.request`, `base64`, `json`) — no `requests` or third-party libs.

**Alternatives Considered:**
- `requests` → rejected (requires pip install, adds friction)
- `httpx` → rejected (same reason)

**Consequences:** Zero-dependency script; slight verbosity in HTTP call setup.

---

### ADR-002: FastMCP for MCP server (2026-06-21)

**Context:**
- Building a Developer Presence MCP server combining GitHub + DEV.to APIs
- User is already a contributor to `modelcontextprotocol/python-sdk`

**Decision:** Use `FastMCP` from `mcp.server.fastmcp` with `@mcp.tool()` decorators. HTTP calls via stdlib `urllib` (same pattern as update_profile.py).

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

### ADR-005: `drafts/` stays local-only; the log entry + live URL is the permanent record (2026-07-18)

**Context:**
- The scheduled publishing task's instructions say to commit `drafts/<slug>.md` alongside the `issues.md` log entry
- `.gitignore` has excluded `drafts/` since the repo's first commit — every run's "commit drafts + the log" has actually only ever committed the log entry (verified: `git log --all -- drafts/` is empty across 30+ published articles)

**Decision:** Keep `drafts/` gitignored. Treat the `issues.md` log entry (topic rationale, tag choices, source filenames for context) plus the live DEV.to URL as the permanent record of each article. Draft markdown files are ephemeral working files, not archived.

**Alternatives Considered:**
- Force-add drafts going forward (`git add -f`) → rejected: would silently accumulate hundreds of full-article markdown files into repo history over months for a blog-publishing side task, with no reader (the live URL already is the canonical published version)
- Un-ignore `drafts/` entirely → rejected, same reason

**Consequences:**
- ✅ Repo stays small; no duplicate copies of published content drifting from the live version
- ✅ Matches what has actually been happening for 30+ articles, now documented instead of accidental
- ❌ A draft's exact pre-publish markdown isn't recoverable after the fact — only the log's rationale and the live (post-DEV.to-formatting) article are
