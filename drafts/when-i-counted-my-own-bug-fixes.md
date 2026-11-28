---
title: "When I Counted My Own Bug Fixes, Only One in 53 Was a Prompt Change"
published: true
tags: ai, llm, agents, devtools
---

A benchmark post went around this week claiming that for a particular agent task, changing the scaffolding around a model moved its score by 39 points, while changing the model itself only moved it by 10. I didn't have a benchmark to reproduce that with, but I do have something close: a plain-text log of every bug this project's scheduled agents have hit and how each one actually got fixed, going back five months. So instead of nodding along, I grepped it.

This repo runs a handful of small agent-driven jobs: a commit-message generator, a dev.to publishing pipeline, a comment-reply drafter. Every time one of them broke, the fix got written up in `docs/project_notes/bugs.md` — issue, root cause, solution, prevention. I went through all 53 entries and sorted each one into two buckets: fixes that changed a prompt or system-prompt text, and fixes that changed code.

```python
import re
text = open("docs/project_notes/bugs.md", encoding="utf-8").read()
entries = re.split(r"(?m)^### ", text)[1:]
prompt_fixes = [e for e in entries if "system prompt" in e.lower() or "system-prompt" in e.lower()]
print(len(entries), "total,", len(prompt_fixes), "mention system prompt text")
```

53 entries. 3 mention "system prompt" at all, and of those, only one is actually a prompt-wording fix — `server.py`'s `generate_commit_message` tool had an inline system prompt that never got updated when its sibling function's prompt was hardened to say "no co-author lines, no signatures, no AI references." The fix was copying the updated wording over. One function, one string, done.

The other 52 are all code: a `KeyError` from a bare `os.environ[...]` subscript, `except HTTPError` not catching the broader `URLError` it's a subclass of, HTML entities never getting decoded before a reply gets drafted from the stripped text, a duplicate-title guard that only paginated three pages when the account had grown past that, a `.env` parser that didn't strip a trailing space from a key name. Closed-form bugs, each with a single correct fix, each of which stayed fixed once it landed.

The one place a prompt was doing real enforcement work — "no AI attribution in commit messages" — tells a different story. That instruction has been in the system prompt handed to `claude -p` since 2026-06-21. It's backed by a regex, `_STRIP_RE`, that strips any attribution line the model produces anyway, as a safety net for when the instruction doesn't fully land. That regex has needed four separate hardening passes since then:

- **2026-07-22**: the first version over-matched, deleting legitimate commits that mentioned "llm" or "claude" in a normal sentence.
- **2026-07-26**: the fix for that shipped four days after it was flagged, because the fix itself needed its own fix.
- **2026-08-12**: a second gap — the regex only caught the literal `Co-Authored-By:` trailer spelling. `Signed-off-by:`, `Reviewed-by:`, and a bare `noreply@anthropic.com` on their own line all sailed through untouched.
- **2026-11-12**, eleven days before I'm writing this: a third gap in the same spirit — the trailer-value alternation covered six AI tool names, and none of them was the one this project's own `CLAUDE.md` actually names.

That last entry's own root-cause line is the part that stuck with me: "A blocklist built from 'which bypasses have actually happened so far' always lags 'which AI names could plausibly appear in a trailer.'" Four months, four passes, and the entry written eleven days ago is explicitly diagnosing that the approach is a closed set chasing an open one. Nobody's claiming it's fixed now, either — just that this particular gap is closed until the next one shows up.

Compare that to the pagination bug, or the HTML-entity bug, or the `.env` whitespace bug. Each of those got one fix and never came back. The difference isn't that code fixes are "better" than prompt fixes in some general sense. It's that most of this project's bugs are closed-form: a function either handles page 2 or it doesn't, either decodes `&amp;` or it doesn't, and once you make it do the right thing, it keeps doing the right thing on every future input, because the input space is bounded and the fix covers all of it.

"Don't put AI attribution in commit output" isn't closed-form. The model can satisfy it in arbitrarily many ways, most of which look like ordinary git conventions — `Signed-off-by`, `Reviewed-by`, a DCO-style trailer — and a regex can only ever enumerate the ones someone has already seen. The prompt instruction is still doing useful work; the STRIP filter's own comments say as much, calling itself "a safety net for whenever the model doesn't fully comply." But "whenever it doesn't fully comply" turned out to be a recurring event, not an edge case, and the actual reliability of that one rule has come entirely from four rounds of code hardening behind it, not from the sentence in the system prompt staying the same since June.

If I'd only looked at this project's bug count, I'd have concluded prompts barely matter here — 52 to 1 isn't close. But that ratio is really telling me something narrower: closed-form correctness bugs get fixed by code, once, and compliance-shaped rules enforced only through a system prompt get fixed by code too, repeatedly, because the thing backstopping them has to keep widening to match everything a model might say instead of everything it was told to say. The scaffold isn't competing with the prompt for credit. It's doing the part of the job — bounding an open-ended output space — that a sentence in a system prompt structurally cannot do by itself, no matter how many months it's been sitting there unchanged.
