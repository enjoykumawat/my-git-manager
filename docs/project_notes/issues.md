# Work Log

---

### 2026-07-04 - DEV.to: 3 articles published (batch)
- **Status**: Completed (published live)
- **Description**: Ranked trending dev.to ai/llm/mcp/claudecode posts by reactions + 3×comments. Picked 3 distinct, first-hand topics not overlapping the prior 11 posts:
  - "faked tool result" trend → grounded in the real `vercel/eve` #412 fix (terminal `MODEL_CALL_FAILED` swallowed as silent success, missing `config.mode === "task"` check on the terminal branch).
  - "headless agent 401" trend → grounded in the real `ANTHROPIC_API_KEY`-vs-OAuth bug from `bugs.md` (raw API key assumed, actual auth is `claude -p` OAuth session).
  - "vector RAG weak for coding agents" trend → grounded in this repo's own `context-mode` tool, which indexes into an FTS5 knowledge base, not a vector DB.
  - dev.to rate-limited the 3rd POST (429 "try again in 30s"), same throttle as the 2026-06-29 batch; retried after cooldown.
  - Tags per article: claudecode/ai/agents/debugging; claudecode/ai/devops/debugging; mcp/ai/llm/python. Sources: `drafts/agent-faked-tool-result.md`, `drafts/headless-agent-401.md`, `drafts/fts5-not-vectors.md`.
  - https://dev.to/enjoy_kumawat/my-agent-said-the-tool-call-succeeded-it-had-404d-3c07
  - https://dev.to/enjoy_kumawat/the-token-was-valid-my-headless-agent-401d-anyway-3bgl
  - https://dev.to/enjoy_kumawat/i-ditched-vector-search-for-my-coding-agents-memory-fts5-won-22g2

### 2026-07-03 - DEV.to article: MCP tool schema bloat
- **Status**: Completed (published live)
- **Description**: Ranked trending dev.to mcp/ai/llm/claudecode posts by reactions + 3×comments. Picked "Your MCP servers are burning 50k+ tokens before you type a word" (mcp tag, live discussion) — distinct from the earlier "56KB context flooding" piece (that was runtime output bloat; this is upfront tool-schema bloat). Grounded first-hand in this session's own deferred-tool-loading pattern (ToolSearch: ~80 MCP tools listed by name only, full schema fetched on demand). Tags: mcp, ai, claudecode, productivity. Source: `drafts/mcp-tool-schema-bloat.md`.
- **URL**: https://dev.to/enjoy_kumawat/your-mcp-servers-are-burning-tokens-before-you-type-a-word-3076

### 2026-07-01 - OSS Contribution to vercel/eve — issue #412

- **Status**: Completed (PR opened, awaiting review)
- **Description**: Forked + cloned `vercel/eve` (already set up: fork `enjoykumawat/eve`, local clone `D:\codes\eve`). Root-caused #412 ("subagent MODEL_CALL_FAILED gets swallowed") via systematic-debugging: `packages/eve/src/harness/tool-loop.ts`'s `classification === "terminal"` branch returned `{ done: true, output: "" }` unconditionally, never checking `config.mode`, unlike the non-terminal branch right below it which already special-cased `config.mode === "task"` to set `isError: true`. Result: a subagent whose model call failed terminally (401/403/404/invalid API key/unresolvable model id) rolled up into the parent orchestrator via `workflow-entry.ts`'s `finalizeDone` as a **successful** empty-output `subagent-result` — matches the issue's exact repro (404 from an unresolvable OpenRouter model slug). Fix: applied the same `config.mode === "task"` check to the terminal branch. Added a regression test in `tool-loop.test.ts` (confirmed red before fix, green after). Full `packages/eve` unit suite run before/after — no new failures (pre-existing Windows path-separator failures in unrelated CLI/nitro-host tests present on `main` too). Added a changeset.
- **URL**: https://github.com/vercel/eve/pull/454
- **Notes**: No GPG/SSH signing key configured in this environment — vercel/eve requires verified signatures on protected branches (CONTRIBUTING.md); committed with DCO sign-off (`-s`) only, flagged in the PR for re-signing before merge. Also hit and worked around (didn't fix) an unrelated pre-existing Windows bug in the repo's own `scripts/pre-commit-fmt.mjs`: computes `REPO_ROOT` via `new URL("..", import.meta.url).pathname`, which keeps a leading `/` before the drive letter on Windows (`/D:/codes/eve/`), producing a bogus `cwd` for `spawnSync` that fails with a misleading `ENOENT: git` error on every commit. Worked around via the script's own `SKIP_SIMPLE_GIT_HOOKS=1` escape hatch after manually running `oxfmt`/`oxlint` to replicate what the hook would have done.

### 2026-06-29 - DEV.to: 4 articles published (batch)
- **Status**: Completed (all 4 live; verified in /me/published)
- **Description**: Ranked trending dev.to ai/llm/mcp/claudecode by reactions + 3×comments. Picked 4 in the user's first-hand lane, each distinct from prior 6 posts. dev.to throttles rapid POSTs (HTTP 429 "try again in 30s") — first batch loop published 2/4, retried the other 2 spaced ~35s apart. Voice: "real problem / my fix", concrete code each.
  1. "My AI Agent Read 56 KB to Answer One Question. I Made It Stop." (context flooding / context-mode sandbox routing; distinct from Context Rot=memory). Tags: ai, llm, claudecode, productivity. `drafts/agent-reads-56kb-context-flooding.md`
  2. "My AI Wrote Code That Passed Every Test and Was Still Wrong" (functional≠correct; r/c-top of week). Tags: ai, llm, codequality, claudecode. `drafts/functional-doesnt-mean-correct.md`
  3. "One Agent or Five? What I Learned Running a Team of AI Coders" (multi-agent fan-out vs pipeline). Tags: ai, claudecode, llm, productivity. `drafts/one-agent-or-many.md`
  4. "I Stopped Installing MCP Servers Blind. Here's My 5-Minute Vetting Checklist." (install-side MCP vetting; distinct from prior build-side security piece). Tags: mcp, ai, security, claudecode. `drafts/vetting-mcp-servers-before-install.md`
- **URLs**:
  - https://dev.to/enjoy_kumawat/my-ai-agent-read-56-kb-to-answer-one-question-i-made-it-stop-34g5
  - https://dev.to/enjoy_kumawat/my-ai-wrote-code-that-passed-every-test-and-was-still-wrong-lad
  - https://dev.to/enjoy_kumawat/one-agent-or-five-what-i-learned-running-a-team-of-ai-coders-4lci
  - https://dev.to/enjoy_kumawat/i-stopped-installing-mcp-servers-blind-heres-my-5-minute-vetting-checklist-30ph

### 2026-06-24 - DEV.to article: agent cross-session memory
- **Status**: Completed (published live)
- **Description**: Ranked trending dev.to AI/LLM/MCP/claudecode posts by reactions + 3×comments. Top fit for the user's lane: "agents don't remember" (high comment count = live problem), grounded first-hand in this repo's `docs/project_notes/` memory system. Distinct from prior "Context Rot" piece (that was mid-session degradation; this is cross-session amnesia). Voice: "real problem / my fix", concrete code = the 4-file structure + CLAUDE.md trigger protocols. Tags: ai, llm, claudecode, devtools. Source: `drafts/agents-dont-remember.md`. Published by PUT-promoting the existing draft (id 3977857) to avoid a duplicate — publish_devto.py always POSTs new.
- **URL**: https://dev.to/enjoy_kumawat/my-ai-agent-writes-great-code-and-forgets-all-of-it-by-tomorrow-32ec

### 2026-06-23 - OSS Contribution to google-gemini/gemini-cli — issue #28090
- **Status**: Completed (PR opened 2026-07-14, awaiting review) — unblocked via `gh auth refresh -s workflow`, rebased on upstream/main (clean), 93/93 shell tests green post-rebase, PR: https://github.com/google-gemini/gemini-cli/pull/28401
- **Description**: Triaged recent gemini-cli + google/adk-python issues for high merge-chance (no existing PR, clear scope). Picked #28090 (p1: shell tool forwards unbounded command output to the model). Root cause: `llmContent` built from full `result.output`; only mediation is opt-in `summarizeToolOutput`. Fix: added `truncateLlmOutput` (codepoint-safe head+tail byte bound, `MAX_LLM_OUTPUT_BYTES = 32 KiB`) in `packages/core/src/tools/shell.ts`, applied to normal-completion + aborted paths. Added 4 unit tests. Verified: 93/93 shell tests, tsc, eslint all clean; reported 40319-byte case → 32768 bytes. Branch `fix/28090-large-shell-output` in `codes/gemini-cli`, based on current `upstream/main`.
- **URL**: https://github.com/google-gemini/gemini-cli/issues/28090
- **Notes**: Forks cloned to `codes/` (adk-python, gemini-cli). Other live candidates with no PR: adk-python #6171 (eval), #6167 (services). Skipped #27790, adk #6174 (already had PRs).

### 2026-06-23 - DEV.to article: MCP security + /devto-article command
- **Status**: Completed (published live)
- **Description**: Built `/devto-article` slash command + `publish_devto.py` (reusable stdlib publisher; handles dev.to 403-bot UA, H1 strip, frontmatter). Test-ran it to draft, then published "I Build MCP Servers. Here's the Security Hole Nobody Talks About." (MCP prompt-injection / least-privilege). Tags: mcp, ai, security, claudecode. Source: `drafts/mcp-backdoor.md`.
- **URL**: https://dev.to/enjoy_kumawat/i-build-mcp-servers-heres-the-security-hole-nobody-talks-about-41b6

### 2026-06-23 - DEV.to article: Context Rot
- **Status**: Completed (published live)
- **Description**: Researched trending dev.to AI/LLM/Claude Code pain points; picked context-window degradation (most-discussed thread, 62 comments). Wrote + published "Context Rot: Why Your AI Coding Agent Gets Dumber Mid-Session (and How I Stopped It)" in established "real reason / my fix" voice, grounded in our `context-mode` setup. Tags: ai, claudecode, llm, productivity. Source: `drafts/context-rot.md`.
- **URL**: https://dev.to/enjoy_kumawat/context-rot-why-your-ai-coding-agent-gets-dumber-mid-session-and-how-i-stopped-it-3e9o

### 2026-06-21 - Phase 1: GitHub Profile README
- **Status**: Completed
- **Description**: Created `template.md` with animated typing SVG, tech stack badges, open source contribution badges, GitHub stats widgets. Auto-push via `update_profile.py` (stdlib-only).
- **Result**: Live at `github.com/enjoykumawat`

### 2026-06-21 - Phase 2: Developer Presence MCP Server
- **Status**: Completed
- **Description**: Built `server.py` — 7-tool FastMCP server combining GitHub REST API + DEV.to API. Tools: get_github_profile, list_repos, get_repo_stats, list_articles, create_article, update_article, get_article_stats.
- **Next**: Publish as public repo + write DEV.to article to drive visibility

### 2026-06-21 - Phase 3: AI Commit Message Generator
- **Status**: Completed
- **Description**: Built `git_commit.py` (20-line standalone CLI) + `generate_commit_message` MCP tool. Uses `claude -p` subprocess (OAuth, no API key). Published dev.to article and pushed to `enjoykumawat/my-git-manager`.
- **URLs**: https://dev.to/enjoy_kumawat/i-fixed-the-ai-commit-messages-problem-in-50-lines-of-python-3a5a | https://github.com/enjoykumawat/my-git-manager

### 2026-06-22 - OSS Contribution to nodejs/undici — review response
- **Status**: Merged (confirmed 2026-07-14)
- **Description**: Addressed `metcoder95` feedback: removed full `## Pre-built interceptors` section from `Dispatcher.md` (-285 lines), replaced with 3-line pointer to `Interceptors.md`, added link from `dispatcher.compose()` section, removed 9 now-unused link references. Pushed as commit `fbac28a1` on branch `docs/add-interceptors-api-page`.
- **URL**: https://github.com/nodejs/undici/pull/5446

### 2026-06-21 - Option C: OSS Contribution to nodejs/undici
- **Status**: Completed (PR opened)
- **Description**: Added missing API docs for all 8 built-in interceptors (`dump`, `retry`, `redirect`, `decompress`, `responseError`, `dns`, `cache`, `deduplicate`). Created `docs/docs/api/Interceptors.md` + updated sidebar in `site.json`.
- **URL**: https://github.com/nodejs/undici/pull/5446

### 2026-06-21 - Deleted oh-my-codex repo
- **Status**: Completed (manual)
- **Description**: Deleted `enjoykumawat/oh-my-codex` via GitHub Settings UI (API token lacked delete_repo scope)
