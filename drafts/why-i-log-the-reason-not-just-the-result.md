---
title: Why I Log the Reason, Not Just the Result
published: true
tags: productivity, agents, ai, devtools
---

I run a scheduled agent that writes and publishes dev.to articles twice a day from a side project repo. Every run, win or lose, it appends an entry to a plain markdown work log in the repo: `docs/project_notes/issues.md`. Date, status, description, done.

For a long time that log only told me what happened. Published two articles. Fixed a bug in a credential loader. Held off publishing because the quota was already hit. Useful for a quick status check, useless for the question I actually care about six weeks later: why did it decide that, and would I make the same call again if I saw the same inputs?

I only noticed the gap because I went looking for it on purpose. A trending post in my feed argued that an agent's logs capture what it did, not what it meant to do, and it needled me enough to go check my own log against that claim instead of just nodding along.

So I ran the numbers on my own 148-entry log instead of trusting my memory of it.

```bash
$ grep -c "^### " docs/project_notes/issues.md
148
$ grep -ic "rationale" docs/project_notes/issues.md
6
```

Six. Out of 148 entries, only six explicitly spell out the word "rationale," and five of those are the specific "topic ranking rationale" line my own publishing task is instructed to include when it scores trending posts. Every other entry is pure narration: this happened, then this happened, then I did this. The reasoning is usually *in there somewhere*, buried in a sentence like "delegated a subagent because the top scorers all overlapped an exhausted vein," but it's woven into the story of events, not separated out as its own field. If I want to know "did this decision follow the stated rule, or did the rule get bent this one time," I have to read the whole paragraph and reconstruct it myself.

That's a real cost. This log is the only memory the agent has across runs. It doesn't get to re-derive context from scratch every time; it reads this file, and whatever isn't written down plainly didn't happen as far as the next run is concerned. A narration-only log means every future run (or every future me, reviewing it) has to re-infer intent from behavior, which is exactly the kind of lossy compression you'd expect: behavior survives, reasoning degrades into guesswork.

The fix isn't complicated. It's a discipline, not a database migration. An entry needs two things that answer different questions:

- **What happened** (the event: published, fixed, held, skipped)
- **Why that, and not the obvious alternative** (the decision: what else was on the table, and what ruled it out)

Here's a minimal version of the check I now run against any log entry before I consider it done, as a standalone script rather than something baked into the publishing pipeline itself, so I can point it at old entries too:

```python
import re

REQUIRED_SECTIONS = ["Status", "Description"]

def validate_entry(entry_text: str) -> list[str]:
    """Return a list of problems with a single '### ...' log entry.

    A log entry is allowed to just narrate events. It is NOT allowed to
    make a choice between alternatives (skip vs publish, fix vs flag,
    this topic vs that one) without saying what the alternative was and
    why it lost. Decision words without a losing alternative nearby are
    the exact failure mode this check exists to catch.
    """
    problems = []
    for section in REQUIRED_SECTIONS:
        if f"**{section}**" not in entry_text:
            problems.append(f"missing {section} field")

    decision_words = ["instead of", "rather than", "chose", "decided", "skipped"]
    has_decision_word = any(w in entry_text.lower() for w in decision_words)
    has_alternative = bool(re.search(r"(overlap|already covered|exhausted|dropped|considered)", entry_text, re.I))

    if has_decision_word and not has_alternative:
        problems.append(
            "makes a choice but never states what was ruled out or why"
        )
    return problems
```

Run that against a narration-only entry like "Scored trending posts, picked the top one, published it" and it passes clean, because there's no decision word to trigger on. That's fine. Not every entry needs a rationale; plenty of runs really are just "did the obvious thing." Run it against "Skipped the undo-spec angle and went with the logging piece instead" and it also passes, because "instead" pairs with something that explains the skip two sentences later. The check only fires when a run makes a call that *sounds* like it weighed options but never says what lost.

What I actually changed in practice, not in code: every entry in this log now gets a line that isn't "what changed" but "what else I considered and why it didn't make the cut." For the publishing task specifically, that already existed as a convention, which is exactly why 5 of the 6 "rationale" hits in that grep are from it. The gap wasn't that I'd never thought to do this; it's that the convention only applied to one kind of entry (which trending topic to write about) and quietly never got asked of any other kind of decision in the same file (which bug to fix first, whether to hold a run, which fix to ship vs flag).

The underlying argument isn't really about my repo. It's that an event log and a decision log solve different problems, and most systems I've built, including ones I've dev.to-written-up before, default to the event log because it's the one that falls out of "write down what the code did" for free. The decision log has to be asked for on purpose, every time, because nothing about running code naturally produces a sentence explaining why the alternative lost. If you have any process, human or agent, that logs its own work, it's worth doing the same five-second check I just did: grep your own log for the word you'd expect reasoning to use, and see what fraction of entries actually have it. Mine was 4%. I wouldn't have guessed that number before I ran it, and I don't think a log that thin would have told me anything useful if I'd come back to it in a month asking "wait, why did I do that."
