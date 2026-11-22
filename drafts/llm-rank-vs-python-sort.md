---
title: Asking an LLM to Rank My Own Trending Topics Took 150,000x Longer Than Four Lines of Python, and Landed on the Identical Answer
published: true
tags: ai, llm, python, productivity
---

A trending dev.to post this week asked "Is coding with AI actually faster and cheaper?" and it stuck with me, because I run a small pipeline that already has a buried answer to a narrower version of that question, and I'd never actually measured it.

Twice a day, a scheduled job in my `my-git-manager` repo pulls the top posts from six dev.to tags (`ai`, `llm`, `mcp`, `claudecode`, `agents`, `productivity`), scores each one, and picks the highest-scoring theme that isn't already something I've written about. The scoring step is one line:

```python
scored = sorted(posts, key=lambda p: p["reactions"] + 3 * p["comments"], reverse=True)
```

That formula — reactions plus three times the comment count — treats a comment as a stronger engagement signal than a reaction, on the theory that someone who typed a sentence cared more than someone who clicked a button. I didn't invent that justification today; it's been sitting in this pipeline's design for a while. What I'd never done is ask the obvious follow-up: would an LLM call, pointed at the same data, do this job as well, and is there any reason it should.

So today I ran both, back to back, on the real trending data this run actually pulled.

## The deterministic version

I fetched 96 unique posts across the six tags (after dropping my own account's posts — more on that below), scored them with the one-liner above, and timed it:

```python
import time
t0 = time.time()
scored = sorted(posts, key=lambda p: p["reactions"] + 3 * p["comments"], reverse=True)
t1 = time.time()
print(f"{t1 - t0:.6f}")
```

`0.000031` seconds. Top three by score: a post titled "Is Coding with AI Actually Faster and Cheaper?" at 824, "AI agents open 17 million pull requests a month..." at 290, and a `#Stratagems` post at 280. No ambiguity — the ranking is a deterministic function of two integers already sitting in the API response.

## The LLM version

Then I handed the identical 96 posts (id, title, reaction count, comment count) to a one-shot `claude -p` call, with explicit instructions to apply the exact same formula and return the top three ids as JSON:

```bash
claude -p --output-format json "$(cat prompt.txt)"
```

The result came back as `[5060452, 5058432, 5069884]` — the exact same three ids, in the exact same order, as the Python sort. No disagreement. But `--output-format json` also hands back real usage numbers, and those are where the two approaches stop looking equivalent:

```json
"duration_api_ms": 3372,
"usage": {
  "input_tokens": 2,
  "cache_creation_input_tokens": 18050,
  "cache_read_input_tokens": 27421,
  "output_tokens": 195
},
"total_cost_usd": 0.1537922
```

Wall-clock time for the whole call, including process spawn: 4.94 seconds. Total tokens moved: on the order of 45,000, split across a fresh cache write and a cache read. Cost: just over 15 cents, for a single ranking of 96 rows I could've done for free.

Divide it out and the LLM call took roughly 150,000 times longer than the Python sort, for a task where both produced byte-identical output.

## Why this isn't an argument against using an LLM here

It would be easy to read this as "don't use AI for things code can do," and stop there, but that's not quite the finding — the finding is narrower and more useful than that. The reason the two approaches agreed perfectly is that I gave the LLM a closed-form formula and numbers that were already in the input. There was no judgment call left for it to make. I'd already done the actual thinking — deciding that comments should count three times as much as reactions — when I wrote the Python one-liner weeks ago. Asking the LLM to re-derive an answer I'd already computed isn't delegating a decision, it's paying for arithmetic.

This same pipeline uses `claude -p` for a completely different job, and that one earns its cost: turning a staged git diff into a Conventional Commit message is not a function of two integers. It requires reading the actual change and summarizing intent in a sentence a human would write — there's no `reactions + 3*comments` for "what did this diff actually do." That's a real ADR in this repo (`docs/project_notes/decisions.md`, ADR-004): shell out to `claude -p` specifically because the task is open-ended language generation, not because an LLM is generically the right tool for every step of a pipeline that happens to touch text.

The useful question, it turns out, isn't "is AI faster/cheaper than code" in the abstract. It's: does this specific step reduce to a formula over data I already have? If yes, the LLM call is strictly worse on every axis that matters here — latency, cost, and determinism, since a second call with a shuffled prompt or a slightly different cache state has no guarantee of landing on the same ranking twice, where the sort always will. If no — if the step actually requires reading unstructured text and producing a judgment — the comparison flips, because there's no formula to fall back on in the first place.

## What I changed

Nothing in the pipeline's code, actually — the scoring step was already plain Python before I ran this comparison, which is exactly why I was curious whether that choice was still justified or just inertia. What changed is that it's no longer an assumption. I have real numbers now: 0.000031s and $0 versus 4.94s and $0.15, for an identical result, measured against today's actual trending data instead of a synthetic benchmark.

If you're building a pipeline that mixes deterministic steps with genuinely open-ended ones — and most agent pipelines do — it's worth actually timing the boundary between them at least once, the way I did here, rather than reaching for the model by default because the rest of the pipeline already talks to one. The two numbers side by side make the case better than any general argument about AI coding speed could.
