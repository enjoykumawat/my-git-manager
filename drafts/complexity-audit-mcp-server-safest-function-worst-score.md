---
title: "A Cyclomatic Complexity Audit of My Own MCP Server: The Fix With the Most Safety Checks Scored the Worst"
published: true
tags: python, mcp, devtools, debugging
---

A trending post this week argued that "AI code is unmaintainable" is the wrong complaint, because most human-written code is just as bad, and nobody's actually measuring either one. That's a fair jab, and it's an easy one to make without numbers. I run a small MCP server (`server.py`, 8 tools) and a handful of supporting scripts that publish this blog, and I've fixed real bugs in them over the past few months. I had never once run a complexity metric against any of it. So I did, before writing a word of opinion.

## The script

No new dependencies — `ast` is stdlib, and cyclomatic complexity is just "1 plus the number of decision points a function can branch on":

```python
import ast

def cyclomatic(node):
    complexity = 1
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.For, ast.While, ast.Try,
                           ast.ExceptHandler, ast.With, ast.BoolOp)):
            complexity += 1
        if isinstance(n, ast.comprehension):
            complexity += len(n.ifs) + 1
    return complexity

def max_nesting(node):
    best = [0]
    def walk(n, d):
        best[0] = max(best[0], d)
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
                walk(child, d + 1)
            else:
                walk(child, d)
    walk(node, 0)
    return best[0]
```

Walk every `.py` file, collect every function, record its line count, cyclomatic complexity, and max nesting depth. I ran it against all 7 Python files in the repo — `server.py`, `publish_devto.py`, `reply_comments.py`, `git_commit.py`, and three small `scripts/` helpers.

## The numbers

75 functions total. Mean length: 16.5 lines. Mean cyclomatic complexity: 4.0. By itself that looks fine — most functions here are short and boring, which is what you want. But means hide where the risk actually lives. Sorted by length, the top of the list isn't boring at all:

```
file          func              lines  cc   nest
server.py     update_article    126    15   1
server.py     _null_field_regression  63   9   1
publish_devto.py  main          59     15   2
publish_devto.py  already_published  47  8   2
server.py     _gh               46     8   2
```

`update_article` isn't just the longest function in the codebase — at 126 lines it's nearly twice the next entry, and its cyclomatic complexity of 15 is the highest of all 75 functions measured. Five functions exceed 40 lines; three exceed a complexity of 10. That's not "spread evenly across sloppy code." It's concentrated in one place.

## Why that one function

`update_article` PUTs changes to a live DEV.to article by id. I went back and reread it next to `bugs.md`, where every change to this function is logged with a date and a root cause, and the complexity isn't random — it's five separate hardening passes stacked on top of each other, each one closing a real incident:

- **2026-07-27**: a wrong or hallucinated `article_id` used to silently overwrite whatever article it pointed at, with zero trace. Fix: fetch the article's current state before writing, log the before/after, return a diff.
- **2026-07-29**: that diff and log were hardcoded to a fixed `{title, published}` pair. A `body_markdown`-only write — the tool's main real use — showed a diff where nothing looked changed, while the actual body had just been silently replaced.
- **2026-08-15** (first): the `confirm=True` gate proved the *caller* meant to write, but said nothing about whether the article was still in the state the caller reviewed before confirming. Fix: a fingerprint of the previewed content, checked again at write time, that fails the write closed if anything changed in between.
- **2026-08-15** (second): `create_article`'s duplicate-published-title guard only ran on its own code path. `update_article` could reach the identical outcome — two live articles with the same title — two different ways that guard never covered.
- **2026-08-15** (third): a write that doesn't touch live content (a draft, or a call where every field is already a no-op) never needed any of the above gates, and the function had to be taught to tell that case apart from one that does.

Each of those fixes is a few lines of real logic: an extra early return, an extra field compared, an extra guard clause. None of them is bloat on its own. But they don't compose for free — every added guard is another branch `cyclomatic()` counts, and the five together are why this one function is the single biggest complexity outlier in a 75-function codebase where the *average* function has a complexity of 4.

Here's the shape of just one of those passes, the fingerprint staleness check, so this isn't an abstract claim:

```python
if live_content_write and expected_fingerprint is not None \
        and expected_fingerprint != fingerprint:
    return {
        "id": article_id,
        "url": before.get("url"),
        "applied": False,
        "reason": "stale — the live article changed since the diff you "
                  "approved was generated; re-preview and re-approve "
                  "against the current content before writing",
        "fingerprint": fingerprint,
        "diff": {field: {"before": before.get(field), "after": article.get(field)}
                 for field in article},
    }
```

Reasonable in isolation. But it's one of four conditionals in the function that each build and return the same `diff` shape under a slightly different reason string, which is most of where the extra branches and the extra lines come from.

## The actual finding

The trending post's point was that human-written code is unmaintainable too, so stop singling out AI. Measuring my own repo gave me a narrower and more useful claim: the complexity here didn't come from carelessness, it came from safety. Every one of the five passes on `update_article` made the tool strictly harder to misuse — and every one made the function measurably harder to read in one sitting. Those aren't opposite outcomes I can pick between; in this function they're the same outcome. A linter flagging `cyclomatic complexity: 15` would be right that this function is risky to touch — and wrong to imply the fix is "simplify it," since simplifying it is exactly what would bring back the 2026-07-27 bug.

Two smaller findings from the same run, for anyone who wants to try this on their own repo:

- `max_nesting` found `load_env` at depth 4 in `server.py` — a small `.env` parser that's duplicated, nearly line-for-line, in five of the seven files. None of them import a shared helper. That's real duplication a complexity script finds for free, as a side effect, without being built to look for it.
- Looking only at the mean (4.0) would have told me nothing was wrong. The outliers are where the actual risk sits, and a repo-wide average will always dilute them.

If you're running something similar against your own code: don't stop at the top-line average. Sort by complexity, read the top 3, and check whether each one's `bugs.md` (or git log, or commit history — whatever you've got) explains why it looks that way. If it does, the complexity is a receipt, not a red flag. If it doesn't, you've found something worth a second look before you touch it next.
