---
title: I Measured What My Curated MCP Tool Output Is Actually Saving
published: true
tags: mcp, llm, python, ai
---

Every tool in my Developer Presence MCP server returns a hand-picked dict, never the raw API response. I did that from day one because it felt obviously correct — why hand a model twenty fields when it needs six. I never actually measured what it was saving. I finally ran the numbers this morning, on real data from my own account, and the size of the gap surprised me enough that I want to show the actual breakdown instead of just asserting "less is more."

### the tool in question

`list_articles` in `server.py` wraps DEV.to's `/articles/me/published` endpoint:

```python
@mcp.tool()
def list_articles(per_page: int = 10) -> list:
    """List your published DEV.to articles."""
    articles = _dev(f"/articles/me/published?per_page={min(per_page, 30)}")
    return [
        {
            "id": a["id"],
            "title": a["title"],
            "published": a.get("published"),
            "url": a.get("url"),
            "reactions": a.get("positive_reactions_count", 0),
            "comments": a.get("comments_count", 0),
            "page_views": a.get("page_views_count", 0),
        }
        for a in articles
    ]
```

Seven fields. The raw API response per article has twenty, including `body_markdown` — the entire rendered article text — and a nested `user` object with the author's name, username, avatar URL, and Twitter handle, none of which this account's own tool calling itself will ever need to know about itself.

### running it for real

I pulled 5 of my own published articles through both paths — the raw `_dev()` call this tool wraps, and the curated list it returns — and diffed the payload sizes:

```python
raw = _dev("/articles/me/published?per_page=5")   # list of 5 raw dicts
curated = [{"id": a["id"], "title": a["title"], ...} for a in raw]  # the tool's actual output

len(json.dumps(raw))       # 40613 bytes
len(json.dumps(curated))   # 1649 bytes
```

24.6x. Not a rounding difference — a quarter of the payload survives curation. At roughly 4 characters per token, that's the difference between feeding an agent about 10,150 tokens of article data and about 410, for the exact same five articles, the exact same underlying facts (title, id, url, published state, three engagement numbers).

### where it actually goes

I broke down one article's raw JSON by field size to see what's driving the ratio, expecting it to be spread out. It isn't:

```
6963  body_markdown
 675  user
 126  url
 126  canonical_url
 112  path
 110  title
 105  description
  97  slug
  49  tag_list
  26  published_at
  ...
```

`body_markdown` alone is 86% of one article's raw payload. `user` is most of what's left — an object with five sub-fields for an account that already knows who it is, since every call in this server is scoped to `enjoykumawat`/`enjoy_kumawat` by hardcoded constant (see `ADR-003` in this repo's own decision log — hardcoding the username was a deliberate call specifically to avoid this kind of redundant per-call identity data). Everything past those two fields — `canonical_url`, `path`, `slug`, `tag_list`, `published_at` vs `published_timestamp` — is genuinely small individually, and none of it is what makes the response expensive. Two fields are.

### why this matters more than it sounds like it should

None of my MCP tools' docstrings mention token cost, and none of the fixes logged against this codebase over the last seven weeks were about output size — they're about correctness (a docstring promising "limit: 1-100" that a negative number sailed straight through, a duplicate-check that only looked at the newest 30 articles, an endpoint that returned drafts when the tool claimed "published only"). Output shape got zero scrutiny by comparison, on the assumption that curating fields was self-evidently fine and there was nothing left to check.

That assumption happened to be right here, but only because whoever wrote `list_articles` guessed correctly that `body_markdown` wasn't worth returning. It's easy to imagine the same tool, six months from now, growing a `summary` field that someone populates by slicing the first 500 characters of `body_markdown` for "context" — a reasonable-sounding addition that quietly drags the full-text field's cost back into every call, defeating the curation without anyone touching the field list that actually gets returned. A one-line addition, no new field in the *output* to review, and the 24.6x gap collapses back toward the original ratio. The failure mode isn't "someone removes the curation" — it's "someone adds one field back in, for a good reason, without re-running the number that justified curating in the first place."

The concrete habit I'm taking from this: when a tool's return shape changes, diff the byte size against the raw response it wraps, the same way `update_article` in this server already diffs before/after values on every write instead of trusting that a change did what it claimed. A tool that returns curated data because "obviously less is more" and a tool that returns curated data because someone actually measured a 24x gap and re-checks it on every schema change are doing the same thing today. They stop being the same thing the first time a well-intentioned field gets added back.

```python
def payload_cost(raw, curated):
    r, c = len(json.dumps(raw)), len(json.dumps(curated))
    return {"raw_bytes": r, "curated_bytes": c, "ratio": round(r / c, 1)}
```

Three lines, run once per tool, next to the selftest block every script in this repo already has for its actual logic. Cheap enough that "I never measured it" isn't really an excuse the second time.
