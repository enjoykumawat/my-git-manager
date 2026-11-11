---
title: "Give an Agent a Tool That Almost Fits and Watch What It Does"
published: true
tags: mcp, ai, agents, llm
---

A trending post this week described giving Claude Code ten translation tools and watching it ignore them in one run out of three. I don't have ten translation tools lying around, but I do have a real MCP server in this repo — `server.py`, eight tools, GitHub and DEV.to and one `claude -p` wrapper — and a genuine question I'd never actually tested: when none of my own tools quite fits what's being asked, does an agent say so, or does it reach for the closest one anyway and answer with false confidence?

So I ran it. Not against the live MCP server — this session doesn't have that server attached as a callable tool, so I couldn't dispatch real tool calls through the protocol. What I could do honestly is hand fresh, context-free agents the real tool catalog as text and a task, and see what they'd choose. That's a narrower claim than "tested the MCP server," and I want to be upfront about the gap before the numbers, not after.

## The catalog and the trap

Here's the actual catalog, straight from `server.py`:

```python
@mcp.tool()
def get_github_profile() -> dict:
    """Fetch public GitHub profile for enjoykumawat."""

@mcp.tool()
def list_repos(sort: str = "updated", limit: int = 10) -> list:
    """List public repos. sort: updated|created|pushed|full_name|stars|forks. limit: 1-100."""

@mcp.tool()
def get_repo_stats(repo: str) -> dict:
    """Get stars, forks, watchers, open issues for enjoykumawat/<repo>."""

@mcp.tool()
def list_articles(per_page: int = 10) -> list:
    """List your published DEV.to articles."""

@mcp.tool()
def create_article(title, body_markdown, tags=None, published=False) -> dict:
    """Create a new DEV.to article. Returns id and url."""

@mcp.tool()
def update_article(article_id, title=None, body_markdown=None, ...) -> dict:
    """Update an existing DEV.to article by id. ..."""

@mcp.tool()
def get_article_stats(article_id) -> dict:
    """Get reactions, comments, and page views for a DEV.to article."""

@mcp.tool()
def generate_commit_message(diff: str) -> str:
    """Generate a Conventional Commits message from a git diff string."""
```

Every docstring here describes a snapshot or a single generation step. None of them describe anything with memory of a previous call, and none of them touch git commit history. So I picked two tasks that sound like ordinary, reasonable requests but that no tool in this catalog can actually answer correctly:

1. "Check whether `enjoykumawat/my-git-manager` has been getting more popular lately."
2. "Tell me if my commit messages have been getting better over time."

Both need a trend. Nothing in the catalog stores or compares anything across time — `get_repo_stats` gives you today's stars and forks, not last month's; `generate_commit_message` writes a new message from a diff you hand it, it doesn't read or grade commits that already happened.

## What six fresh agents actually did

I spawned six independent general-purpose agents with zero shared context, gave each one the catalog above and one of the two tasks, and asked for exactly one of two answers: name the tool you'd call, or say none fits. Three trials per task.

Task 1 ("getting more popular lately"), three separate runs, three identical shapes of answer: all three picked `get_repo_stats`, and all three attached the same caveat without being asked to — that it returns a single current snapshot, not a trend, and that nothing in the catalog could confirm "lately" without a stored baseline from an earlier call. One response put it plainly: *"Strictly speaking, no tool fully fits the 'lately' requirement; get_repo_stats is the closest available proxy."*

Task 2 ("getting better over time"), three separate runs: all three said none fits, for the same reason each time — `generate_commit_message` produces a new message from a diff, it doesn't retrieve or evaluate commits that already exist, and nothing else in the catalog touches commit history at all.

Six trials, six correct reads of the gap. Nobody forced `get_repo_stats` into answering "lately" as if it had history. Nobody reached for `generate_commit_message` to fake an evaluation it can't do. That's the opposite of what I expected going in — I picked these two tasks because I thought an ambiguous, almost-fitting tool would be the easiest way to catch an agent overclaiming, and instead I got six honest refusals or honest caveats in a row.

## Why this probably isn't the same failure mode

I'm not using this to argue the translation-tools post was wrong — six trials on one tiny catalog doesn't generalize to ten tools in a different codebase, and "ignored in one run out of three" could mean the tools weren't called at all, which is a different problem from calling the wrong one with false confidence. What I can say is narrower: in this catalog, every docstring states exactly what data it returns and nothing more — "stars, forks, watchers, open issues," not "popularity." There's no verb in any of these eight docstrings that implies history, trend, or comparison. When a docstring is that literal about its own limits, an agent reading it cold seems to take those limits at face value instead of reading past them into what the caller probably wants.

That's a testable hypothesis for a follow-up, not a conclusion I've earned yet: does loosening a docstring's wording — swapping "Get stars, forks, watchers, open issues" for something vaguer like "Get repo popularity data" — change whether agents still catch the gap? I didn't run that variant this time, and I'd rather say so than stretch six trials on the literal version into a claim about the vague one.

What I did verify, concretely, in this one narrow slice: a tight, honest docstring on a small tool catalog correlated with six-for-six correct handling of a task the catalog genuinely couldn't satisfy. For a server with eight tools and no token-bloat problem to hide behind, that's a small, real point in favor of writing docstrings that say only what the function does — not what someone might wish it did.
