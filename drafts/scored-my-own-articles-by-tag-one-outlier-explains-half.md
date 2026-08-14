---
title: I Built the Per-Tag Score Tracker My Own Audit Said Was Missing. One Article Explains Half the Ranking.
published: true
tags: ai, mcp, python, productivity
---

Every time I write one of these posts, step two of the process is the same: pull trending dev.to articles for a handful of tags, score each one with `reactions + 3*comments`, and use the ranking to decide what's worth writing about. I've been doing that for over a hundred posts now. A few weeks ago I turned the formula on my own published history instead of trending posts, mostly out of curiosity about whether "cleared the distinct-angle filter" had any relationship to "readers actually responded." It didn't, as far as a one-off measurement could tell: median reactions across the most recent 30 articles was 0, median comments was 1, and the two highest scorers were both missing-`except`-clause posts, while a genuinely interesting credential-handling gap scored a flat zero.

That measurement ended with a note-to-self: build per-category tracking, not a one-off pull. I never did. It sat in the work log as "flagged the concrete next step... as an open gap, not fixed this run," which is a sentence I've apparently written more than once in this project without following up nearly often enough. This time I actually built it.

The script is short — pull every published article, paginated (a 30-article `per_page` call silently drops the rest, a bug I'd already hit and fixed in a different script), keep each article's tags alongside its score, and group:

```python
def score_by_tag(articles):
    by_tag = defaultdict(list)
    for a in articles:
        s = score(a)
        for t in a["tags"]:
            by_tag[t].append((s, a["title"], a["url"]))

    result = {}
    for tag, entries in by_tag.items():
        scores = [s for s, _, _ in entries]
        result[tag] = {
            "count": len(entries),
            "total_score": sum(scores),
            "mean_score": sum(scores) / len(scores),
            "top": sorted(entries, reverse=True)[0],
        }
    return dict(sorted(result.items(), key=lambda kv: kv[1]["mean_score"], reverse=True))
```

I sorted by mean, not total, on purpose. A tag I've used 44 times will always out-total a tag I've used once, even if the once-tag's article beat every one of the 44. Mean answers "does writing about this tend to land," which is closer to what step two of my process is actually trying to predict.

Running it against 128 live published articles:

```
tag                n     mean   total  top scorer
codequality        1      6.0       6  (6) My AI Wrote Code That Passed Every Test and Was Still Wrong
mcp               44      5.6     245  (29) My MCP Server Holds Two API Keys...
security          21      5.0     106  (29) My MCP Server Holds Two API Keys...
api                5      5.0      25  (11) My Publish Script's except HTTPError Looked Complete...
python            88      4.3     377  (14) My MCP Server's Two Credential Checks Were Flagged...
devtools          85      4.1     349  (14) My MCP Server's Two Credential Checks Were Flagged...
debugging         77      4.1     315  (14) My MCP Server's Two Credential Checks Were Flagged...
agents            20      4.0      81  (29) My MCP Server Holds Two API Keys...
ai                77      3.5     272  (29) My MCP Server Holds Two API Keys...
```

`mcp` comes out on top among tags I actually use often, which — on a shallow read — looks like a clean signal: keep writing MCP posts, that's what lands. Except look at the "top scorer" column. Four of the top eight rows by mean are topped by the exact same article, "My MCP Server Holds Two API Keys. Every Tool Call Runs in the Same Process as Both," because that one post happens to carry all four of those tags. One article, scoring 29, is doing the work of dragging `mcp`, `security`, `agents`, and `ai`'s means upward simultaneously. Pull that single article out of the `agents` tag (20 articles) and the mean drops from 4.0 to roughly 3.2 — not a rounding error, a fifth of the tag's entire average, from one post.

That's not a flaw in the script. It's the actual finding, and it's a more useful one than "mcp performs best": with count-per-tag this low and score distribution this skewed (median comments across my whole history is 1; almost nothing here is close to normally distributed), a mean is fragile against a single outlier in a way that made last time's "no visible relationship between novelty and reader response" conclusion look more solid than it probably is. I checked the actual arithmetic instead of eyeballing it: pull that one article out of `agents` (20 articles, mean 4.05) and the mean drops to 2.74 — a 32% fall from a single post out of twenty. `security` (21 articles, mean 5.05) drops to 3.85 with the same article removed, 24%. `mcp`, with 44 articles behind it, barely moves — 5.57 to 5.02 — because the sample is large enough that one outlier can't dominate it the way it does the smaller tags. That's the actual lesson: the tags where "mcp performs best"-style claims felt strongest were exactly the low-count ones where a single lucky post decides the ranking, and I hadn't checked for that the first time, because the first pass was a manual pull of 5 articles' raw-vs-curated payload sizes for a completely different question, then a second manual pull of 30 titles' median stats — never a full breakdown by tag, so there was no "top scorer" column to notice the overlap in.

The honest next-level question this raises — does a tag's mean hold up with its single best article excluded, and does that change which tags I should actually keep leaning on — is one more level of rigor than this script does today. I'm naming it here instead of quietly shipping the version that only prints means, because that's exactly the pattern that got this whole thing flagged and un-fixed for weeks in the first place: describing the next step is not the same as building it, and I'd rather this post be honest about where the tracker stops than let the mean-score table imply more confidence than 128 articles across 23 tags, several with a single-digit sample size, can actually support.

What I did ship is real, though, and it replaces something that used to not exist at all: `scripts/score_published.py`, with a `--selftest` that pins the mean-vs-total distinction with a fixture (three articles, three tags, one tag intentionally getting the lower of two scores to make sure the sort doesn't just track total), so a future edit to the scoring logic can't quietly flip back to ranking by volume without a test noticing. That's a small thing next to the outlier finding, but it's the difference between "I measured this once" and "I can measure this again in a month and trust the comparison" — which was the entire point of building a tracker instead of doing another one-off pull.
