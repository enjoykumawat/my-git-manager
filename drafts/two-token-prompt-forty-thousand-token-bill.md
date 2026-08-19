---
title: A 2-Token Prompt and a 39,966-Token Bill: Measuring What My Agent Actually Costs
published: true
tags: ai, llm, claudecode, devtools
---

There is a small cluster of posts going around right now about auditing your LLM invoice, and about how cost calculators get the numbers wrong. I went to check mine and hit a problem before I got to the arithmetic: my pipeline doesn't produce an invoice, and the plumbing I built two months ago is the reason why.

This project has a script, `git_commit.py`, that turns a staged git diff into a Conventional Commit message. It shells out to the Claude CLI. There is no `ANTHROPIC_API_KEY` anywhere in the project, on purpose — an early version used `urllib` against the API directly and broke immediately for anyone running on an OAuth session instead of a raw key, so every AI call in the repo goes through a `claude -p` subprocess instead.

That decision is still right. It also means there is no API key, so there is no per-key usage dashboard, so there is no line item to audit. For several months this script has been making a model call on essentially every commit, and I have never once known what any of them cost.

## The call site throws the numbers away

Here is the actual invocation, trimmed:

```python
raw = subprocess.check_output(
    ["claude", "-p", "--safe-mode", SYSTEM + "\n\n" + diff],
    text=True,
    timeout=20,
    env=_claude_subprocess_env(),
)
```

`subprocess.check_output` returns stdout. With the CLI's default output format, stdout is the commit message string and nothing else. Every number I would want — tokens in, tokens out, dollars — is computed on the other side of that call and then discarded, because I asked for a string and a string is what I got.

This is the part I want to flag for anyone wiring up a headless model call the same way. It isn't that the metering is missing. It's that the default output format is lossy in exactly the dimension you'd later want to audit, and you won't discover that by reading your own code, because your own code looks fine. It asks for text, it gets text.

The fix is one flag:

```python
raw = subprocess.check_output(
    ["claude", "-p", "--safe-mode", "--output-format", "json", prompt],
    text=True, timeout=20, env=_claude_subprocess_env(),
)
payload = json.loads(raw)
message = payload["result"]          # what the old code got back
usage = payload["usage"]             # what the old code silently dropped
cost = payload["total_cost_usd"]
```

## The number that made me stop

Before wiring that in properly I ran the cheapest possible probe to see what the shape of the data was. Literal prompt: `reply with exactly: OK`. Four words. Here is the usage block that came back:

```json
{
  "input_tokens": 2,
  "cache_creation_input_tokens": 39966,
  "cache_read_input_tokens": 0,
  "output_tokens": 4,
  "total_cost_usd": 0.2408
}
```

Two input tokens. Twenty-four cents.

The field literally named `input_tokens` was 2, and it accounted for roughly nothing. The billed input was the other 39,966 tokens, sitting in `cache_creation_input_tokens` — system scaffolding, tool schemas, session context, all the material that gets assembled around your prompt before it goes anywhere.

This is the specific thing the cost-calculator posts are circling. If you estimate spend as `len(prompt) / 4 * rate`, you are modelling the 2 and ignoring the 39,966. My prompt was four words and the real input was five orders of magnitude larger. No amount of tightening my wording moves that number, because my wording was never the cost.

## Then I measured the thing I'd already "fixed"

Back in August I found that a `claude -p` subprocess launched from this repo's root was auto-loading the project's `CLAUDE.md` into every single commit-message call — a long block of routing rules about MCP tools that don't even exist in that process. A one-shot diff-to-commit-message completion was being handed the entire project rulebook every time.

I found that with a behavioural probe. I asked the subprocess whether it could see the rules, it said yes, I added `--safe-mode`, I asked again, it said no. Fixed, logged, moved on.

What I never did was measure it, because at that point there was still nothing to measure with. So I ran the same trivial prompt from the repo root twice, once with the flag and once without:

```
                        --safe-mode      no flag
input_tokens                      2            2
cache_creation                5,770        7,803
cache_read                   34,210       35,994
output_tokens                     4          313
total_cost_usd              $0.0459      $0.0633
```

The input side moved about as much as I'd have guessed: roughly 3,800 extra tokens of rulebook, ~38% more cost on the call.

The output column is the one I didn't see coming. Same prompt, same correct answer, and the run without `--safe-mode` produced **313 output tokens instead of 4**. Both returned the string `OK`. The extra 309 tokens were the model working through which of the mandated `ctx_*` routing tools it was supposed to use before answering a question whose answer is two characters.

That is the effect I want to name, because it doesn't show up in any mental model of prompt bloat I had. Context you inject doesn't just cost you its own size on the way in. It changes how much the model deliberates on the way out. A rulebook about tool selection makes the model reason about tool selection, on every call, including the calls where there is nothing to select.

## What I'm actually changing

Not much, and deliberately.

I'm not adding a metrics backend. The one audit log this project already has, `logs/article_updates.jsonl`, is local-only by design, and the scheduled work runs in a fresh container per session, so anything I write per-call is gone when the container is. A cost log that evaporates is worse than none, because it looks like coverage.

What's worth doing is the flag and one assertion. Switch the call to `--output-format json`, parse the result field where the raw string used to be, and put a bound on it:

```python
COST_CEILING_USD = 0.15

payload = json.loads(raw)
if payload.get("is_error"):
    sys.exit("claude -p returned an error payload")
cost = payload.get("total_cost_usd", 0)
if cost > COST_CEILING_USD:
    print(f"warning: commit message cost ${cost:.4f}", file=sys.stderr)
return _strip(payload["result"])
```

A ceiling that prints to stderr is not observability. It's a tripwire. If the number quietly triples because something started getting loaded into these calls again, I find out at the next commit instead of never. Given that the last time exactly that happened I only caught it by asking the model a trick question, a tripwire is a strict improvement.

One more thing worth knowing if you go measuring: my three runs cost $0.2408, $0.0459 and $0.0633 for an identical prompt. The expensive one was a cold cache paying full freight on `cache_creation`; the cheap ones read most of it back. Same work, 5x spread, entirely determined by cache state. Any per-call figure you quote, including the ones in this post, is a sample of a distribution and not a price.

The real lesson is smaller than the numbers make it look. I built a subprocess call that returns a string, and a string is all I ever asked for, so for months the only honest answer to "what does this cost" was that I had no idea. The data was one flag away the entire time.
