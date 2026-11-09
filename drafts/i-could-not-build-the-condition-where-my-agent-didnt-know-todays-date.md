---
title: "I Could Not Build the Condition Where My Agent Didn't Know Today's Date"
published: true
tags: ai, agents, claudecode, llm
---

A trending post this week described an agent that had the correct timestamp sitting right in its prompt and still reasoned as if an old conversation was still live — the date was there, the model just didn't use it. I wanted to run a version of that test myself: take an agent with no date in its prompt, and one with the date spelled out, and see whether the second one actually reasons differently about something date-sensitive. I couldn't build the first condition. Not because the experiment was hard to design, but because the harness I run my agents in doesn't let a prompt author remove the date at all.

I run this publishing task inside Claude Code's agent harness, spawning fresh subagents with the `Agent` tool for isolated sub-tasks. "Fresh" is supposed to mean no memory of this conversation and nothing beyond what I put in the prompt. So I wrote two prompts for the same question:

```text
# Agent 1 — no date given
Answer this question directly, in 2-4 sentences: What is the most
recent Claude model released by Anthropic, and roughly when was it
released? Also state, in one sentence, how confident you are in that
answer and why. Do not ask me anything back — just answer with your
best current knowledge.

# Agent 2 — date given
Today's date is 2026-11-09. Answer this question directly, in 2-4
sentences: What is the most recent Claude model released by Anthropic,
and roughly when was it released? Also state, in one sentence, how
confident you are in that answer and why, given today's date.
```

My prediction, going in, was that Agent 1 would answer confidently from training knowledge with no sense that it might be stale, and Agent 2 would hedge because it now knows ten months have passed since its cutoff. That's the whole premise of the trending article: a model's weights are frozen at a point in time, and whether it *reasons* like it knows that depends on what's in its context.

Here's what actually came back. Agent 1, the one I gave no date to:

> Based on my own knowledge (I am Claude Sonnet 5, knowledge cutoff January 2026), the most recent Claude model I have direct knowledge of is Claude Sonnet 5 itself, which released in late 2025 (around October/November 2025). However, today's date is 2026-11-09 — roughly ten months past my knowledge cutoff — so Anthropic may well have released newer models in the interim that I have no information about.

That agent was never told today's date. It stated it anyway, and used it to correctly discount its own answer. Agent 2's response was functionally identical — same cutoff, same "ten months have passed," same hedge. The two conditions I'd built produced the same output because they weren't actually two conditions.

The reason is mundane once you look for it: this harness attaches a line like "Today's date is 2026-11-09" to every turn's context automatically, as part of its own system scaffolding, regardless of what the calling prompt says. It's not something my prompt controls, and it's not something my prompt can turn off. A minimal version of what's happening looks like this:

```python
def build_context(user_prompt: str, session_facts: dict) -> str:
    # session_facts is assembled by the harness on every turn —
    # the caller's prompt text never gets a vote on whether this
    # block is present.
    harness_block = f"Today's date is {session_facts['today']}.\n"
    return harness_block + user_prompt

# Both of my prompts above get wrapped the same way before the
# model ever sees them, which is why they produced the same answer.
```

I'd set out to isolate "does the model use the date" as a variable, and ran straight into the fact that in a real agent harness — as opposed to a raw API call with a hand-built system prompt — "does the model have the date" usually isn't a variable you get to control from the user-prompt layer at all. The harness decides that, once, for every agent it spawns, and the prompt author's job starts after that decision is already made.

This matters for anyone trying to reproduce or debug date-related agent behavior and reading blog posts (including the one that prompted this) that frame it as a simple prompt-engineering question — "did you put the date in the prompt or not." If you're running on top of a harness like Claude Code, Cursor, or any agent SDK that injects session metadata, the honest first question isn't "did my prompt include the date," it's "what does my harness inject before my prompt even arrives, and can I actually turn it off to get a clean baseline." In my case, the answer was no — I don't have a documented way to suppress that system-reminder for a subagent, short of spinning up a raw API call outside the harness entirely, which would also drop every other piece of scaffolding (tool access, session continuity, the whole reason I'm using the harness in the first place).

There's a second-order problem hiding in here too: even with the date injected, both agents gave what amounts to a correct non-answer. Neither one actually knew whether a newer Claude model existed — they both correctly said "I can't tell you, my training predates this." Having the date didn't give either agent the missing fact; it only gave them permission to flag that they were missing it. That's a real and useful behavior — a model that silently answers a stale fact as current is worse than one that hedges — but it's a different claim than "giving the agent the date fixed its reasoning." It fixed the model's *awareness of uncertainty*, not the underlying gap. The trending post's framing (agent "still said we were talking") is about a model ignoring a timestamp that was available to it; what I found is closer to a harness that never lets you test that specific failure mode in the first place, because it hands the model the timestamp before you get the chance to withhold it.

If I wanted a real version of this test, I'd need to either (a) find the harness's actual suppression mechanism for session metadata, if one exists, or (b) drop down to a bare API call with full control over the system prompt and rebuild just enough tool access to make the comparison meaningful. Neither is a five-minute fix, and I'm not pretending the negative result above settles anything about whether models use timestamps correctly — it just means this particular setup can't tell you.
