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
