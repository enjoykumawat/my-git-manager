---
title: 13 of My Repo's 53 Logged Bugs Share One Shape: A Fix That Never Reached Its Sibling
published: true
tags: debugging, python, ai, productivity
---

I keep a dated bug log for the small MCP server and publishing pipeline I run this account through — `docs/project_notes/bugs.md`, 53 entries since June. I'd noticed, reading back through months of it, that a lot of the entries felt the same even though they were about different functions. I'd never actually counted how many, so this week I read all 53 start to finish and tagged each one by shape instead of by file.

The shape I was looking for: a fix lands in one function, and a second function — a copy in another file, a sibling code path, an identical block pasted somewhere else — keeps the exact bug the first one just lost. Not "a new, unrelated bug." The *same* bug, still live, somewhere the first fix never reached.

13 of the 53 entries are that shape. A little over a quarter of everything in this log.

## What counts, with receipts

Some of these are explicit about it in their own title. From the log itself:

- 2026-08-09 — "`server.py`'s `create_article` duplicate-title check never got the pagination fix its twin in `publish_devto.py` got a day later."
- 2026-08-08 — "`server.py`'s `_gh`/`_dev` and `reply_comments.py`'s `api()` still only caught `HTTPError`, not `URLError` — the sibling fix `publish_devto.py` got 5 days earlier never made it to either."
- 2026-07-29 — "`server.py`'s `generate_commit_message` never got the 2026-06-21 system-prompt hardening that `git_commit.py` did."
- 2026-08-12 — "`server.py`'s `load_env()` was the one sibling of four that neither quote-stripped values nor whitespace-stripped keys."

Others don't use the word "sibling" or "twin" but are the identical pattern once you read the root cause: `check_key_facts.py` validated two of three memory files and left the third — the one `CLAUDE.md`'s own protocol says to search first — with no check at all (2026-08-15). `pending()` learned to walk a branching comment thread; `audit()`, the sister function answering a different question over the same tree shape, never did (2026-08-17). `ADR-002` restated a phantom-file claim `ADR-001` had already been corrected for, in the same document, because the drift checker's own exemption was scoped to a filename instead of to the specific text that explained it (2026-08-12).

None of these are exotic. Every one is: two places in the codebase do roughly the same thing, something taught one of them better, and nobody went looking for the other.

## Why I didn't just grep for "sibling"

A text search for "sibling," "twin," "copy," or "identical" in the log gets you most of the way but misses entries that describe the pattern without naming it — the `check_key_facts.py` gap above never says "sibling," it says the third file "had no equivalent check at all." So I read every entry's actual root-cause paragraph and classified by hand instead of trusting a keyword match. The keyword search alone found 6 of the 13; reading found the other 7.

## The live check: is this still happening right now

Classifying the past is one thing. I wanted to know if the repo, as it sits today, still has this shape of risk live in it — not just logged, but present. So I ran a small AST scan over every top-level `.py` file and everything in `scripts/`, looking for function names defined in more than one file:

```python
import ast, pathlib, collections

files = list(pathlib.Path(".").glob("*.py")) + list(pathlib.Path("scripts").glob("*.py"))
names = collections.defaultdict(list)
for f in files:
    tree = ast.parse(f.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names[node.name].append(str(f))

for n, fs in sorted(names.items()):
    if len(set(fs)) > 1:
        print(n, "->", fs)
```

Output, as of this run:

```
_claude_subprocess_env -> ['git_commit.py', 'server.py']
load_env -> ['reply_comments.py', 'server.py', 'publish_devto.py',
             'scripts/score_published.py', 'scripts/list_all_published_titles.py']
main -> ['publish_devto.py', 'scripts/score_published.py',
         'scripts/check_key_facts.py', 'scripts/list_all_published_titles.py']
```

`load_env()` is the one the bug log already has an entry about — the 2026-08-12 fix called it "the one sibling of four," meaning four copies existed at the time, one of them (`server.py`'s) behind the other three. I pulled the actual source of all five copies that exist today, not just the count:

```python
# reply_comments.py / publish_devto.py / score_published.py /
# list_all_published_titles.py — all four currently do this:
os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# server.py — the one the 2026-08-12 entry was about — does the same now too.
```

Good news first: all five are in sync. The fix did propagate. But the count itself has quietly drifted past what the fix's own paper trail says. `server.py`'s comment and three of the other files' comments still describe this as "the one sibling of four" — language written when `scripts/score_published.py` and part of `scripts/list_all_published_titles.py`'s current form didn't exist yet. Two more copies got added after the postmortem was written, both already correct, and neither one updated the comment that counts them. The behavior never drifted. The documentation describing how many places that behavior lives already has.

That's a smaller version of the same root cause as the 13 bugs above, one layer up: the thing that goes stale when you copy logic isn't only the logic. It's also whatever comment, docstring, or ADR entry tried to say how many copies exist.

## What I'm actually going to change because of this

Not "extract a shared `env.py` module" — four of these five copies take different arguments (`path=None` vs `path` required vs no argument at all, resolved against different base directories), so a shared function would need a signature that serves all of them, and that refactor has its own risk of becoming entry #14. Low-value churn for a function that's six lines long in each spot.

What I will do: when a fix to one of these functions closes out, the fix note stops saying "the other N copies" from memory and instead runs the same AST scan above and pastes its literal output into the entry. A comment that names a count is a claim that goes stale the first time someone adds a sixth script; a comment that says "run this scan, here's what it printed on $DATE" stays honest by construction, because the next person reading it can rerun it in ten seconds and see whether it's still true.

The broader takeaway, if there is one: "did I fix the bug" and "did I fix every place the bug lives" are different questions, and this log answering the first one 53 times and the second one correctly only about 75% of the time isn't a reason to feel bad about it — it's a measurable rate, and now that it's measured, the next fix has a cheap, concrete check to run before it gets marked done: grep the function name, not just the file you're already looking at.
