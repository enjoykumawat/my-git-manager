# DEV.to comment replies — pending

Paste each reply at its comment link, then delete the entry (once you reply
on-site the script excludes it automatically anyway; the id_code in this file
is what marks it "drafted" until then).

The dev.to API cannot post comments or reactions (verified 2026-07-18), so
this file is the last manual step: click link → paste → done.

---

## 3bdja — python7427 on "I Already Wrote the Article Fixing This Bug. It Broke Again Anyway."
https://dev.to/enjoy_kumawat/comment/3bdja

> Man still new in the field... what resources do you recommend

Welcome! Honestly, the way I learned most of this wasn't a course — it was picking one small, real annoyance (mine was writing commit messages) and automating it, then debugging everything that broke along the way. For fundamentals: the official Python tutorial, then "Automate the Boring Stuff" (free online). For the debugging habit specifically: read the full traceback bottom-up before touching code, and when you fix a bug, write one sentence about it somewhere you'll see again. That last habit is basically what this article is about — my note-taking failed, not my fix.

## 3bd4o — mads_hansen on "I Almost Hand-Rolled JSON-RPC for an MCP Server."
https://dev.to/enjoy_kumawat/comment/3bd4o

Agreed — valid JSON is the floor, not the contract. Constrained ints and enums are the next step I'd take here, and a `retryable` flag on error responses would have saved me one real debugging session already. The tension I'm watching: every constraint I add to the schema also rides along in `tools/list` on every session, so strictness has a token price. Contract-testing `list_tools` against boundary inputs is going on my list.

## 3bdc8 — skillselion on "I Almost Hand-Rolled JSON-RPC for an MCP Server."
https://dev.to/enjoy_kumawat/comment/3bdc8

"The docstring silently becomes routing surface" is the sharpest framing of this I've seen. I wrote those docstrings for humans and only later realized they're prompts — the agent picks tools based on prose I never reviewed as prose. And you're right about the accidental budget: the low-level path's friction was doing rate-limiting on my tool count without me noticing. Eight tools already costs real context on every session start; I measured that in a separate post and the number was uncomfortable.

## 3bd50 — fromzerotoship on "I Measured What My Agent's Own Memory File Costs to Read."
https://dev.to/enjoy_kumawat/comment/3bd50

"Death by justified additions" — stealing that. Your index discipline is the part I needed to hear: I've caught myself writing the rich three-clause summary "so I don't have to open the file," and you're right that it just rebuilds the bloat one layer up. Pointer + hook, pay the open when you want detail. And yes — justification doesn't scale, a byte count does. That's why the measurement, not the cleanup, was the actual fix.

## 3bcal — alexshev on "My AI Commit Hook Never Failed a Single Commit."
https://dev.to/enjoy_kumawat/comment/3bcal

"A status message with extra confidence" is exactly what it was. The fix that stuck for me was your test: deliberately feed it a known-bad case and confirm it actually blocks. A failure path that's never exercised isn't a failure path — it's decoration.

## 3bcab — alexshev on "One .env Key Held Two Different Usernames."
https://dev.to/enjoy_kumawat/comment/3bcab

"Refusing to make ambiguity clever" — that's the whole fix in five words. Every guessing heuristic I considered was just deferring the contract problem to a worse moment. Failing loudly enough that the operator has to name the account was less code AND more correct, which is rare enough to write down.

## 3bca8 — alexshev on "My Publishing Agent Runs Twice a Day and Remembers Nothing."
https://dev.to/enjoy_kumawat/comment/3bca8

Exactly — the durable state lives in plain files the agent must re-read, so every run starts from current facts instead of cached assumptions. The surprise for me was that "remembers nothing" turned out to be a feature I had to defend, not a limitation I had to fix. Stale memory fails quietly; a re-read fails loudly when the file is wrong, and loud is what I want.

## 3bahe — skillselion on "My Project's Own Instructions Told My Agent to Use Tools That Don't Exist"
https://dev.to/enjoy_kumawat/comment/3bahe

"Nothing runs CLAUDE.md, so nothing can fail when it lies" — that's the whole bug in one line. The SessionStart lint you describe (extract tool names, diff against what's actually configured, prepend a warning) is concrete enough that I'm tempted to build it this week. And the wording fix matters as much as the tooling: "MANDATORY when available" stays true across environments; bare "MANDATORY" starts lying the moment the tooling moves.

## 3bal9 — alexshev on "My Project's Own Instructions Told My Agent to Use Tools That Don't Exist"
https://dev.to/enjoy_kumawat/comment/3bal9

Agreed — and "boring" is the right word. The check doesn't need intelligence, it needs to run: every named tool, path, and command validated against the environment before an agent is told to trust it. Instructions age like code but get none of code's failure signals; the lint is how you give them one.

## 3b908 — mads_hansen on "My MCP Server Only Talks to APIs I Trust."
https://dev.to/enjoy_kumawat/comment/3b908

"The pipe can be clean. The payload can still need a warning label" — well put. The origin/interpretation split you list (user-authored vs system-authored, authoritative vs descriptive) is the metadata I wish the protocol nudged servers toward, because right now every server invents its own convention or, worse, sends bare text and lets the model decide what it means. Provenance traveling with the data instead of living in docs is the right direction.

## 3b9fi — eduzsh on "My Commit Message Generator Kept Signing Its Own Work."
https://dev.to/enjoy_kumawat/comment/3b9fi

Landed in exactly the same place: post-process in the script. The hook now does a plain string match on the generated message and strips attribution lines before the commit happens — no prompt involved. Prompt rules are advisory, code is enforced; once a wrong output costs something real, the check has to live where the model can't deprioritize it. The prompt still says "don't sign" as a first line of defense, but the strip is what I actually trust.

## 3b6f1 — alexshev on "Every Commit in My Repo Gets Reviewed by a Second AI."
https://dev.to/enjoy_kumawat/comment/3b6f1

That's it exactly — the value isn't a smarter model, it's a different failure mode. The author-model is optimizing for "make it work"; the reviewer has no attachment to the patch and asks what assumption is hidden. The best catches in my log are all things the first model *knew* but had normalized because it was mid-flow.

## 3b6fe — alexshev on "My requirements.txt Had a Landmine in It."
https://dev.to/enjoy_kumawat/comment/3b6fe

Agreed — "the boring check is the valuable check" should be printed on a poster. No creativity needed: notice drift, notice unpinned versions, notice privileges nobody uses. My landmine sat there for weeks precisely because noticing it was too boring for a human to do unprompted.

## 3agfe — hannune on "I Ditched Vector Search for My Coding Agent's Memory. FTS5 Won."
https://dev.to/enjoy_kumawat/comment/3agfe

The BM25-on-sparse-tokens point explains *why* it won better than I did in the article — error codes and stack-trace tokens are exactly where IDF weighting shines and embeddings blur. Your split (FTS5 for structured artifacts, vectors for cross-session prose) matches what I'm converging on. Hadn't tried the trigram tokenizer for partial matches on route paths — that's going in this week, thanks.

## 3ail8 — skillselion on "My Agent Said the Tool Call Succeeded. It Had 404'd."
https://dev.to/enjoy_kumawat/comment/3ail8

The reason-enum fix is better than what I shipped — I made the error branch carry the flag, but "done with no error" can still be ambiguous between no-op and never-ran. Making the terminal path carry an explicit reason so nothing-to-do can't collapse into model-never-answered kills the whole class, not just my instance. And yes: writing the red test against the terminal path first felt backwards and was exactly why that branch had never been covered.

## 3aa6b — vollos on "My AI Wrote Code That Passed Every Test and Was Still Wrong"
https://dev.to/enjoy_kumawat/comment/3aa6b

The sixth category is real and it's the scariest one, because the fix looks identical ("write the test the model dodged") but the test author has to switch personas — attacking the trust boundary means logging in as the wrong person, which no honest-path suite ever does. "Every checkmark stays green because no test ever logs in as someone else" is going in my notes verbatim. Appreciate the scanner offer — this repo is local tooling without an auth surface, but the different-user test rule applies to a project I do have, so the point lands.

## 3aceg — nark3d on "My AI Wrote Code That Passed Every Test and Was Still Wrong"
https://dev.to/enjoy_kumawat/comment/3aceg

"Green just meant the code agreed with itself" — that's the tweet-length version of my whole article. Code and test off the same prompt share the same blind spots by construction, so the failing cases have to come from outside the prompt: the malformed line, the pre-set variable, the input the author never imagined. External cases or it's a mirror, not a test.

## 3a29k — max_quimby on "My AI Agent Writes Great Code and Forgets All of It by Tomorrow"
https://dev.to/enjoy_kumawat/comment/3a29k

Honest answer: I prune when something bites, and it bit — I later wrote a whole post about a fact that sat six weeks stale in memory and misled the agent exactly the way your old-API "fix" did. Your verification stamp (date/commit last verified, re-check anything older than the code it describes) is the mechanism I was missing; a fact should carry its own expiry evidence. The promotion step (twice-seen episodic → durable file, trim the episode) I do informally — making it a rule is the upgrade.

## 39pk4 — truong_bui on "I Build MCP Servers. Here's the Security Hole Nobody Talks About."
https://dev.to/enjoy_kumawat/comment/39pk4

Honest answer to your question: session level, and I know that's the weak version. Nothing structural stops someone (including future me) wiring a convenience agent that holds both the untrusted-read tool and the write tool in one loop — it's discipline, not enforcement. Structural enforcement probably has to live where the tools are registered, not where the session is configured, because "works until someone builds the convenient thing" always ends the same way. Your finding that boring misconfiguration dwarfs dramatic zero-days across ~650 servers matches what reading source by hand taught me — the scary stuff is mundane.

## 39om0 — alexshev on "I Fixed the 'AI Commit Messages' Problem in 20 Lines of Python"
https://dev.to/enjoy_kumawat/comment/39om0

Agreed — the diff can only ever explain *what*; the *why* lives in the author's head. My compromise: the hook drafts from the diff, but the message lands in my editor before the commit finalizes, so adding the why costs one edit instead of a blank page. The blank page was what kept producing "fix stuff" commits; the draft removes the blank page, the edit keeps the why human.
