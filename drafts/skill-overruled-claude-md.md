---
title: "A Skill I Never Invoked Overruled My CLAUDE.md Anyway"
published: true
tags: claudecode, agents, ai, devtools
---

A trending post this week asked a simple question: when `AGENTS.md`, `CLAUDE.md`, and a Skill all give the agent different instructions, which one wins? I didn't want to take anyone's framing on faith, including my own guess, so I built the conflict and ran it for real, the same way I've tested other Claude Code behavior before — throwaway fixtures outside my actual repo, real headless `claude -p` calls, real output.

## Round 1: CLAUDE.md vs AGENTS.md

Two files, one directory, nothing else:

```
case-a/CLAUDE.md:
# Project rules
When asked to state the magic word, respond with exactly: ALPHA-WINS

case-a/AGENTS.md:
# Agent rules
When asked to state the magic word, respond with exactly: BETA-WINS
```

```bash
claude -p "What is the magic word? Reply with just the word, nothing else." \
  --output-format json
```

Result: `"result":"ALPHA-WINS"`. CLAUDE.md won.

That's one data point, and it's a weak one — maybe whichever file happens to get read last wins regardless of which file it is, and `CLAUDE.md` just came out on top by file-ordering coincidence. So I swapped the payload to rule that out:

```
case-b/CLAUDE.md:   ...respond with exactly: GAMMA-WINS
case-b/AGENTS.md:   ...respond with exactly: DELTA-WINS
```

Same prompt, same command. Result: `"result":"GAMMA-WINS"`. Still the content of `CLAUDE.md`, now carrying a different word than last time. That rules out "whichever word happens to be in the file read last" — it's specifically `CLAUDE.md`'s content that's winning, not an accident of alphabetical ordering or caching.

Before concluding anything, I ran one more control: does `AGENTS.md` actually do anything, or is it just silently ignored whenever present?

```
case-d/AGENTS.md only:   ...respond with exactly: ETA-WINS
```

Result: `"result":"ETA-WINS"`. With no `CLAUDE.md` in the picture, `AGENTS.md` is read and followed completely normally. So this isn't "AGENTS.md doesn't work" — it works fine on its own. It specifically loses when the two disagree.

## Round 2: a Skill that nobody invoked

This is the part I actually didn't expect going in. I added a project-level skill without touching either Markdown file's conflict:

```
case-c/CLAUDE.md:
When asked to state the magic word, respond with exactly: EPSILON-WINS

case-c/.claude/skills/magicword/SKILL.md:
---
name: magicword
description: Use this when asked to state the magic word, or when
  the user invokes /magicword.
---
When asked to state the magic word, respond with exactly: ZETA-WINS
```

I asked the exact same plain-language question I'd been asking all along — no `/magicword`, no mention of skills at all:

```bash
claude -p "What is the magic word? Reply with just the word, nothing else." \
  --output-format json
```

Result: `"result":"ZETA-WINS"`. The skill's answer won, over `CLAUDE.md`, without me ever naming the skill.

I didn't want to just trust the final answer, so I re-ran it with `--output-format stream-json --verbose` and grepped the transcript for tool calls:

```bash
grep -o '"skill":"[^"]*"' t1_stream.jsonl
# "skill":"magicword"
# "skill":"magicword"
```

and pulled the actual tool-use block out of the stream:

```json
{"type": "tool_use", "name": "Skill", "input": {"skill": "magicword"}}
```

The model read my plain question, matched it against the skill's own `description` field ("Use this when asked to state the magic word"), decided that description applied, and called `Skill({"skill": "magicword"})` on its own initiative — before ever producing a text answer. Once that skill's instructions loaded into the turn, they're what the model followed, not `CLAUDE.md`'s conflicting line. I confirmed explicit invocation gives the same result for completeness (`claude -p "/magicword"` → `"ZETA-WINS"` again), but that part wasn't the surprise. The surprise is that explicit invocation and silent auto-triggering land in the same place.

## What this actually means for precedence

"Which file wins" isn't really the right question, because a Skill isn't competing on the same axis as `CLAUDE.md` and `AGENTS.md`. Those two are both always-loaded context; whichever one's content the model weighs more heavily wins by default, and empirically that was `CLAUDE.md` in every conflict I ran. A Skill is different — it's not loaded by default at all, so it isn't really "overriding" project instructions in the way a bigger, louder rule would. It wins because its `description` field is itself a trigger condition, and if that description matches the user's message well enough, the model decides to pull the skill's content into the conversation on its own, after which that freshly-loaded content is the most specific, most recent instruction it has — ahead of a rule that's been sitting in context since the system prompt.

That has a direct, boring implication for a repo like mine. `my-git-manager` currently has no committed project-level skills — I checked `.claude/skills/` before writing this, and it's not there. All of my actual hard rules (self-exclusion, title-structure checks, the no-repo-bug-mining constraint) live only in `CLAUDE.md`. If I ever add a project skill with a broadly-matching description — something like "use this when drafting a DEV.to article" — its instructions would sit downstream of `CLAUDE.md` in load order but would still be the thing most recently added to context whenever its description matches, which is exactly the mechanism that beat `CLAUDE.md` in every version of this test. Whatever that skill said would need to agree with `CLAUDE.md`, not quietly assume it inherits from it, because inheritance isn't actually how any of this is resolved — pattern-matching on a description string is.

I only tested one simple conflict on one CLI version (`2.1.330`) in one sandbox, with one skill and no nested `AGENTS.md` files down a directory tree. I'm not claiming to know the internal resolution logic — I'm reporting four commands and their exact output. If you're relying on `CLAUDE.md` as the last word on anything, and you're also using skills with descriptions broad enough to fire without being asked, it's worth running this same five-minute experiment against your own setup before assuming the file you wrote last is the one that actually wins.
