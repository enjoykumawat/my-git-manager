---
title: "The Attribution Filter That Survived Four Hardening Passes Still Doesn't Know the Name My Own CLAUDE.md Uses"
published: true
tags: python, security, debugging, devtools
---

Every commit message my setup generates — whether from a standalone `git_commit.py` script or from an MCP tool a client calls directly — goes through the same regex before it's allowed to land: `_STRIP_RE`, a filter whose entire job is making sure nothing in the message credits an AI. The system prompt handed to the model already says "no co-author lines, no signatures, no AI references." The regex is the net underneath, for when the model doesn't fully comply.

That net has been rebuilt four times since I first shipped it. Each time, the fix came from finding a real phrasing that slipped through, not from imagining one. I went back through all four passes this week and ran every phrasing they were ever built to catch through the current version at once — and found a fifth gap, sitting in the one place none of the previous four thought to look: my own project's standing instructions.

## Four passes, four different failure shapes

The filter started as a plain substring check: if the generated text contained `co-authored-by`, `claude code`, `written by`, or a handful of other fragments, strip the line. That shipped in commit `1f8808c`, the same commit that added the no-attribution instruction to the system prompt in the first place.

Four days later, the first real bug showed up. The substring check didn't know about word boundaries, so it erased any commit message that legitimately mentioned "llm", "claude", or "anthropic" as an ordinary technical word — `"fix: retry llm calls on 429 with backoff"` came out as an empty string. That fix was proposed on the day it was found and then sat unshipped for four more days before someone actually rewrote the substring tuple into a word-boundary-anchored regex.

A third pass found the regex still only recognized the exact trailer spelling `Co-Authored-By:` — a model that wrote `Signed-off-by: Claude <noreply@anthropic.com>` or `Reviewed-by: Claude` instead sailed through untouched, because every pattern up to that point was shaped around the one incident this project had actually had. That pass added a trailer-value pattern: match the label (`signed-off-by`, `reviewed-by`, `acked-by`, and five others) followed by a value drawn from a short list — `claude`, `chatgpt`, `copilot`, `anthropic`, `ai`, `llm`.

Here's that pattern as it's shipped in both files for the last three months:

```python
r"\b(signed-off-by|reviewed-by|acked-by|tested-by|reported-by"
r"|co-developed-by|assisted-by)\s*:\s*"
r"(claude|chatgpt|copilot|anthropic|ai|llm)\b",
```

Every one of those six names in the second group came from a real line this repo had actually produced or tested against. Nobody built it as "match any AI tool name" — it was built as "match any AI tool name that has bitten us so far," which is a narrower claim than it looks like at a glance.

## Checking it against my own CLAUDE.md, not against new guesses

I didn't want a fifth pass to just be "I thought of another name." So instead of guessing, I checked the regex against the one AI tool this exact project's own standing instructions already name. `CLAUDE.md`, the file every session in this repo reads before doing anything, has a line near the bottom: `after your work done codex will review what you done`. Two earlier articles on this account cited that line as a premise and a third actually ran `git log --all --format='%B' | grep -ic codex` against this repo's full history and found zero matches — meaning if Codex has ever reviewed a commit here, it's left no trace a human or an agent could check from inside the repo.

None of those three posts asked the next question: if Codex *did* leave a trailer the way the system prompt worries Claude might, would this filter even catch it? I ran the actual regex against it, not a mockup:

```python
>>> _STRIP_RE.search("Reviewed-by: Codex")
# None
>>> _STRIP_RE.search("Signed-off-by: Codex <codex@openai.com>")
# None
>>> _STRIP_RE.search("Assisted-by: Gemini")
# None
```

All three return `None` — unmatched, unstripped. `"codex"` and `"gemini"` aren't in the six-name alternation, so a trailer naming either one passes through exactly the way `Signed-off-by: Claude` used to, before the third hardening pass closed that gap for the other six names. The exact bug the 2026-08-12 fix diagnosed and fixed — "the pattern list only ever covered the one spelling this project happened to have an incident with" — was still true one level down, for the value half of the same pattern, and for the one name this repo's own instructions actually mention.

## The fix is the same shape as the last one, which is the point

```python
r"\b(signed-off-by|reviewed-by|acked-by|tested-by|reported-by"
r"|co-developed-by|assisted-by)\s*:\s*"
r"(claude|chatgpt|copilot|anthropic|ai|llm|codex|gemini)\b",
```

Two names added, in both `server.py` and `git_commit.py` — the two files have carried an identical copy of this list since the trailer pattern was first added, a duplication I've flagged before as worth extracting into a shared module and still haven't, since every fix so far has been small enough that keeping two copies in sync by hand hasn't actually cost anything yet. Re-running the same three lines against the patched regex strips all three. A fourth check matters just as much as the fix itself: a plain technical sentence that happens to use the word "codex" has to survive untouched, the same discipline every prior pass on this filter has had to prove —

```python
>>> _STRIP_RE.search("fix: codex flagged this off-by-one, fixed per its review")
# None
```

— still `None`, correctly. I added all four cases — the two bypasses, the one-more-name bypass, and the benign-overlap survivor — to both files' `--selftest` blocks rather than leaving them as a one-off terminal check, the same gap a previous audit of this exact file found in two of its own earlier fixes (verified once, never made permanent).

## What four passes on one regex actually teaches

Every fix to this filter so far has been reactive in the same specific way: find a phrasing the regex missed, add it, move on. That's a reasonable way to harden a blocklist, and it's also guaranteed to keep missing anything that hasn't happened yet. The one source of "names that could plausibly show up here" that was sitting the whole time, unchecked, wasn't a future incident — it was a sentence already written down in this project's own configuration, naming a specific other AI tool as part of its workflow. A blocklist regex doesn't know about a project's own documentation unless someone deliberately checks it against that documentation, and across four hardening passes and three separate articles citing that exact CLAUDE.md line for other reasons, nobody had.

That's a cheap check to add to any similar filter: before shipping the next version of a name-based blocklist, grep the project's own README, config, or standing instructions for tool names it already mentions, and test the filter against each one explicitly. It won't catch names nobody has thought of yet. It will catch the ones already sitting in your own files.
