# Work Log

---

### 2026-07-15 - DEV.to: 2 articles published (first run of the day)
- **Status**: Completed (both live; verified 200 on each URL)
- **Description**: Checked quota via `GET /api/articles/me/published` — today's total was 0 (new UTC day), so this run published 2 per the normal 1-3 range. Scored trending ai/llm/mcp/claudecode/agents/productivity posts by reactions + 3×comments. Explicitly skipped several top scorers as already covered by the prior 19 posts: "Return on Attention: Why AI Code Reviews Are Wearing Us Out" and "I Could Review It. I Couldn't Write It." (both too close to the 2026-07-14 second-ai-reviewer-fatigue post), "Bigger Context Windows Didn't Make Our RAG Smarter" (too close to the FTS5-not-vectors and 56KB-context-flooding posts), "I Stopped Trusting the Agent's 'Done' - prove-it, a verify.sh Gate" (too close to the 2026-07-14 "tests pass" post), and the recurring "I Deleted 200 Lines of Code I Didn't Write" theme (already the undici-deletion-lesson post). Picked 2 themes with a distinct first-hand angle:
  1. "The Myth of the Post-Documentation Era" trend (ai/documentation, score 150) → reframed around a genuinely new angle: docs in `docs/project_notes/` are read by an agent every session, not by humans skimming a wiki, which changes what "good documentation" means (terse facts over narrative prose, expiry triggers on every fact, protocol blocks as routing logic). Grounded in the real stale `key_facts.md` token-scopes line (fixed 2026-07-14, caused a real repeat 403 six weeks after the underlying fix existed in `bugs.md`) and the actual `CLAUDE.md` Protocols block. Distinct from the earlier cross-session-memory post (that was about persistence; this is about writing style once you assume an LLM-only reader).
  2. Real incident from this run itself: `git status` on session start showed `HEAD detached from refs/heads/main` with 2 real commits from a prior session floating unreachable from any branch. Wrote it up live — root cause (a previous session checked out a specific commit instead of the branch ref and never switched back), the actual risk (concurrent sessions fighting over one shared working tree's `HEAD`), and the fix (`git worktree add` for isolated checkouts instead of switching branches in place, tying it to this environment's own `EnterWorktree`/`ExitWorktree` tools and the `Workflow` tool's `isolation: 'worktree'` option). Distinct from the multi-agent-teams post (that was about fan-out/pipeline decision-making, not git working-tree isolation). Weak trending signal on its own (claudecode-tag "worktrees" post, score 9) but strong first-hand anecdote that happened in this exact session.
  - Tags: ai/claudecode/documentation/productivity; claudecode/agents/git/devtools. Sources: `drafts/docs-for-an-agent-not-a-human.md`, `drafts/detached-head-agent-worktrees.md`.
  - https://dev.to/enjoy_kumawat/my-project-docs-arent-for-humans-anymore-theyre-for-an-agent-that-re-reads-them-every-session-56a7
  - https://dev.to/enjoy_kumawat/my-agents-git-checkout-left-two-commits-floating-in-nowhere-worktrees-fixed-the-actual-problem-54m2

### 2026-07-14 - DEV.to: 2 articles published (third run, capped at daily max of 5)
- **Status**: Completed (both live; verified 200 on each URL)
- **Description**: Checked quota via `GET /api/articles/me/published` (had to add `User-Agent: Mozilla/5.0` — dev.to 403s the default urllib UA on GET too, not just POST). Today's total was already 3 (from the second run's batch below), so this run published 2 to land exactly at the 5-article daily cap rather than the normal 1-3 range. Ranked trending ai/llm/mcp/claudecode/agents/productivity posts by reactions + 3×comments; explicitly excluded "The Citation Lied Without Lying," "The Agent Faked a Test Log," and the fastmcp/unbounded-dependency post since those were this morning's source trends already used. Picked 2 themes with a distinct first-hand angle not covered by the prior 17 posts:
  1. "Return on Attention: Why AI Code Reviews Are Wearing Us Out" trend (ai/productivity, score 124) → distinct from the "tests pass" verification-discipline post and the "citation lied" stale-memory post — this one is about the *workflow* cost of a mandatory second-AI-review step, grounded in this repo's own real `CLAUDE.md` line ("codex will review what you done") and a 3-bucket triage protocol (fix silently / ask first / skip silently), with real examples from the `vercel/eve` #454 DCO-signing decision (bucket: ask first) and the `nodejs/undici` #5446 review response (bucket: fix silently).
  2. "I Deleted 200 Lines of Code I Didn't Write and Learned More Than When I Wrote It" trend (ai, score 124) → distinct from all prior OSS-contribution mentions (that PR was never written up on its own) — grounded fully in the real `nodejs/undici` #5446 review-response event: added `Interceptors.md` duplicating an existing but hard-to-find `Dispatcher.md` section, reviewer caught it, fix was -285/+3 lines on commit `fbac28a1`. Lesson: keyword grep found the term but not the existing section's shape, since it was buried as a subsection of a differently-named file.
  - Tags: ai/claudecode/productivity/devtools; ai/agents/claudecode/debugging. Sources: `drafts/second-ai-reviewer-fatigue.md`, `drafts/undici-deletion-lesson.md`.
  - https://dev.to/enjoy_kumawat/every-commit-in-my-repo-gets-reviewed-by-a-second-ai-heres-what-actually-changed-4k92
  - https://dev.to/enjoy_kumawat/my-open-source-pr-added-285-lines-of-docs-a-reviewer-told-me-to-delete-most-of-them-they-were-3ii3

### 2026-07-14 - DEV.to: 3 articles published (second run, egress restored)
- **Status**: Completed (all 3 live; verified 200 on each URL)
- **Description**: First run today was blocked by a sandbox egress policy denial on `dev.to:443` (see entry below) — egress was restored by this run, and today's published count was still 0, so per the run policy this batch published 3 (minimum-2 floor cleared with room for a 3rd genuinely distinct angle). Ranked trending dev.to ai/llm/mcp/claudecode/agents/productivity posts by reactions + 3×comments; picked 3 themes with a distinct first-hand angle not covered by the prior 14 posts:
  1. "The Agent Faked a Test Log, Then Believed It" trend (agents/llm, score 132) → distinct from the earlier "faked tool result" post (that was a code bug in `vercel/eve` swallowing a terminal error) — this one is about verification *discipline*: never accept an agent's self-report of "tests pass" without a forced red-before/green-after transition, grounded in the actual eve #454 PR methodology and the repo's own `codex reviews what you've done` second-pass note.
  2. "The Citation Lied Without Lying" trend (agents/llm, score 131) → distinct from the earlier "agents don't remember" post (that was total amnesia) — this one is about *stale* memory being presented with full confidence. Found and fixed a real live instance in this repo: `key_facts.md`'s token-scopes line never got the `workflow` scope added after `bugs.md`'s 2026-06-23 entry documented needing it. Fixed both files as part of writing the piece.
  3. Real "unbounded MCP dependency" trend (mcp, fastmcp 421 incident) → audited this repo's own `requirements.txt`, found the exact same anti-pattern (`mcp[cli]` with zero version constraint), pinned it to `>=1.28.0,<2.0.0`. Also fixed a `publish_devto.py` bug found along the way: `load_env()` crashed with `FileNotFoundError` when no `.env` file exists (this sandbox has `DEV_TO_API` set directly in the environment) — added the same try/except pattern `server.py` already used.
  - Tags: agents/ai/claudecode/debugging; ai/llm/agents/productivity; mcp/python/security/devtools. Sources: `drafts/stopped-trusting-agent-done.md`, `drafts/citation-lied-without-lying.md`, `drafts/unbounded-mcp-dependency.md`.
  - https://dev.to/enjoy_kumawat/my-agent-kept-saying-tests-pass-i-stopped-believing-it-378k
  - https://dev.to/enjoy_kumawat/my-agents-memory-file-wasnt-wrong-it-was-just-six-weeks-stale-458m
  - https://dev.to/enjoy_kumawat/my-requirementstxt-had-a-landmine-in-it-it-just-hadnt-gone-off-yet-84n

### 2026-07-14 - DEV.to run blocked: dev.to unreachable from sandbox egress policy
- **Status**: Blocked (no articles published, no quota consumed)
- **Description**: Scheduled DEV.to publishing run could not get past Step 1 (quota check). `dev.to:443` is not on the environment's egress allowlist — every outbound HTTPS call to it fails at the agent proxy with a hard `403` on `CONNECT` (`gateway answered 403 to CONNECT (policy denial or upstream failure)`, confirmed via `curl $HTTPS_PROXY/__agentproxy/status`). This is a hard organization policy denial, not a transient network error — per `/root/.ccr/README.md` these must not be retried or routed around (no CA/proxy workaround applies; the host itself is denied). No workaround exists from inside this sandbox; the environment's network policy needs `dev.to` added to the allowlist for this to run.
- **Action needed**: Either run the DEV.to publishing task from an environment whose egress policy allows `dev.to`, or get `dev.to` added to this environment's allowed egress hosts.

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
