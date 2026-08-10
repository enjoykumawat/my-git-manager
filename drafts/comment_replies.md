# DEV.to comment replies — pending

Paste each reply at its comment link, then delete the entry (once you reply
on-site the script excludes it automatically anyway; the id_code in this file
is what marks it "drafted" until then).

The dev.to API cannot post comments or reactions (verified 2026-07-18), so
this file is the last manual step: click link → paste → done.

---

## 3c8em — mads_hansen_27b33ebfee4c9 on "My MCP Tool's Audit Log Was Built So a Bad Write Would Leave a Trace. The Log Itself Leaves None."
https://dev.to/enjoy_kumawat/comment/3c8em

The `outcome_unknown` state is the piece I didn't have language for. My actual gap is even earlier than your state machine — the log currently only gets appended after a successful write, so there's no `intent_recorded` step at all, which means a crash between "decided to write" and "wrote the log line" leaves nothing, not even an ambiguous entry. Your crash-point list is a better test plan than what I ran (a happy-path unit test against fake before/after state). I haven't picked between local SQLite and a shared durable sink yet — that's still the open decision I flagged — but "store hashes/revisions, not full bodies" is going to shape whichever one I pick, since right now the entry writes the full before/after field values.

## 3c7og — mads_hansen_27b33ebfee4c9 on "My MCP Server's .env Loader Only Works If You Launch It From One Specific Directory. My MCP Client Doesn't Promise That."
https://dev.to/enjoy_kumawat/comment/3c7og

Agreed, and the startup validation report is the exact gap I called out at the end and didn't fix — right now a missing key surfaces as a bare `KeyError` from inside `_gh()`/`_dev()` on the first tool call, not at startup, and it names neither variable. Your point about not treating a repo-adjacent `.env` as the production source is fair too, though in this project's case it's honestly the only source — this is a single-developer MCP server launched from one documented Claude Desktop config, not a multi-environment deploy, so the launcher-injection path you're describing would be new infrastructure, not a swap. Still, "fail loud at startup with which var and which source" is worth doing regardless of where the secret ultimately comes from.

## 3c7fg — alexshev on "I Looked for Where My Publishing Agent Needed a State Machine. The State Machine Was Already Live on dev.to."
https://dev.to/enjoy_kumawat/comment/3c7fg

That's the whole finding, yeah. The tell for me was that every fact I was tempted to track locally (which step, which article, what succeeded) was actually just a stale copy of something dev.to's own API would answer correctly on the next call — so the "state machine" was really just remembering to ask instead of remembering the answer.

## 3c7fi — alexshev on "My Repo Has One Pinned Dependency and Zero pip install Calls. I Didn't Design That for Security."
https://dev.to/enjoy_kumawat/comment/3c7fi

Right, and I want to be careful not to oversell it as a strategy — it's a side effect of a convenience decision, not a security review I ran. The part I'd actually generalize is narrower: an agent's `pip install <name>` suggestion shouldn't reach a shell unchecked, whether that's because there's no dependency path to exploit at all (my case) or because something's actually verifying the name first (the PyPI check at the end, for projects that do need real dependencies).

## 3c693 — mads_hansen_27b33ebfee4c9 on "My MCP Server's GitHub Helper Function Could POST and DELETE. Every Tool That Called It Only Ever Used GET."
https://dev.to/enjoy_kumawat/comment/3c693

You're right that the code guard doesn't change what the token itself can do — `GITHUB_TOKEN` is still scoped `repo, user`, full write, and I haven't touched that. The first regression test you describe I do have: the `method != "GET"` check raises before `urlopen` is ever called, verified with a call counter at zero. The second one — request bodies rejected — I don't have, and looking at it now `_gh` would silently attach a JSON body to a GET request if some future call ever passed `data` alongside the default method, which the code-level guard wouldn't catch. Scoping a second, read-only token is the actual fix for the identity layer; adding that test is cheap and I'm doing it next.

## 3c8d0 — fern_eterna on "My MCP Server Holds Two API Keys. Every Tool Call Runs in the Same Process as Both."
https://dev.to/enjoy_kumawat/comment/3c8d0

To be clear about where this repo actually stands: the article proposes the two-process split, it hasn't been built — `server.py` still loads both `GITHUB_TOKEN` and `DEV_TO_API` into one process at import, one `FastMCP` instance, no broker. On your question, my rough answer would be threat model, not credential count: a third credential earns its own process when a compromise of it has meaningfully different blast radius than what's already isolated — a write-capable exchange key next to a read-only GitHub token isn't "one more of the same," it's a different failure mode entirely. A scoped token inside the existing process is fine when the new credential's worst case looks like the existing ones'. I'll pass on the pitch for now — this repo doesn't have a trading surface to plug it into — but that's a real question and worth thinking through properly rather than answering it in a comment reply.

## 3c8ph — rizzdev on "My MCP Server Holds Two API Keys. Every Tool Call Runs in the Same Process as Both."
https://dev.to/enjoy_kumawat/comment/3c8ph

That's a real hole in the fix as I sketched it, not a nitpick. The two-process split stops one server's code from ever holding both tokens in the same `os.environ`, but you're right that it does nothing about the client-side tool list — the agent's conversation can still call the GitHub-server tool and the dev.to-server tool back to back in the same turn, and neither the protocol nor the tool call carries anything marking which server a given call's authority came from. So the isolation I described defends against a bug or a compromised process reaching for a credential it wasn't given — it doesn't defend against a single agent session legitimately using both servers' tools in a sequence nobody reviewed. That's a client/orchestration-layer problem, not something a server-side process boundary can fix, and I don't have an answer for it yet.

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

## 3be55 — alexshev on "I Almost Hand-Rolled JSON-RPC for an MCP Server."
https://dev.to/enjoy_kumawat/comment/3be55

That's exactly the tradeoff I landed on writing this up — the boring plumbing removes a whole class of protocol bugs I'd have shipped myself (cancellation, weird client retries) for free. But it's not zero-judgment: FastMCP's schema generation didn't catch a `min(per_page, 30)` clamp one tool needed, and tool-call errors still come back opaque enough that I had to reformat them by hand. So the taste budget moves to tool boundaries like you said, but a sliver of it stays on the plumbing too.

## 3be54 — alexshev on "I Measured What My Agent's Own Memory File Costs to Read."
https://dev.to/enjoy_kumawat/comment/3be54

That's basically the split I ended up with by accident: `issues.md` is the raw log, append-only, never pruned, and `bugs.md`/`decisions.md`/`key_facts.md` are the distilled operating model the agent actually reads first each run. I didn't design it as distillation up front, it just came from not wanting to re-read the full log every session, but "periodic distillation" is the right name for it. The part I haven't automated is *when* something in the distilled files goes stale versus the raw log — right now that's still a human noticing, not a process.

## 3bh2i — alexshev on "My MCP Server Has 8 Tools and Zero Log Lines. Diagnosing a Failure Meant Guessing From the Outside."
https://dev.to/enjoy_kumawat/comment/3bh2i

Agreed, and that's exactly where I stopped short in this piece — I only got as far as "log the call," not "make the run diagnosable." Right now `_gh`/`_dev` still don't capture a request id or an argument snapshot, so if a call inside a tool fails I'd know it happened but not much about the shape of the failure. Result summaries and a defined set of failure classes (auth vs. rate-limit vs. transport vs. 4xx-from-policy) are the next real step, not the logging line itself.

## 3bfgb — fromzerotoship on "df Said My Sandbox Had No Disk Left. It Wasn't Wrong, It Just Wasn't Answering the Question I Asked"
https://dev.to/enjoy_kumawat/comment/3bfgb

The WAF-to-405 example is the same shape exactly — a status code that's technically accurate for a question nobody asked ("did a rule fire") standing in for the one you actually asked ("did my request succeed"), and it costs you real time before you think to stop trusting the summary and read the body. Your running file of one-liners is basically what `bugs.md` is in this repo, and I'd bet it earns its keep the same way: worthless until 2am, then the only thing that saves you. The agent-overcorrection point is the one I'd underline back — a human misreading `df` shrugs, an agent misreading it can go looking for something to delete. That's the actual argument for writing the note down, not just convenience.

## 3belg — mads_hansen_27b33ebfee4c9 on "My Comment-Reply Bot Hit a Wall the Docs Never Mentioned. That Wall Turned Out to Be a Security Feature."
https://dev.to/enjoy_kumawat/comment/3belg

Fair correction — I treated the 404-then-401 pair as confirmation, but you're right that's still an inference from behavior, not verification against the spec or an official statement. I haven't actually checked DEV.to's OpenAPI docs or source for this; I reasoned entirely from the two failure shapes. The capability matrix idea is the concrete fix — right now this repo has exactly one write endpoint (`create_article`) and nothing written down about what it can't do, which is precisely the setup where a working write gets generalized by habit to endpoints that were never tested.

## 3bf35 — alexshev on "My Comment-Reply Bot Hit a Wall the Docs Never Mentioned. That Wall Turned Out to Be a Security Feature."
https://dev.to/enjoy_kumawat/comment/3bf35

That's a sharper way to put it than I did — publishing and replying look like the same category of write from inside my own code, but they carry different identity and abuse risk from the platform's side. "The wall is the consent surface" is a good enough line that I'm annoyed I didn't write it that way myself.

## 3bf36 — alexshev on "I Fixed Unbounded Shell Output in an Open Source Agent. My First Draft Would Have Corrupted Text."
https://dev.to/enjoy_kumawat/comment/3bf36

Right — the part that made this bug sneaky is that a naive cap still looks like a safety fix, passes review, and only fails on input nobody put in the test fixtures. The real fix had to decide where to cut (byte-safe boundary, not code-unit), what marker to leave (`...[truncated]...` so the model knows something's missing rather than assuming it read everything), and that stderr/stdout both stay valid strings after the cut — three decisions, not one clamp.

## 3bef5 — mads_hansen_27b33ebfee4c9 on "My AI Commit Script and My MCP Tool Run the Exact Same Code. Only One of Them Is Agentic."
https://dev.to/enjoy_kumawat/comment/3bef5

Good catch, and checking my own code against it: you're right, `-> str` doesn't solve it here. `generate_commit_message` in `server.py` has no empty-diff check at all — the script has one (`if not diff.strip(): print(...); raise SystemExit(1)`), but the MCP tool just passes whatever it gets straight to `_claude()` and returns whatever comes back. An agent calling it with an empty diff gets a string back either way, with nothing to tell it "no-op" from "here's your message." Schema + bounded error semantics is exactly the gap; I only built the schema half.

## 3bf38 — alexshev on "My AI Commit Script and My MCP Tool Run the Exact Same Code. Only One of Them Is Agentic."
https://dev.to/enjoy_kumawat/comment/3bf38

Agreed — that's the part I underweighted while writing this. The decorator changes who can find and call the function and under what permission surface; the model invocation underneath never changes at all.

## 3bf3e — alexshev on "My Blog Had 20 Unanswered Comments Across 35 Posts. Nothing Ever Told Me."
https://dev.to/enjoy_kumawat/comment/3bf3e

That's the honest read of it — the pipeline had a clean success metric (published, live, verified 200) and zero metric for anything downstream of publish. An unanswered-comments audit is also just cheaper to build than it sounds; the whole check ended up being the recursive `replied_by_me` walk plus a diff against what's already drafted, maybe 20 lines total.

## 3bm7h — gnlassi on "My Commit Hook Calls an LLM on Every Commit. It Had No Timeout, So Neither Did `git commit`."
https://dev.to/enjoy_kumawat/comment/3bm7h

Thanks! And yeah, that's the part that stuck with me too — a limit isn't a nice-to-have on a call that blocks a normal git command, it's the difference between "the tool failed" and "my terminal just hangs forever with no error." Added a 20s timeout on both subprocess calls after finding the hang was silent, not a crash.

## 3blgp — mads_hansen_27b33ebfee4c9 on "My MCP Tool Defaults to Draft Mode. The Script That Actually Publishes My Blog Doesn't Call It."
https://dev.to/enjoy_kumawat/comment/3blgp

That's exactly the gap I stopped short of naming in the article. `published: False` is a default a caller can respect or ignore, and in this repo the scheduled routine simply never calls the tool that has the safe default — it shells out to a script whose `published` flag comes from frontmatter the same task sets to `true` every run. There's no separate promotion step with its own credential to revoke, so right now the honest answer to "which component is authorized to cross draft → public" is "whichever process happened to run last." Your failure-test list (frontmatter changed post-approval, duplicate retry after timeout, lost response after a real POST) is a better spec than anything I've written down for this, and none of them are covered today.

## 3bk7k — mads_hansen_27b33ebfee4c9 on "My GitHub Token Is Valid. My MCP Server Still Gets a 403, and GitHub Never Saw the Request."
https://dev.to/enjoy_kumawat/comment/3bk7k

Fair — `documentation_url` is exactly the kind of heuristic that works until whatever's forging the response bothers to fake that field too. What I actually did was cruder: hit `$HTTPS_PROXY/__agentproxy/status` by hand to confirm the proxy, not GitHub, was answering. Your point about a trusted local header attached at the transport boundary (`blocked_by=agent_proxy`, policy id, destination) and stripped before the client sees it is the real fix — right now `_gh`/`_dev` in `server.py` have no such envelope, so a caller genuinely can't branch on origin-vs-policy without shelling out to check the proxy status the way I just did manually. That's a gap worth closing before I'd trust any retry logic built on top of these helpers.

## 3bkeo — alexshev on "Git Told Me I Was 14 Commits Ahead of Origin. I Wasn't — My Local Copy of \"origin/main\" Was Just Old."
https://dev.to/enjoy_kumawat/comment/3bkeo

Exactly right, and it's what the reflog gave away here — `refs/remotes/origin/main` had exactly two entries, the stale clone-time fetch and the push I'd just made. The pinned-commit checkout that produces the detached HEAD never touches that tracking ref, so it's stale from the moment the container boots, before I run a single command. Naming it as "which ref" instead of "which branch" is the fix; I just added a plain `git fetch origin main` before any ahead/behind comparison.

## 3bihp — alexshev on "A Post-Commit Hook Told Me to Rewrite 8 Pushed Commits to Fix \"Unverified.\" I Said No."
https://dev.to/enjoy_kumawat/comment/3bihp

Agreed, and checking the hook's claim before acting on it is what saved me here — 6 of the 8 commits already had the right committer, the actual gap was a missing signature. The part that made me say no outright was that its fix meant force-pushing already-shared history and setting committer identity to "Claude," which is AI attribution, just moved into git metadata instead of the commit message this repo already strips it from. A follow-up commit plus a real decision on signing beats rewriting history because a hook told me to.

## 3bm64 — eduzsh on "df Said My Sandbox Had No Disk Left. It Wasn't Wrong, It Just Wasn't Answering the Question I Asked"
https://dev.to/enjoy_kumawat/comment/3bm64

That's the part that worries me more than the misdiagnosis itself — the narration of "freeing space" reads identically whether the agent's clearing disposable cache or something you needed, so you can't tell from the commit message alone which one just happened. A preflight check against the actual quota (`shutil.disk_usage` compared to the known session limit, not raw `df`) turns "delete things and hope" into "this specific number is the real constraint," which is cheaper than auditing every cleanup diff after the fact like you're doing now.

## 3bo55 — mads_hansen_27b33ebfee4c9 on "My Commit-Message Script Has an Empty-Diff Guard. My MCP Tool Version Doesn't — and It Doesn't Fail Loud."
https://dev.to/enjoy_kumawat/comment/3bo55

Fair — what I shipped is exactly the "plausible sentence" problem you're pointing at, just with an `ERROR:` prefix instead of prose. It's still a bare string a caller has to `.startswith()` on, not a typed contract or a structured union. The hash-binding point is the sharper one though: right now nothing ties the diff string passed into the tool to the actual staged tree at commit time, so a caller could reuse a stale or fabricated diff and still get a message that looks valid. That's a gap I hadn't considered — I was solving "don't silently commit an explanation," not "prove the message matches what's about to be committed."

## 3bnel — cailab on "I Fixed a Timeout Bug Two Days Ago. The Copy of That Code Inside My MCP Server Still Has It."
https://dev.to/enjoy_kumawat/comment/3bnel

Yeah, that's the fix I still owe. `_claude()` in `server.py` and the inline `claude -p` call in `git_commit.py` are still two separate copies today — same STRIP list, same subprocess pattern, just duplicated instead of shared. I patched the timeout into both by hand, which is the exact "grep-and-hope" you're describing, not the actual fix. Pulling both into one module the script and the tool import from is the right next step, I just haven't done it yet.

## 3bnd2 — skillselion on "My Commit Hook Calls an LLM on Every Commit. It Had No Timeout, So Neither Did `git commit`."
https://dev.to/enjoy_kumawat/comment/3bnd2

The hook already does the capture-to-a-variable version of your fix — `MSG="$(python "$SCRIPT" ...)"` only overwrites `$1` if `$MSG` is non-empty, so a failure never wipes git's own template. But you're right that the deadline still only lives inside Python (`subprocess.check_output(..., timeout=20)`), not at the shell level. That means a hang in interpreter startup or the `git diff --staged` call itself isn't covered by anything — only the `claude -p` call is. Wrapping the whole `python "$SCRIPT"` invocation in `timeout 15` is the more honest fix and I haven't made that change yet.

## 3c00h — alexshev on "I Gave My MCP Tool an ERROR: Convention. I Only Taught It to One of Its Two Failure Paths."
https://dev.to/enjoy_kumawat/comment/3c00h

Agreed — a convention isn't real until it's exercised on every branch. Right now `_claude()` in `server.py` has exactly two failure paths, the empty-diff guard and the timeout, both prefixed `ERROR:` now, but that's the only case I've actually enumerated. I haven't tested what happens if `_STRIP_RE` strips a real response down to an empty string, or what a genuinely malformed `claude -p` output looks like. Your fixture list is basically the test suite I don't have yet — enumerate every state, assert only the failure ones carry the prefix.

## 3c0a8 — mads_hansen_27b33ebfee4c9 on "I Gave My MCP Tool an ERROR: Convention. I Only Taught It to One of Its Two Failure Paths."
https://dev.to/enjoy_kumawat/comment/3c0a8

You're right that a string sentinel is a liability, not just inconsistent — nothing stops `claude -p`'s real output from starting with something that reads like "ERROR:" and getting misclassified the other way. I haven't moved to a typed shape yet; every tool in `server.py` still returns a bare `str` or `dict` with no error variant modeled in the signature, so a caller has to know to check a substring. This fix made the string consistent across both branches — it didn't make failure exhaustively enforceable, which is the gap you're pointing at.

## 3c00b — alexshev on "My AI-Attribution Filter Strips Any Commit Mentioning \"llm\". Including the Ones About My Own LLM Calls."
https://dev.to/enjoy_kumawat/comment/3c00b

For this specific filter I'd still keep it a hard exclusion rather than a review queue — its only job is stripping attribution lines out of a commit message before it's written, and the other signals you list (generated output, credentials, eval code) would need a completely different check than string-matching a commit subject. What I did fix is exactly the trap you're describing though: the old version was a bare substring match, so it silently deleted real commits about my own LLM-calling code, not just fake attribution. Narrowing it to anchored phrases (`co-authored-by:`, `generated by claude`, etc.) fixed that without needing a queue.

## 3c00j — alexshev on "My prepare-commit-msg Hook Got a Timeout Fix 3 Days Ago. It Has Never Once Executed."
https://dev.to/enjoy_kumawat/comment/3c00j

That's exactly what's still missing. I fixed the reachability problem — `scripts/install-hooks.sh` actually copies the hook into `.git/hooks/` now — but the hook itself has zero self-reporting: no record of when it last ran, what input it saw, or whether it exited clean. Right now "verified it runs" means I checked `.git/hooks/` matches source once, by hand; there's no ongoing signal if it silently goes uninstalled again on the next fresh clone. A timestamped line appended on every run would close that gap.

## 3c00a — alexshev on "My Project Has a Memory File So My Agent Doesn't Reread Everything. It Never Learned My Most-Used Script Existed."
https://dev.to/enjoy_kumawat/comment/3c00a

Agreed, and that's basically why I built `scripts/check_key_facts.py` right after this — it diffs the filenames `key_facts.md` claims exist against what's actually in the repo root/`scripts/`/`hooks/`, so the summary can get caught lying instead of trusted by default. It's not automatic though: it's a script I have to remember to run, not something that fires before every action the way you're describing. So the failure mode you're naming — the summary quietly deciding what exists — is only partly closed; the check exists, nothing forces it to run first.

## 3bpji — neelagiri65 on "My GitHub Token Is Valid. My MCP Server Still Gets a 403, and GitHub Never Saw the Request."
https://dev.to/enjoy_kumawat/comment/3bpji

Confirmed it's the proxy, not the client rejecting locally. I hit `$HTTPS_PROXY/__agentproxy/status` directly and this session's outbound HTTPS runs through a local agent proxy — the request does leave the machine, but it hits that proxy and gets answered with a synthetic GitHub-shaped 403 (real `message`/`documentation_url` keys, except `documentation_url` pointed at Anthropic's own docs, not GitHub's) because raw `api.github.com` calls outside the session's declared repo scope get intercepted before ever reaching GitHub. So "GitHub never saw the request" was literal — the 403 body was proxy-authored.

## 3bpjj — neelagiri65 on "My MCP Server Has 8 Tools and Zero Log Lines. Diagnosing a Failure Meant Guessing From the Outside."
https://dev.to/enjoy_kumawat/comment/3bpjj

Honestly, neither — `server.py` still has zero logging calls today, same as when I wrote that piece. I got as far as naming what's missing (a request id and argument snapshot per call, a defined set of failure classes like auth/rate-limit/transport/4xx-from-policy) but haven't shipped even the print-statement version yet. It's on the list, not done.

## 3c102 — cailab on "I Fixed a Timeout Bug Two Days Ago. The Copy of That Code Inside My MCP Server Still Has It."
[skip — spam. References "SRE Sidekick," a "Vercel import issue," and OTel/GenAI tracing conventions — none of which exist anywhere in this repo. Doesn't engage the actual article (duplicated timeout logic between git_commit.py and server.py's _claude()). Reads like a templated bot comment written for a different post.]

## 3c1o2 — mads_hansen_27b33ebfee4c9 on "My MCP Tool Can Overwrite Any of My Live Articles With Just an Integer. No Diff, No Log, No Warning."
https://dev.to/enjoy_kumawat/comment/3c1o2

Right on the crash window — `update_article` in `server.py` fetches `before`, does the PUT, then calls `_log_article_update` with the result, so a process death or timeout between a landed PUT and that log call leaves a write with no record, exactly what you're describing. And you're right that fetch-then-write is still check-then-act: nothing stops another writer (me running the tool twice, or an edit from the dev.to UI) from landing between the GET and the PUT. I haven't checked whether dev.to's API exposes any conditional-write primitive (ETag, `If-Match`, a revision field) to build a real compare-and-set on top of — that's the actual next thing to check before promising more than "fetch first, log after," which is what I've got today.

## 3c1i9 — alexshev on "My Fix for \"The Git Hook Never Installs\" Landed Yesterday. Today's Container Didn't Have It Either."
https://dev.to/enjoy_kumawat/comment/3c1i9

That's fair, and it's exactly the gap the fix I shipped doesn't close. What I did was attach `install-hooks.sh` to `sync-main.sh`, which already runs unconditionally at the start of every session for an unrelated reason — so the hook gets reinstalled every run instead of depending on someone remembering to run a one-time step. But it's silent: no version stamp, no install path logged, no record of when it last actually ran. Right now "proof it's present" is still me rereading the script, not the runtime telling me. Your receipt idea is the right next layer on top of what I have.

## 3c1i8 — alexshev on "My Comment Pipeline Marks a Thread \"Handled\" the Moment I Reply Once. A Follow-Up Question Proved It Wrong."
https://dev.to/enjoy_kumawat/comment/3c1i8

Agreed, and I ended up landing close to what you're describing, just without a stored state at all. `needs_reply()` in `reply_comments.py` now walks the whole thread and checks who posted the newest message, not whether I ever replied — so there's no "handled" flag that can go stale, it's recomputed fresh every run from who spoke last. Functionally that gets me your "waiting/monitoring" case for free: if they follow up after my reply, they're now the latest speaker and the thread shows up as pending again. What I don't have is an explicit third state for "no actionable next move left" — right now it's binary, needs-reply or not.

## 3c1ih — alexshev on "My Comment-Dedup Check Used \"in\" on a Whole Markdown File. A Date in a Sentence Broke It."
https://dev.to/enjoy_kumawat/comment/3c1ih

Fixed the same way you're describing, actually — `pending()` in `reply_comments.py` now pulls `^## (\S+)` headers out of the drafts file into a set of id_codes and checks membership against that, instead of a raw substring `in` on the whole file. So it's a canonical key now, just the comment id rather than a hash of the text, sitting right next to the human-readable log the way you suggested. Markdown stayed the audit trail; it stopped being the lookup structure.

## 3c34p — mads_hansen_27b33ebfee4c9 on "My MCP Server Holds Two API Keys. Every Tool Call Runs in the Same Process as Both."
https://dev.to/enjoy_kumawat/comment/3c34p

I stopped well short of what you're describing — the article sketches a two-process split (separate `.env`, separate `FastMCP` instance per credential domain) as the fix and says outright it didn't apply it. Today `server.py` is still one process: `load_env()` loads `GITHUB_TOKEN` and `DEV_TO_API` straight into `os.environ` at import, and every one of the 8 tools sits in that same environment regardless of what it needs, including `generate_commit_message`, which touches neither API. So no brokered handles, no per-invocation capability, no adversarial fixtures testing the boundary — there isn't a boundary yet to test. Your point about two processes on the same Unix user still sharing `/proc` and inherited descriptors is sharper than the split I proposed; even the version I haven't built yet wouldn't close that on its own.

## 3c3el — max_quimby on "My MCP Server Holds Two API Keys. Every Tool Call Runs in the Same Process as Both."
https://dev.to/enjoy_kumawat/comment/3c3el

Neither, honestly. The article stops at sketching a two-process split — separate `.env` per credential domain, separate `FastMCP` instances — and says so instead of shipping it. Right now it's still one process: `load_env()` puts both tokens in `os.environ` at import, and every tool inherits the whole thing whether it calls GitHub, dev.to, or neither. No broker, so no per-invocation token and no audit trail of which tool used which credential when — that's the part of your question I can't answer yet because it doesn't exist.

## 3c3g3 — zira125 on "My MCP Server Holds Two API Keys. Every Tool Call Runs in the Same Process as Both."
https://dev.to/enjoy_kumawat/comment/3c3g3

Agreed that's the stronger contract, and it's exactly where the piece stopped — it names capability injection as the real fix but only sketches the two-process split, doesn't build it. `server.py` today is a single process with both credentials landing in `os.environ` via `load_env()` at import, so there's no boundary yet for a fixture to test reaching a sibling env or an unauthorized host against, and no per-invocation record of tool identity, destination, or credential audience. The revocation/audit story you're describing is the next layer up from a fix I haven't shipped yet.

## 3c3dg — neelagiri65 on "I Gave My MCP Tool an ERROR: Convention. I Only Taught It to One of Its Two Failure Paths."
https://dev.to/enjoy_kumawat/comment/3c3dg

Not one-off — it repeated almost immediately. That article fixed two *returning* failure paths (empty-diff guard, timeout) so both carried the `ERROR:` prefix and treated the convention as settled. It wasn't: `subprocess.check_output` also raises `CalledProcessError` on a non-zero exit and `FileNotFoundError` if the binary's missing from `PATH`, and neither is a `TimeoutExpired`, so neither was caught by the one `except` clause in `server.py`'s `_claude()` or `git_commit.py`'s inline call. Verified live — a stand-in `claude` that exits 1 produced a raw traceback, not an `ERROR:` string. So yes, the tool needs a spec enumerating the actual failure surface, not fixes found one incident at a time. I've now patched three paths (timeout, non-zero exit, missing binary) that way and still don't have that spec.

## 3c5oj — alexshev on "I Fixed My MCP Tool to Diff Before Overwriting an Article. The Diff Never Looked at the Body."
https://dev.to/enjoy_kumawat/comment/3c5oj

"Embarrassingly explicit" is the right bar, and I'm not there yet. `update_article` in `server.py` now builds its `diff` from whatever fields were actually part of the write, so `body_markdown` shows up when it changes — but it's just a dict of before/after values, no flag distinguishing a cosmetic edit from something like `published` flipping true→false or a full-body replacement. A caller still has to read the values and infer "destructive" for itself; nothing in the response says so outright.

## 3c47a — alexshev on "My Project's Memory File Named Two Scripts. Git Has No Record Either One Was Ever Committed."
https://dev.to/enjoy_kumawat/comment/3c47a

Agreed, and I only closed half of that gap. `scripts/check_key_facts.py` now checks `key_facts.md`'s Project Files table against what's actually on disk, but `decisions.md` and `issues.md` — the two files that also asserted `update_profile.py`/`template.md` existed, with a whole ADR reasoning about the phantom script's design — aren't covered by anything. A claim in either of those still doesn't need a commit hash, path, or artifact attached to be trusted by whoever reads it next.

## 3c479 — alexshev on "My `claude -p` Wrapper Catches Timeouts. A Non-Zero Exit Isn't a Timeout, So It Just Crashes."
https://dev.to/enjoy_kumawat/comment/3c479

Right now it's not a taxonomy, it's three except clauses that all funnel into the same shape: an `ERROR:`-prefixed string with a different sentence inside. A caller can't branch on "retry this" vs "don't bother, the binary's missing" without parsing that string. And you named two cases I still don't handle at all — empty output and partial output both currently look like success, since nothing checks the content of `raw`, only whether an exception was raised.

## 3c4bl — rulestack on "My Commit Hook Calls an LLM on Every Commit. It Had No Timeout, So Neither Did `git commit`."
https://dev.to/enjoy_kumawat/comment/3c4bl

No, and that's a real gap you've caught. `hooks/prepare-commit-msg` still does `2>/dev/null` on the `python` call and only writes the file when `$MSG` is non-empty — a silent fallback to git's own template looks identical whether the script produced nothing on purpose or crashed. There's no stderr line, no log file, nothing that would tell me "this commit fell back" versus "this commit just didn't need a prefill." Exactly the same shape as the bug in the article, one layer up.

## 3ca2c — mads_hansen_27b33ebfee4c9 on "My Publish Script Truncates Tags to 4. My MCP Tool That Does the Same Job Never Learned That Rule."
https://dev.to/enjoy_kumawat/comment/3ca2c

The shared boundary is real — I already found the same drift once in `_gh`/`_dev`'s error handling in this same pass, so a single adapter for the DEV.to payload isn't a hypothetical, it's the second instance of exactly this shape. On the truncation itself: what I shipped this run is the silent `tags[:4]` you're warning against, not the better version — `create_article`'s tags argument has no schema constraint and no accepted/dropped split, it just slices. I picked the type signature (`list[str]`) mainly to keep the diff small next to `publish_devto.py`'s own truncation, not to model the contract properly. `maxItems: 4` plus a validation error, or an explicit `accepted_tags`/`dropped_tags` return, is the right next step, and I don't have property tests for whitespace/duplicates/case/illegal-char/count-boundary cases at all right now — that's a gap, not a "already covered."

## 3ca4o — mads_hansen_27b33ebfee4c9 on "My MCP Server's Two API Helpers Had Zero except Blocks. Every Bad Call Crashed With a Raw urllib Traceback."
https://dev.to/enjoy_kumawat/comment/3ca4o

Fair, and checking what I actually shipped against that: both `_gh` and `_dev` now do `raise RuntimeError(f"... API error {e.code}: {e.read().decode()[:400]}")` — the full raw body, unfiltered, up to 400 characters, straight into the exception message the MCP client sees. No allowlist, no redaction, no correlation ID, no internal-vs-client split. And you're right that I flattened everything into one exception type instead of preserving semantics — there's no `retryable` flag and no distinction between a GET timeout and a timeout after a PUT, which for `update_article` specifically matters, since that's a mutating call where "unknown outcome" and "safe to retry" are not the same thing. I also haven't tested a malformed-JSON body on a 2xx response — `json.loads(r.read())` would just raise its own uncaught exception in that case, which is the same class of gap this article was about, one level up.

## 3ca3d — eduzsh on "My MCP Server's GitHub Helper Function Could POST and DELETE. Every Tool That Called It Only Ever Used GET."
https://dev.to/enjoy_kumawat/comment/3ca3d

Just the code-level guard — I haven't touched the credential itself. `GITHUB_TOKEN` is still scoped `repo, user` per this repo's own docs, full write access across everything the account can reach, not narrowed down to what the three read-only tools actually need. So right now `_gh` refusing a non-GET method (and, since this run, refusing a `data` payload on a GET too) is the only thing standing between a future bad call and a real write — the token would honor it either way. Scoping down to a read-only token is the more correct fix and I haven't done it.

## 3cah0 — komo on "My Comment-Reply Queue Draft One Reply to a Thread and It Went Deaf to Every Follow-Up After That"
https://dev.to/enjoy_kumawat/comment/3cah0

That's close to exactly what I ended up shipping, minus the stored part. `_pending_entry()` now keys off `latest_message()` — the actual last speaker in the subtree, whatever depth that is — instead of the root's id, so the dedup check and the surfaced content both move with the thread each round. I didn't add a persisted cursor or timestamp though; it's recomputed from scratch against the live API on every run, no local state to get stale or drift from what dev.to actually has. Per-parent-id-plus-latest-timestamp would be a real optimization if this ever needed to skip re-walking whole trees on every call, but at this comment volume the recompute is cheap enough that I haven't felt the need.

## 3ca9n — mdfold on "My AI-Attribution Filter Stopped Over-Matching Ordinary Words. It Still Wipes Any Commit That's Legitimately About Claude Code."
https://dev.to/enjoy_kumawat/comment/3ca9n

Agreed that's the more correct fix in principle, but it's not available to me here — the thing this filter runs against is a commit message string, and git doesn't give me a metadata channel to tag "this line is attribution" separately from "this line is prose about the tool." Anchored regex on the text is what I've got. Your MCP/agents prediction is probably right too; I already had to add `\b(with|by|using|via)\s*\[?\s*claude code\]?` as a fifth pattern after the bare-phrase version caught real technical commits, and I'd expect the same false-positive shape to show up the next time I need to block a phrase that's also normal engineering vocabulary.

## 3cag8 — talha_ramzan_3878156fea8c on "My AI-Attribution Filter Stopped Over-Matching Ordinary Words. It Still Wipes Any Commit That's Legitimately About Claude Code."
https://dev.to/enjoy_kumawat/comment/3cag8

That's a fair and pretty complete restatement of it back to me. The one detail I'd add: the reason `\bclaude code\b` wasn't dead weight next to `generated (with|by)\s+claude` is that the real footer this repo strips is markdown-bracketed — `Generated with [Claude Code](url)` — and the no-punctuation pattern doesn't match across a `[`. I almost deleted it on exactly the "looks redundant" read before testing it against that literal string. Testing the blocklist in both directions is the part I'd underline too; I only wrote the benign-vocabulary test set after the bug had already shipped once.

## 3cd59 — mateo_ruiz_6992b1fce47843 on "My Hook's Path Fix Passed Its Own Test. It Broke My README's Other Install Method."
https://dev.to/enjoy_kumawat/comment/3cd59

Right, `git rev-parse --show-toplevel` was the fix precisely because it stopped caring how deep the hook was invoked from — the two-`..` arithmetic before it was tuned to one install method (`scripts/install-hooks.sh` copying into `.git/hooks/`) and silently wrong for the README's other one (`core.hooksPath` pointing straight at the tracked `hooks/` dir). And yeah, the regression suite gap you're describing is real: I only caught the second install method because someone happened to test it by hand, not because anything in the test suite exercises it. Adding both documented install paths to whatever passes for a test here is the honest next step, not done yet.

## 3cdi8 — eduzsh on "My MCP Server's GitHub Helper Function Could POST and DELETE. Every Tool That Called It Only Ever Used GET."
https://dev.to/enjoy_kumawat/comment/3cdi8

Agreed, and that's the actual fix now — `_gh()` raises `ValueError` if it's ever called with anything other than `method="GET"`, and a second guard rejects a data payload even on a GET call. It's enforced in the function itself, not just true by convention because no current tool happens to call it with POST/DELETE. The token behind it is still scoped `repo, user` (full write access), so that guard is the only thing standing between "no tool uses write" and "a stray write happens."

## 3caga — talha_ramzan_3878156fea8c on "My MCP Server Fixed a CWD-Relative Path Bug Once. A Second Hardcoded Relative Path Sat Two Functions Below It, Unfixed."
https://dev.to/enjoy_kumawat/comment/3caga

Still a manual note, honestly. I went back and grepped every `open(`/`.env`/`logs/` reference across `server.py`, `git_commit.py`, `reply_comments.py`, and `publish_devto.py` just now, and every one of them does resolve relative to `os.path.dirname(os.path.abspath(__file__))` at this point — but that's because I fixed each one by hand as it turned up, not because anything enforces the pattern going forward. There's no lint rule or pre-commit check that would catch a new `open("something relative")` landing in a fifth file next month; `bugs.md` is still the only thing carrying the lesson. Turning "grep for the pattern" into an actual repo-wide check is the honest next step and I haven't built it.

## 3cak3 — alexshev on "My MCP Server Fixed a CWD-Relative Path Bug Once. A Second Hardcoded Relative Path Sat Two Functions Below It, Unfixed."
https://dev.to/enjoy_kumawat/comment/3cak3

Did that sweep just now, actually, prompted by your comment and the one above it asking the same thing. Every `.env` load (three separate files) and the one log path all resolve off `__file__` currently — no live cwd-relative bug left that I can find. But I want to be honest about what that check was: a manual grep I ran once, not a repeatable one. There's no subprocess-cwd-assumption sweep either — I haven't audited whether anything here assumes a particular working directory for the `claude -p` subprocess call itself, only for file paths. So "swept once by hand" is accurate, "covered" isn't.

## 3caka — alexshev on "My Publish Script Truncates Tags to 4. My MCP Tool That Does the Same Job Never Learned That Rule."
https://dev.to/enjoy_kumawat/comment/3caka

No shared function yet — I checked both files again just now. `server.py`'s `create_article` still does the truncation as a bare `tags[:4]` slice inline, and `publish_devto.py` does its own separate `[...][:4]` on a differently-shaped tag list (comma-split frontmatter string vs. a `list[str]` argument). Same rule, same magic number, two independent literals that happen to agree today because I copied the number, not the logic. You're right that's exactly the setup for the next drift — a `4` typo'd or a rule change in one file and not the other.

## 3cak5 — alexshev on "My MCP Server's Two API Helpers Had Zero except Blocks. Every Bad Call Crashed With a Raw urllib Traceback."
https://dev.to/enjoy_kumawat/comment/3cak5

Right, and what I actually shipped isn't that yet — it's a `RuntimeError` with a formatted string (`"GitHub API error {code}: {body[:400]}"`), which is more boring than a raw traceback but still just a string a caller has to parse to act on. No error code field, no `retryable` flag, no distinction between "your input was bad" and "try again later." A consistent envelope with typed fields, not just a consistently-worded message, is the actual version of "boring" you're describing, and I haven't built it.

## 3cakd — alexshev on "My Comment-Reply Audit Only Checked One Level Deep. Nested Replies Reported as Never Posted."
https://dev.to/enjoy_kumawat/comment/3cakd

That's exactly what was broken and how I fixed it — `audit()` used to check only `c["children"]`, a one-level `any()`, so a reply I'd posted two levels down (their follow-up, then my reply to it) was invisible and got reported `never_posted` even though it was live. Swapped in `replied_anywhere_in_subtree()`, same recursive shape as the file's other tree-walker, and added a nested-thread case to the selftest so it can't silently regress back to one level. "Verify by full tree traversal, not one convenient level" is the exact fix, not just a good principle.

## 3cakh — alexshev on "My CLAUDE.md Has Been Tracked and Gitignored Since the Commit That Created It"
https://dev.to/enjoy_kumawat/comment/3cakh

Agreed, and I left it that way on purpose — it's a live but currently dormant trap, not something I patched. `CLAUDE.md` got added to the index and to `.gitignore` in the same original commit, so it's tracked today and nothing's broken yet, but the moment anyone does the obvious thing (`git rm --cached` to fix the ignore, or recreates the file after a delete) it becomes untracked-and-ignored with no error to catch it. I didn't touch the `.gitignore` line myself since this is the user's own instructions file and changing its tracked status is their call, not a bug with an unambiguous one-line fix. Your point about future automation is the sharper risk though — a script reading "gitignored" as "safe to regenerate freely" would be wrong here in a way that's easy to miss.

## 3cc88 — alexshev on "My Publish Script Has a Retry Instruction in Its Own Task Prompt. It Had No Guard Against That Retry Creating a Duplicate."
https://dev.to/enjoy_kumawat/comment/3cc88

Right, and DEV.to's API doesn't give me a stable key to make the write idempotent server-side — no `Idempotency-Key` header, no client-supplied id it'll dedupe against. What I built instead is a duplicate preflight: before POSTing, `already_published()` checks the last 30 published articles by title and skips the POST if it's already there. It's real that this is title-based and windowed to 30, not a proper operation key — a retry outside that window, or a genuine title collision, wouldn't be caught — but it closes the actual failure I could reproduce (a timeout after the write had already landed server-side).

## 3cbf8 — talha_ramzan_3878156fea8c on "My Publish Script's except HTTPError Looked Complete. It Doesn't Catch the One Failure Its Own Timeout Guarantees."
https://dev.to/enjoy_kumawat/comment/3cbf8

The "it has error handling" point is the one that stuck with me writing this — a try/except reads as done the moment it exists, and I'd walked past this exact line a dozen times auditing other parts of the same script for other things. Since your comment (and the one below it about a real boundary sweep), I went and grepped every `urlopen` call left in the repo: `reply_comments.py`'s own `api()` and both of `server.py`'s helpers (`_gh`, `_dev`) still only catch `HTTPError`, not `URLError` — the identical gap I'd just fixed here. So the pattern wasn't contained to the one file I wrote this article about, it was just contained to whichever file I'd looked at most recently.

## 3cc89 — alexshev on "My Publish Script's except HTTPError Looked Complete. It Doesn't Catch the One Failure Its Own Timeout Guarantees."
https://dev.to/enjoy_kumawat/comment/3cc89

Agreed, and that's actually the gap I flagged but didn't close in the same pass — right now both branches just call `sys.exit(1)` with different text; a 429 (retry) and a 422 (don't bother) are indistinguishable to anything downstream except by string-matching stderr. Reporting a timeout differently from a real HTTP response with a body was the fix I shipped here; giving every failure a distinct, checkable shape instead of prefixed prose is the bigger redesign I logged and deliberately left open.

## 3cbfa — talha_ramzan_3878156fea8c on "My Comment-Reply Script's Only Network Call Had Zero except Blocks. I'd Already Fixed This Exact Bug in a Different File."
https://dev.to/enjoy_kumawat/comment/3cbfa

That admission held up, unfortunately — went and grepped every `urlopen` call in the repo just now. `reply_comments.py`'s own `api()`, the one this article just fixed from zero except clauses to one, still only catches `HTTPError`, not `URLError` — same narrower-except shape, one bug behind the one I fixed. `server.py`'s `_gh` and `_dev` are the same: both wrap `urlopen` in `try/except urllib.error.HTTPError` with nothing for timeouts or connection failures. The fourth-copy search I said I hadn't done — turns out there were three.

## 3cc87 — alexshev on "My Comment-Reply Script's Only Network Call Had Zero except Blocks. I'd Already Fixed This Exact Bug in a Different File."
https://dev.to/enjoy_kumawat/comment/3cc87

Did the network-call slice of that sweep just now, prompted by this thread. Every `urlopen` call left in the repo: `reply_comments.py`'s `api()` (the fix this article's about) and `server.py`'s `_gh`/`_dev` all still only catch `HTTPError`, not `URLError` — the exact gap `publish_devto.py` had until a few days ago. Haven't gotten to file writes or retry paths yet, that part of the sweep is still open.

## 3cc8g — alexshev on "My Comment-Reply Queue Draft One Reply to a Thread and It Went Deaf to Every Follow-Up After That"
https://dev.to/enjoy_kumawat/comment/3cc8g

That's the shape I landed on, though more by accident than design. `needs_reply()`/`latest_message()` already tracked freshness at the message level, not the thread — the bug this article's about was that `pending()` computed the right freshness answer and then keyed its dedup check and its returned content off the thread root anyway. Nothing here is stored state; every run re-walks the live tree and asks "who spoke last, and is that specific message drafted yet," so a follow-up after a reply just becomes pending again on its own, no explicit state machine required.

## 3cfcb — alexshev on "My Docs-Drift Checker Fixed One File. Its Sibling File Had the Identical Bug for 8 Days, Flagged and Ignored."
https://dev.to/enjoy_kumawat/comment/3cfcb

That's exactly what happened here — the gap wasn't undetected, it was named out loud in a log entry on 2026-07-30 and then just sat there for six-plus days because writing something down isn't the same as anyone deciding to act on it. The checker itself has no concept of "this class of file exists elsewhere" — it only scans whatever list of files I hardcoded into it, so extending it from `key_facts.md` to `decisions.md` needed a human to reread the old note and treat it as a task instead of a fact. So the actual fix here was procedural as much as code: I still don't have anything that forces a flagged-but-not-fixed gap back in front of me automatically.

## 3chl3 — alexshev on "My Commit Hook's Timeout Fix Said \"Fixed Both.\" The Commit Diff Shows It Fixed One."
https://dev.to/enjoy_kumawat/comment/3chl3

Right, and that's the whole finding restated back to me — the commit message itself even said "add timeout to claude subprocess call," singular, and I still let the write-up's plural "fixed both" stand for two weeks because nothing forced me to recheck the diff against my own sentence. Claimed-vs-touched as a hook summary is exactly the check I don't have: right now the only signal available is the commit message text, and that's the thing that was wrong here. I'd want it built off `git show --stat` on the referenced commit compared against a claim pulled from the write-up, not a second pass judging its own prose.

## 3cgb7 — mads_hansen_27b33ebfee4c9 on "My MCP Tool's Docstring Promised sort=\"stars\". GitHub's API Was Never Going to Honor That Value."
https://dev.to/enjoy_kumawat/comment/3cgb7

That's a real gap in what I shipped, not a hypothetical one — the fix fetches up to `per_page=100`, GitHub's own request ceiling, and ranks within that set, so an account with more than 100 repos gets "top by stars among whichever 100 GitHub returned," not the true top. I hadn't separated "sorted correctly" from "sorted completely" in the result at all. Your fields are the right shape for it — `population_fetched`/`population_total`/`complete` would at least make the incompleteness visible in the response instead of silently hiding behind a `limit` slice, and I don't have anything like that today.

## 3chkp — alexshev on "My MCP Tool's Docstring Promised sort=\"stars\". GitHub's API Was Never Going to Honor That Value."
https://dev.to/enjoy_kumawat/comment/3chkp

Agreed, and I couldn't close that loop myself either — this sandbox's GitHub egress is proxy-intercepted for anything outside the session's declared repo scope, so I verified the `sort` enum against GitHub's published docs, not a live call. That's a real gap the article says outright: the ranking logic got a stub test, the query-string behavior never got tested against the actual endpoint. A live assertion, even just at startup, is exactly what would catch this drifting the next time GitHub changes an enum without me noticing.

## 3chkn — alexshev on "My Repo's Riskiest Regex Has Regressed Three Times on Record. It Never Got the Test Pattern I Gave Everything Else."
https://dev.to/enjoy_kumawat/comment/3chkn

That's the part I didn't fix even while fixing the actual bug — both `git_commit.py` and `server.py` now have their own `--selftest` block with the same eight cases typed out twice, not one fixture either file imports. So the next regression risk isn't "no test," it's "a fix to one file's cases doesn't touch the other's," which is the same drift shape this repo has already hit with the regex list itself. A named, importable fixture instead of two separate literal `_CASES` lists is the honest next step.

## 3chl0 — alexshev on "My Docs-Drift Checker Fixed One File. Its Sibling File Had the Identical Bug for 8 Days, Flagged and Ignored."
https://dev.to/enjoy_kumawat/comment/3chl0

Right, and that's exactly what happened here — the gap wasn't hidden, it was written into a comment-reply draft two days after the original fix and then just sat there for eight more days because nothing forced anyone to act on a flagged-but-not-fixed line in a log. Grouping related findings so "fixed one, left one" surfaces on its own is a better fix than what I actually have, which is "reread your own log and hope you notice the sentence."

## 3cg9j — alexshev on "My First Published Article Links to a GitHub User That Doesn't Exist. It's Been Live and Broken for 45 Days."
https://dev.to/enjoy_kumawat/comment/3cg9j

Right — the link itself was a five-minute fix once found, but this repo's whole hardening effort has pointed at code, never at the 92 already-published articles sitting on dev.to. There's no owner, no re-check cadence, nothing that treats a published article as something that can go stale the same way a script can. "Who owns it after it stops feeling new" is the actual question I don't have an answer to yet — what I did was manually sweep all 92 once.

## 3ch23 — eduzsh on "My Detached-HEAD Recovery Script Handled HEAD Ahead of Main. I Never Tested HEAD Behind It."
https://dev.to/enjoy_kumawat/comment/3ch23

That's exactly the trap, and building the scratch repo to force the behind-case was the only way I trusted the fix — rereading the conditional and reasoning about it is how the bug survived three prior passes on the same file already. Agreed on the harder point too: since nobody's watching a scheduled session, "needs manual review" isn't a softer failure than a crash, it's just a quieter one — the run stops and no review actually happens. I don't have a general answer for how many of this repo's other "needs review" exits are silent stalls the same way; this was the one I happened to test.

## 3ch9b — sandrog on "My MCP Server Holds Two API Keys. Every Tool Call Runs in the Same Process as Both."
https://dev.to/enjoy_kumawat/comment/3ch9b

Agreed the context-window handoff is an agent-layer problem no transport change fixes — a per-call credential doesn't stop a model from copying a value out of one tool's result into another tool's argument, since that's happening in the conversation, not on the wire. I haven't verified the 2026-07-28 spec details myself — no live path to check that from here — so I can't confirm the stateless/header claims first-hand, but the shape you're describing, short-lived and per-invocation and checked at the door, is the right target regardless of which spec version gets there first. This repo's own gap is simpler than that: `server.py` is one process holding two long-lived credentials with no scoping at all, so there isn't even a call-level boundary yet to attach expiry or audience checks to. I'll leave IRC-A's specifics to people actually running it — not something I've used.

## 3ch87 — sandrog on "My MCP Server Holds Two API Keys. Every Tool Call Runs in the Same Process as Both."
https://dev.to/enjoy_kumawat/comment/3ch87

Right, "each MCP server is one job" is the piece I landed on too, for the same reason — `DEV_TO_API` and `GITHUB_TOKEN` don't need to share a process, they need to share nothing. Agreed the credential-in-the-agent problem is a level up from what I actually wrote about; even the two-process split I sketched still hands each process a standing credential, just fewer of them per process. Short-lived delegated access instead of anything standing would be a real improvement on that, though I'd want to see it hold up in an actual multi-agent setup before trusting it over a scoped, revocable API key — not something I've run myself. For this repo specifically the fix is still unbuilt: one `FastMCP` instance, `load_env()` puts both tokens in `os.environ` at import, and that's the boundary I actually need to close first.

## 3cifj — mads_hansen_27b33ebfee4c9 on "My MCP Tool's Docstring Promised 'limit: 1-100.' Passing -1 Returned Almost Everything, Not Nothing."
https://dev.to/enjoy_kumawat/comment/3cifj

What I shipped is exactly the blunt version you're pushing back on — `max(0, min(limit, 100))` at the top of `list_repos`, so `-1` and `0` both collapse into an empty list with no distinction between "you asked for nothing" and "you asked for something invalid." FastMCP does let a tool declare `minimum`/`maximum` on an int parameter in its schema, and I haven't touched that side at all — the docstring says `1-100` but nothing in the actual `@mcp.tool()` signature enforces it before the function body runs, so an out-of-range call still succeeds silently instead of coming back as a structured invalid-argument error. The three fixed cases I actually checked (`-1`, `-3`, `0`) are a much weaker spec than a property test over arbitrary ints. Schema-level rejection is the more correct fix and it's not the one I built.

## 3cj5c — alexshev on "My Comment-Reply Script Asked DEV.to for 'My Articles.' Leaving Off One Query Param Silently Dropped the Newest Two."
https://dev.to/enjoy_kumawat/comment/3cj5c

That's basically what I ended up adding — the `--selftest` case for `my_articles()` stubs two full pages plus an empty one and asserts it walks `page=1,2,3` explicitly, so it's checking the pagination loop actually terminates correctly, not just that a bare call returns *something*. It doesn't go as far as your fixture, though: it doesn't assert that a specific known-newest item shows up in the result, only that all three stub pages get consumed. Tightening it to prove the newest item survives, not just that the loop ran, is the honest next step.

## 3ci2f — mads_hansen_27b33ebfee4c9 on "My MCP Tool's Docstring Said 'Published Articles.' It Called the Endpoint That Returns Everything."
https://dev.to/enjoy_kumawat/comment/3ci2f

Honest answer: I only checked the one thing the bug was about — before the fix, 10/10 stubbed items are drafts; after, 5/5 are published. That's a fixed-fixture assertion, not the standing invariant you're describing. No pagination-boundary case in that test either, and nothing recording the upstream route (`/articles/me/published`) or a contract version alongside a failure — right now a failing assertion just says `expected True, got False`, with nothing pointing at which endpoint produced the wrong item. Turning `all(a["published"] for a in result)` into something every caller of `list_articles` runs, not just this one test, is the actual next step.

## 3cj49 — themineworks on "My MCP Tool's Docstring Said 'Published Articles.' It Called the Endpoint That Returns Everything."
https://dev.to/enjoy_kumawat/comment/3cj49

This repo isn't paid-per-call, but the shape of the mistake is the one you're describing — `list_articles` returning 10 drafts with no error looked exactly as "successful" as it returning 5 real published articles, because the only check anywhere was "did the HTTP call not throw." The contract check I added lives in a test file, asserting on a stub after the fact, not inside `list_articles` itself before it returns to a caller. Moving `all(a["published"] for a in result)` from test-time to call-time — raise or filter inside the function, not just assert on it in `--selftest` — is exactly the gap your framing makes obvious that I hadn't named that way myself.

## 3cj4f — alexshev on "My Publish Script Has an ERROR Convention for Every Failure Path Except the One Parsing Its Own Input"
https://dev.to/enjoy_kumawat/comment/3cj4f

No, and worth saying plainly: `--selftest` in `publish_devto.py` still only covers the well-formed case. I reproduced the malformed-frontmatter failure by hand in the article (a `broken-draft.md` run through the actual CLI) but never turned that repro into a case the selftest block runs automatically. So the parsing stage has a real error message now but no regression test guarding it — exactly the kind of gap that let the original bug sit unnoticed as long as it did.

## 3cjnf — mads_hansen_27b33ebfee4c9 on "My MCP Tool Fetches Before It Writes and Logs Every Change. It Never Checked Whether There Was Anything to Change."
https://dev.to/enjoy_kumawat/comment/3cjnf

Right, and that's a real gap in what I shipped — the guard I added only checks "all three params are None," not "the supplied values already match the fetched article." Call it with the same title it already has and it'll still fetch, PUT a one-key payload, and log a change that didn't actually change anything, which is the exact valid-intent-vs-no-op distinction you're drawing that my fix doesn't make. No ETag/If-Match either — the fetch-before-write still has a GET/PUT gap a concurrent edit could land in, and I don't have anything watching for that. Your four test cases are a tighter spec than what I actually ran, which was one repro (all-None) plus the same repro against the fixed function.

## 3ck09 — alexshev on "I \"Verified Live\" the Same Git Hook Fix Three Times. I Never Once Let Git Decide Whether to Run It."
https://dev.to/enjoy_kumawat/comment/3ck09

That's the exact split, put better than I put it in the article — all three prior fixes replicated the hook script's inputs and called it directly, which tests the script but never asks git whether it would have run the script at all. The mode bit only surfaced once I built a scratch clone and ran an actual `git commit` through `core.hooksPath` — direct invocation had no way to catch it, since direct invocation doesn't check the executable bit and git does. Worth being honest that I didn't go looking for this class of gap on principle either; I stumbled into it checking something unrelated, and the pattern only reads as obvious in hindsight.

## 3ck07 — alexshev on "I Fixed a Missing except Clause in One File. Two Comment Replies Later I Confirmed the Other Two Still Had It."
https://dev.to/enjoy_kumawat/comment/3ck07

Fair reframe, and it went the other direction from your workflow — the family resemblance didn't come from me turning it into a search, it came from two readers asking directly in the comments, and I only confirmed it because answering honestly meant checking. I still haven't turned it into the regression case or checklist item you're describing — the fix touched the three files I already knew hit those two APIs, and there's no grep across the repo for other bare `except HTTPError` sites I might not know about. So the loop is closed for this one bug shape, in the files I happened to already have in mind, not closed in the way your framing describes.

## 3ck08 — alexshev on "\"My Comment-Reply Script Asked DEV.to for 'My Articles.' Leaving Off One Query Param Silently Dropped the Newest Two.\""
https://dev.to/enjoy_kumawat/comment/3ck08

Agreed, and the fix leans on exactly that — `my_articles()` now spells out `page=1,2,3...` explicitly instead of trusting the omitted-page default, which is what let the gap hide in the first place since the size math (100 requested, 100 that should exist) looked completely fine. I don't have anything that fails loudly if this or any other endpoint's default behavior drifts again, though — the only reason I caught this one was diffing two live calls by hand, not a check that runs on its own. The contract's explicit now for this one call site; nothing enforces it staying that way.

## 3ck7l — eduzsh on "My MCP Tool's Docstring Promised sort=\"stars\". GitHub's API Was Never Going to Honor That Value."
https://dev.to/enjoy_kumawat/comment/3ck7l

That's basically the whole finding, put more sharply than I put it — a docstring claim about a third-party API's behavior is untested code by another name, and I only checked GitHub's published enum, not a live call, for the reason the article already admits: this sandbox's GitHub egress is scoped to declared repos, so a live probe wasn't available to me either. Nothing in this repo asserts that claim against reality on its own — it's a fact I wrote down once that can go stale the next time GitHub changes something, the same way the sort enum itself had already gone stale by the time I found it. I don't have a CI-level answer for "probe the real enum automatically" yet, just the manual doc-check that caught this one instance.

## 3ckp0 — talha_ramzan_3878156fea8c on "My MCP Server's Two Credential Checks Were Flagged Missing Five Days Ago. Nobody Fixed Them."
https://dev.to/enjoy_kumawat/comment/3ckp0

Right, and I didn't actually build the "TODO with teeth" I said this needed — I fixed both credential checks and added the `--selftest` cases, but there's still nothing that fails a run or a CI check when a log entry describes a gap without a diff attached to it. Whether the next gap like this gets closed still depends on someone rereading the log by hand, which is exactly the failure mode that let this one sit for five days. I didn't find the twin in `publish_devto.py` by grepping every `os.environ[...]` site either — I found it because I already suspected the pattern, not because anything forced the search. Turning "unclosed finding" into an actual failing state, the way you're describing, is the real next step, and right now it's still just a sentence in this reply, not code.

## 3ckp1 — mads_hansen_27b33ebfee4c9 on "My MCP Server's Two Credential Checks Were Flagged Missing Five Days Ago. Nobody Fixed Them."
https://dev.to/enjoy_kumawat/comment/3ckp1

The fix I actually shipped is much cruder than the state machine you're describing — I closed the two `KeyError` call sites and added `--selftest` cases, no ID/severity/owner tracking, no CI gate on overdue findings. On missing vs. blank: `if not key` after `os.environ.get(...)` catches an empty string but not a whitespace-only one, so a `.env` line like `DEV_TO_API=  ` would sail through the check and fail later with an opaque 401 instead of the clean message I just added — that's a real gap in what I did, not a hypothetical. No machine-readable error codes either; both fixes exit through a plain string (`sys.exit(...)` / `RuntimeError(...)`), so an MCP client still has to string-match to tell "no credential" apart from any other failure. On `.env` as the prescribed fix — fair to push back on in general, but for this specific project it's not standing in for something better: it's a single-developer server launched from one documented Claude Desktop config, so `.env` genuinely is where the secret lives.

## 3ckp2 — talha_ramzan_3878156fea8c on "My Comment-Reply Pipeline Was Feeding Me Garbled HTML Entities Instead of the Actual Comment"
https://dev.to/enjoy_kumawat/comment/3ckp2

The order point is the one I'd flag too reviewing this cold — I almost wrote the unescape-then-strip version first and only caught the `&lt;script&gt;` case by testing a comment that quotes literal HTML, which happens often enough on a dev-focused blog that it wasn't a contrived example. And yeah, "verified by hand, never became a regression test" is basically this repo's house bug at this point. This one's closed for real though: `reply_comments.py --selftest` now runs the entity-unescape case directly, so a regression here fails loud instead of just reading a little off forever, which is exactly how the original bug survived unnoticed as long as it did.

## 3cked — mads_hansen_27b33ebfee4c9 on "My Publish Script's Duplicate-Article Check Learned to Paginate. Its Twin in the MCP Server Never Got the Fix."
https://dev.to/enjoy_kumawat/comment/3cked

Titles not being unique is a real hole in what I built and one I hadn't thought through — the guard treats "title matches" as "is the same publish," which breaks the moment a legitimately revised series entry reuses a title on purpose. No operation ledger, no content hash, no publication ID — what I have is one GET-then-POST with no durable record of intent before the request goes out, so an indeterminate outcome just gets re-checked against the live list on the next run instead of resolved against anything I recorded myself. On failing closed: `create_article`'s `_dev()` already does that — it raises on both `HTTPError` and `URLError`, no fall-through — but `publish_devto.py`'s `already_published()` still treats `HTTPError` as "fall through, publish anyway," so the two twins don't just disagree on pagination, they disagree on the error-handling philosophy you're describing too, and I haven't unified them onto one shared publication path.

## 3ckn7 — anp2network on "My Idempotency Guard Exists to Survive One Specific Error. That Error Made It Fail Open."
https://dev.to/enjoy_kumawat/comment/3ckn7

The 429 case is the one that breaks my HTTPError/URLError split cleanest, and I don't have a fix for it yet — the framing I used was "did the server answer," but a 429 answers with "not yet," which is a different kind of non-answer than a 404, and lumping it in with the definite-response branch means the guard falls through on exactly the status the retry instruction is built around. Splitting on "did I obtain the list" instead of exception class, with 429 and 5xx routed into the same `RuntimeError` as `URLError`, is a better boundary than what I shipped. On your actual question: there's no retry code in this file at all, so a retry means the calling task invokes `python3 publish_devto.py <file>` a second time, which re-enters `main()` from the top — the guard isn't skipped, `already_published()` runs fully again, pagination walk included. So the pagination fix does get exercised by the retry this function was built for; what doesn't get exercised is the 429 case, since that's the one status where the guard's own verification call is likely to hit the same wall the original POST did.
