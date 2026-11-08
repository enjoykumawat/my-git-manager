---
title: Do Grep and AST Agree on Which Functions Are Dead Code?
published: true
tags: python, mcp, debugging, productivity
---
I wanted a quick dead-code pass over the Python files in my `my-git-manager` repo (`server.py`, `reply_comments.py`, `publish_devto.py`, `git_commit.py`, and three scripts under `scripts/`) and had two options sitting right there in the stdlib: a regex over the source text, or `ast`. I assumed one would obviously be better and ran both for real to see by how much.

The regex version is the kind of thing you'd write in thirty seconds:

```python
import re

def grep_heuristic(src):
    defs = re.findall(r'^def (\w+)\(', src, re.MULTILINE)
    flags = []
    for name in defs:
        total_calls = len(re.findall(re.escape(name) + r'\(', src))
        if total_calls - 1 <= 0:   # minus the def line itself
            flags.append(name)
    return defs, flags
```

The AST version walks the real parse tree and checks every `Name` and `Attribute` node instead of grepping text:

```python
import ast

def ast_heuristic(src, path):
    tree = ast.parse(src, filename=path)
    defs, called_names = [], set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append(node.name)
        if isinstance(node, ast.Name):
            called_names.add(node.id)
        if isinstance(node, ast.Attribute):
            called_names.add(node.attr)
    return defs, [d for d in defs if d not in called_names]
```

Across all seven files, here's what each one actually flagged:

```
grep total flagged: 5
ast total flagged:  9
grep-only (ast missed): set()
ast-only (grep missed): {
  ('scripts/list_all_published_titles.py', '__enter__'),
  ('scripts/list_all_published_titles.py', '__exit__'),
  ('publish_devto.py', '__init__'),
  ('server.py', 'create_article'),
}
agreed on both: {
  ('server.py', 'get_github_profile'),
  ('server.py', 'generate_commit_message'),
  ('server.py', 'list_articles'),
  ('server.py', 'get_article_stats'),
  ('server.py', 'get_repo_stats'),
}
```

The dunder methods (`__init__`, `__enter__`, `__exit__`) are an easy miss to explain: Python calls them implicitly through the object protocol, never by writing their literal name at a call site, so neither heuristic should expect to see them "called" in source text. That's a known blind spot for both approaches, not a disagreement between them — grep happened not to flag them here only because of what's near them in the file, not because it understood anything about dunder semantics.

The actual disagreement is `create_article`, and it's a real example of regex's biggest weakness: it can't tell a call from a mention. I checked where grep thought it saw a call:

```python
def create_article(title: str, body_markdown: str, ...) -> dict:
    ...
# 90 lines later, inside another function's docstring:
"""
create_article(title="X", published=False) — the duplicate check is
...
"""
```

`re.findall(r'create_article\(', src)` matches that docstring line exactly as happily as it would match a real call — it's just text, and `create_article(` is `create_article(` whether it's Python being executed or English describing Python. The AST walker doesn't have this problem, because a docstring is a string literal `ast.Constant` node, not a `Call` or `Name` node; it never saw a "call" there to begin with. On this specific file, that's the difference between grep correctly reporting 5 unused functions and silently clearing a 6th one that was never actually called anywhere — a false negative hiding behind an unrelated comment.

But both tools agree on calling all five of those `server.py` functions "dead," and both are wrong in the same way. `get_github_profile`, `get_repo_stats`, `list_articles`, `get_article_stats`, and `generate_commit_message` are MCP tools, registered with `@mcp.tool()` and invoked by an MCP client through the protocol — never by another line of Python in this file calling their name directly. Neither static heuristic can see that kind of call, because it isn't a call in the AST or in the text at all; it's a dispatch table built at runtime from string tool names coming over a transport, resolved by the FastMCP framework after the fact. A tool function in this codebase can have real, live callers every day and still read as 0-reference dead code to any analysis that only looks at the file it's defined in.

Timing was the other thing I measured, since I had the numbers anyway:

```
server.py (1141 lines): grep 2.17ms, ast 8.03ms  (~3.7x)
reply_comments.py (460 lines): grep 0.72ms, ast 2.78ms  (~3.9x)
```

AST parsing costs roughly 4x the regex pass across every file I measured, consistently enough that it's clearly the tree construction overhead, not noise. For a one-off check on a file this size that's still under 10 milliseconds — irrelevant in absolute terms, but it's not "free," and on a much larger codebase run frequently it's the kind of multiplier that does start to matter.

So: for a quick first-pass sweep where occasional false negatives are tolerable, grep is three times cheaper and catches everything AST caught in my agreement set. For anything where the result actually drives a decision — deleting a function, flagging it in a PR review — the regex isn't just less precise, it's precise in a way you can't predict without rereading every result by hand, because you don't know whether a given hit is a real call or an English sentence that happens to look like one until you check. And for any codebase where some fraction of your "unused" functions are actually registered callbacks, RPC handlers, Flask routes, or MCP tools — invoked by name from outside the file, through a mechanism neither tool can trace — both approaches need a third check layered on top: an allowlist, a decorator-aware exclusion, or just accepting that "no in-file callers" and "dead code" are two different claims that happen to usually overlap and sometimes don't.
