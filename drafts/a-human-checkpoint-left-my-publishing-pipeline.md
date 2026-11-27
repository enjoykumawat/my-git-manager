---
title: "A Human Checkpoint Left My Publishing Pipeline, and Three Testable Rules Took Its Place"
published: true
tags: ai, agents, productivity, devtools
---

A trending post this week asked why, after automating most of a software factory, someone was still clicking "approve" on typo fixes — the point being that some approval gates earn their keep and some are just friction wearing a safety costume. I've got a real instance of exactly that decision in my own repo, and it didn't end the way the trending post's framing would predict. The gate wasn't removed because it was friction. It was removed because the thing it was protecting against got turned into code instead.

For a stretch of this repo's history, my twice-daily dev.to publishing routine had a human-in-the-loop step, but not the kind people usually mean by that phrase. Nobody reviewed each article before it went out. The checkpoint was coarser and further upstream: if a run noticed something structurally wrong with the whole publishing pattern, it would stop publishing entirely and escalate, rather than keep producing more of whatever the problem was. That's what happened starting 2026-08-16. Three concrete concerns got flagged in the work log:

```
1. identical two-sentence reversal title template across 15+ posts
2. the account's own published articles contaminating its own
   trending-topic query (step 2 was scoring my own back-catalog
   as if it were someone else's trending post)
3. every article sourced from mining this one private repo for
   another bug — no outside angle, ever
```

The routine held at zero published articles and sent a notification. Then it held again the next run. And the one after that. By 2026-08-28 the log entry is titled "twenty-second consecutive hold, no new information since this morning." By 2026-08-30, with still no recorded response across eleven straight dark days, the run went further than holding — it disabled its own trigger:

> Decision this run: rather than hold again and let the routine keep firing twice daily into the same silence, disabled the recurring trigger itself... This does not change today's actual output (still 0 articles)... it removes the twice-daily "still no answer" noise from continuing to pile up.

That's a genuinely unusual thing to find in a work log: an automated pipeline choosing to go quiet rather than keep repeating a pattern it had already flagged as a problem to a human who hadn't answered yet. It's the opposite failure mode from the one the trending post is worried about — this wasn't rubber-stamping, it was the checkpoint doing exactly what it was built for, for eleven days straight, with a real cost (zero published articles, a paused trigger) attached to taking it seriously.

The resolution came on 2026-11-04, and it's worth being precise about what actually changed, because it isn't "the owner said stop worrying about it." The decision replaced the hold-and-escalate step with three rules that run inside every single publish, unconditionally:

```
1. Self-exclusion: drop every post where user.username ==
   "enjoy_kumawat" before scoring — closes concern #2 directly.
2. No formulaic titles: never use the two-sentence reversal
   shape. Each new title must use a structure different from
   the last 10 published titles — closes concern #1 directly,
   and makes it checkable, not just avoidable by intention.
3. Not repo-bug mining: an article must not be just "another
   bug I found in this repo." This repo's history can be
   supporting evidence, not the whole article — closes concern
   #3, with an explicit list of which prior themes count as
   already exhausted.
```

Rule 2 is the one I can verify is actually load-bearing rather than decorative, because it runs every time this pipeline publishes — including right now, writing this. Before drafting either of today's articles, the real last-10 published titles get pulled live and checked structurally: a question-mark lead, an "If X, Y" conditional, a "Why I... Instead of..." causal declarative, a bare three-part noun list, a numeric list with a trailing clause, and so on. This article's own title had to clear that same bar against the same list before it could be written. The rule isn't "try not to repeat yourself" sitting in a prompt somewhere hoping to be followed — it's a check against live data, every run, with no exception clause for "but this topic really fits the reversal shape better."

That's the actual distinction I'd draw from the trending post's question, sharper than "some gates are worth keeping and some aren't." It's: a human checkpoint and a hard-coded rule aren't two strengths of the same thing, they're different failure shapes. The checkpoint that held for 23 runs was good at stopping a slow-accumulating pattern problem (title repetition, self-contamination) that nobody would notice from inside any single run — but it had no way to resume itself, which is exactly why eleven days of silence turned into a paused trigger instead of a fixed pipeline. The three rules that replaced it can't notice a *new* kind of pattern problem nobody specified in advance — they only catch what they were written to catch. Swapping one for the other wasn't a downgrade in rigor; it traded a mechanism that could escalate indefinitely for one that can't escalate at all, in exchange for one that can't get stuck either.

There's a second, smaller gate in this same repo that the 2026-08-30 entry mentions almost in passing, and it's the control case that makes the first one legible: the comment-reply routine was left running the whole time, explicitly "because it drafts replies for manual review and posting, not autonomous publishing, and isn't implicated in this concern." Nobody built a hard rule to replace anything there, because nothing needed replacing — that pipeline's output was already bounded by a human doing the actual posting by hand (dev.to's write API returns a 404 trying to create a comment as a normal account; there's no autonomous path to take away). The publishing pipeline's checkpoint existed because the autonomous path was real and the risk was a slow-drift pattern, not a single bad action. Three testable rules are a reasonable trade for that kind of risk. They wouldn't be a reasonable trade for "don't let the pipeline do something irreversible on its own" — that one needs an actual gate, not a rule a sufficiently motivated prompt could talk itself past. Before removing any approval step, that's the question I'd actually ask: not "is this still useful," but "what shape of failure was this catching, and does the replacement catch that same shape, or just the one instance of it we already know about."
