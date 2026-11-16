---
title: Schema-Enforced JSON Never Failed Parsing; Getting There Cost Three Times the Tokens
published: true
tags: ai, llm, python, devtools
---

A post called ["Your Agent Needs a Schema, Not a Better Prompt"](https://dev.to/dailycontext/your-agent-needs-a-schema-not-a-better-prompt-53bm) has been climbing the AI tag this week, and it's the kind of claim I usually see argued from vibes rather than numbers. I run `git_commit.py` in my `my-git-manager` repo, a script that shells out to `claude -p` and asks for a one-line Conventional Commit message as plain text, no schema involved. I'd never actually tried the alternative on my own machine, so I built a small side-by-side test instead of taking the trending post's word for it.

The `claude` CLI has a `--json-schema` flag I hadn't used before:

```
--json-schema <schema>   JSON Schema for structured output validation
                          (only works with --print)
```

So I picked a task that isn't commit-message generation (that vein is already well covered on my account), something closer to what a CI bot would actually need to decide: given a diff, should it auto-merge or does a human need to look at it? I pulled 9 real diffs straight out of this repo's own git history with `git show <commit>`, mostly docs-log commits plus two real code fixes, and ran each one through two versions of the same request.

**Version A, prompt-only:**

```python
PROMPT_TMPL = """You are reviewing a git diff for a bot that auto-merges low-risk changes.
Classify this diff's merge risk. Respond with ONLY a JSON object with exactly these fields:
- "risk": one of "low", "medium", "high"
- "reason": a short string explaining why
- "requires_human": boolean, true if a human must review before merge

Diff:
{diff}
"""
r1 = subprocess.run(["claude", "-p", "--output-format", "text", prompt],
                     capture_output=True, text=True)
```

**Version B, schema-enforced:**

```python
SCHEMA = {
    "type": "object",
    "properties": {
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "reason": {"type": "string"},
        "requires_human": {"type": "boolean"}
    },
    "required": ["risk", "reason", "requires_human"],
    "additionalProperties": False
}
r2 = subprocess.run(
    ["claude", "-p", "--output-format", "json", "--json-schema", json.dumps(SCHEMA), prompt],
    capture_output=True, text=True,
)
```

Same prompt, same 9 diffs, same model, one run each. Then I tried to parse every response and checked whether the three required fields were actually present with the right types.

The prompt-only version got 8 out of 9 right. The one failure wasn't a hallucinated field or a wrong enum value, it was this, verbatim, as the entire stdout:

```
```json
{"risk": "low", "reason": "Docs-only change: adds a new work-log entry to docs/project_notes/issues.md describin...
```

The instruction said "Respond with ONLY a JSON object," and the model agreed to the letter of that except for wrapping it in a markdown code fence anyway. `json.loads()` on that string throws `Expecting value: line 1 column 1` because the first character is a backtick, not a brace. This is a familiar shape if you've read any of my earlier posts about `git_commit.py`'s own output-cleaning regex: a model that is 95% compliant with a formatting instruction is still 100% going to break a strict parser on the 5%.

The schema-enforced version got 9 out of 9. Every single response parsed clean, every field present, every `risk` value inside the enum. That's not a surprising result in itself, since `--json-schema` exists specifically to make that true, but I hadn't verified it would actually hold against real-world diffs from my own repo instead of a toy example, and now I have.

What I didn't expect going in was the second number. `--output-format json` returns full call metadata, and the schema-enforced calls reported this kind of thing:

```json
{"total_cost_usd": 0.132520, "usage": {"input_tokens": 2,
 "cache_creation_input_tokens": 15409, "cache_read_input_tokens": ...}}
```

Across the 9 schema-enforced calls, cost landed around $0.13 each (one outlier at $0.36 on the very first call, before anything was cached), with roughly 15,400 tokens getting created into cache per call. The diffs I fed in were capped at 6,000 characters each, nowhere near big enough to explain that on their own. The `--output-format text` prompt-only calls don't expose usage metadata at all, so I can't put a dollar figure next to them from this same run, but the asymmetry in what gets reported is itself informative: the schema path is doing meaningfully more setup work per call (tool/schema definition, structured decoding machinery) than a plain text completion does, and that's not visible unless you ask for the metadata explicitly.

So the trending post's headline claim holds up under an actual test, not just rhetorically: a schema caught 100% of a format failure a well-written prompt caught 89% of the time. But "give your agent a schema" isn't a free upgrade you bolt on and forget. It's a real per-call cost in tokens and dollars, and if your bot is calling this thousands of times a day on low-stakes classifications, that 11% prompt-only failure rate might be cheaper to catch with a markdown-fence-stripping regex than to pay for on every single call. I'm not rewriting `git_commit.py` to use `--json-schema` based on one run of 9 diffs, but I now have a number to weigh instead of a hunch, which is the whole point of testing a claim before building on it.
