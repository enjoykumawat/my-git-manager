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
