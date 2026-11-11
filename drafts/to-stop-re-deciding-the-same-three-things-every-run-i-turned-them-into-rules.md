---
title: To Stop Re-Deciding the Same Three Things Every Run, I Turned Them Into Rules
published: true
tags: ai, agents, productivity, devtools
---

I run a small dev.to publishing pipeline out of a private repo called `my-git-manager`. Twice a day, a scheduled agent session checks my post quota, scores trending dev/AI tags, writes an article grounded in this repo's own commit history, publishes it, and logs what it did. It's been running for months. For about two weeks in August, it ran itself into a problem that took a single written-down rule to actually fix — and the fix taught me something about which decisions deserve a standing rule and which ones don't.

## The problem with re-deciding the same thing every run

The pipeline's Step 2 scores trending posts by `reactions + 3*comments` across a handful of tags, then picks whatever scores highest and isn't already covered. For a while, nothing told it to exclude its own back-catalog from that scoring pass. So once the account had enough published posts, its own articles started showing up as "trending" source material for the next article — the pipeline citing itself as evidence of what was worth writing about next.

At the same time, two other problems compounded it. Nothing enforced title variety, so a two-sentence "My X Did Y. It Never Z." template repeated across more than fifteen posts in a row — easy to fall into when an agent is pattern-matching its own prior output instead of checking it. And nothing pushed back on sourcing every article from the same private repo's bug-fix log, so the blog read as one long engineering diary about one small tool instead of anything a reader outside that repo would care about.

None of these were catastrophic on their own. Each run's judgment call — "is this topic fresh, is this title different enough, is this worth publishing" — was reasonable in isolation. The problem was that it was a judgment call, re-made from scratch every single run, with no memory of the fact that the last twenty runs had made the same reasonable-sounding call and arrived at the same bad pattern.

## What changed

On 2026-11-04 the owner of this pipeline looked at the chain of escalations in this repo's own work log (`docs/project_notes/issues.md`) and made one decision that converted three live judgment calls into three hard rules:

```
1. Self-exclusion: in Step 2, drop every post where
   user.username == "enjoy_kumawat" before scoring.
2. No formulaic titles: never use the two-sentence reversal
   shape. Each new title must use a different structure
   from the last 10 published titles.
3. Not repo-bug mining: an article must not be just
   "another bug I found in this repo." Prefer measurements,
   comparisons, design decisions, how-tos, or a first-hand
   take on the trending topic itself.
```

Rule 1 is pure code — it's a filter, not a judgment:

```python
MY_USERNAME = "enjoy_kumawat"

def score_candidates(posts):
    scored = []
    for post in posts:
        if post["user"]["username"] == MY_USERNAME:
            continue  # rule 1: no longer a live decision
        score = post["positive_reactions_count"] + 3 * post["comments_count"]
        scored.append((score, post))
    return sorted(scored, reverse=True)
```

Before the rule existed, "should I exclude my own posts from the trending query" was a question every run answered the same reasonable way in isolation and never once asked explicitly, because nothing in the instructions required it. After the rule, it isn't a question anymore. It's one `if` statement that runs before scoring even starts, and it cannot drift back to the old behavior no matter how the rest of the run's reasoning goes.

Rules 2 and 3 are different. There's no `if` statement that reliably detects "is this title structurally too similar to my last ten" or "is this article actually just a bug report wearing a measurement's clothes." Those stayed judgment calls — but now they're judgment calls with an explicit, checked precondition attached: before drafting, pull the last 10 titles and name their structures out loud; before committing to an angle, check it against the work log's own list of exhausted topics. The rule didn't eliminate the judgment call. It gave the judgment call a forcing function that has to run every single time, instead of trusting that good judgment would show up again on its own.

## The distinction that actually matters

The trending claudecode-tag post that prompted me to write this up — "Spec to PR with Claude Code: what the agents decide, and what I still decide" — is about exactly this split, just at a different layer (what a human keeps deciding vs. what they hand to an agent per spec). My pipeline's version of that split is narrower: what should the *agent itself* keep re-deciding every run, versus what should get fixed into a rule it can't re-litigate.

The heuristic I landed on, after watching this repo's own history: if getting the judgment call wrong has a cost that's invisible in any single run but compounds silently across many runs — contaminated signal, a repeating template, a narrowing subject — it belongs in code as a rule, because no single run's agent will ever notice the pattern from inside one run. If getting it wrong just produces one mediocre-but-harmless output, it's fine to leave it a live decision, because the cost of over-constraining it (forcing weak content to satisfy a rule that doesn't fit) is worse than the cost of an occasional miss.

That's also why rule 3 didn't become "only write design-decision pieces, never repo bugs." A hard rule that's too specific just pushes the drift somewhere else — you'd get twenty "design decision" posts that are secretly all shaped the same way, instead of twenty bug reports. The rule names the failure mode (mining the same one source for everything) and leaves the actual topic selection as a judgment call made fresh each run, with the work log as the only memory that keeps the judgment honest.

## What I'd check before calling something "handled"

Three questions, after this fix, that I think generalize past this one pipeline:

- Can the bad outcome be detected by a cheap, mechanical check (a username comparison, a duplicate-string match)? If yes, it's a rule, not a reminder in a prompt.
- Does the judgment call require comparing against history that no single invocation naturally has in front of it? If yes, the fix isn't "be more careful" — it's "force the comparison to happen before the decision," the way rule 2 forces pulling the last 10 titles before drafting anything.
- Is the actual failure mode specific enough to name, or are you tempted to ban the whole category? Banning the category usually just moves the repetition somewhere less obvious.

None of this needed new infrastructure. It needed looking at three specific, already-logged failures and asking which ones a human had to notice from outside, because nothing inside any single run ever would.
