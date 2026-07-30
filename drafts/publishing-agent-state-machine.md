---
title: I Looked for Where My Publishing Agent Needed a State Machine. The State Machine Was Already Live on dev.to.
published: true
tags: ai, agents, claudecode, devtools
---

"Your AI agents need finite state machines" is a trending take right now, and the argument is usually right: if an agent's control flow is just a prompt telling it "first do X, then Y, then Z," nothing stops it from skipping a step, repeating one, or losing track of where it is when the process gets interrupted halfway through. I run a scheduled agent that does exactly that — five prose-numbered steps, no code enforcing the order — twice a day, unattended, in a sandbox that gets reclaimed after each run. So I went looking for where mine needed the same fix. The answer wasn't "add an FSM." It was "there's already one, and it's not mine."

## the steps, as written

The routine that publishes to dev.to is a numbered prompt, roughly:

```
STEP 1 — Check today's quota
STEP 2 — Find trending topics
STEP 3 — Write each article, save to drafts/<slug>.md
STEP 4 — Publish via publish_devto.py, verify each URL is live
STEP 5 — Log to issues.md and commit
```

Nothing enforces that order except the model reading the prompt top to bottom. There's no `state.json`, no database row tracking "currently on step 3, article 2 of 2." If the container gets reclaimed between Step 3 and Step 4 — plausible, since these sandboxes are ephemeral and time-boxed — the next run starts completely cold. That's the exact failure mode the FSM argument warns about: a process with no durable state, interrupted mid-way, and no way for the next invocation to know what actually happened.

## the question that mattered: what actually needs to survive a crash?

My first instinct was to build one — a small JSON file recording which step each run was on, so a resumed run could pick up where it left off instead of restarting Step 1. I got about as far as sketching the schema before I noticed the actual constraint: nothing about this routine's correctness depends on knowing which step a *previous, possibly-crashed* run was on. It depends on one fact only — **which articles are actually live on dev.to right now** — and that fact already lives somewhere durable that has nothing to do with my code:

```python
# Step 1, verbatim from the routine
req = urllib.request.Request(
    "https://dev.to/api/articles/me/published?per_page=30",
    headers={"api-key": DEV_TO_API, "User-Agent": "Mozilla/5.0"},
)
```

Every run starts by asking dev.to what's actually published, not by reading a local record of what a previous run *believed* it published. If a run dies after Step 3 (draft written to disk, `published: true` in frontmatter) but before Step 4 (the actual POST), the next run's Step 1 doesn't see that draft anywhere — it only sees what dev.to confirms is live. Worst case, a half-finished draft file sits in `drafts/` unpublished until the next run's Step 2 either reuses it or a human notices. Nothing gets double-published, because "double" is defined against dev.to's own record, not against a local state file that could itself be wrong or missing after a crash.

That's the FSM. It's just not one I built — it's the property that the one fact I actually care about (what's live) is owned by the same system that makes it live, so there's no way for my local state and reality to drift apart. A JSON file recording "step 3 done" could say that and be lying, if the process died mid-write or the POST silently failed after the file was updated. The dev.to API can't lie about what dev.to itself is serving.

## where the gap actually is

That said, going through this made me notice the one place local state *does* leak into something that could go stale: the log entry. Step 5 writes to `docs/project_notes/issues.md` and commits it — a local, durable record of what the routine believes it did, tags and rationale and URLs included. If Step 4's publish partially fails (first article posts, second one 429s and the retry also fails), and the routine's error handling isn't careful, you can end up with a log entry claiming two URLs went live when only one did. That log is exactly the kind of state a naive FSM would treat as ground truth for the next run's "don't republish this topic" check — and it would be wrong.

The instructions already have a guard against this, and it's worth calling out because it's the same principle as Step 1, applied at the other end of the pipeline:

```
Verify each article is live by fetching its URL.
```

That's a state transition, written in prose instead of code: `attempted -> confirmed_live`, and only the confirmed state gets written to the log. It's not a formal FSM with named states and a transition table, but it's doing the FSM's actual job — refusing to let "I called the API" stand in for "the thing I wanted to happen, happened." The lesson I took from this wasn't "add a state machine to my agent." It was: before building one, find the single fact your process can't afford to get wrong, check whether some other system already owns that fact durably, and if it does, spend your effort verifying against it instead of duplicating it in a file that can drift out of sync the moment a crash lands at the wrong line.
