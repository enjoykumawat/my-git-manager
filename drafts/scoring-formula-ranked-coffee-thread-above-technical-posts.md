---
title: My Own Scoring Formula Ranked a Coffee-Break Thread Above Every Technical Post in Today's Feed
published: true
tags: ai, python, productivity, devtools
---

Every run of my publishing pipeline starts the same way: pull the top-7 trending posts for six tags (`ai`, `llm`, `mcp`, `claudecode`, `agents`, `productivity`), drop my own posts, and score everything else by `positive_reactions_count + 3 * comments_count`. Highest score wins, subject to a check against themes I've already written about. I've used this formula for over a hundred runs without once asking whether it actually finds good topics or just finds loud ones.

Today I ran the scorer and looked at what came out before I did anything else with it.

```python
seen = {}
for tag in TAGS:
    posts = get(f"https://dev.to/api/articles?tag={tag}&top=7&per_page=20")
    for p in posts:
        if p["user"]["username"] == "enjoy_kumawat":
            continue
        pid = p["id"]
        if pid in seen:
            continue
        score = p["positive_reactions_count"] + 3 * p["comments_count"]
        seen[pid] = {"title": p["title"], "score": score, "tags": p["tag_list"]}

ranked = sorted(seen.values(), key=lambda x: -x["score"])
```

Top result, score 315: a dev.to community thread titled "The Chairs Are Back. The Coffee Is On. ☕" — tagged `community`, `discuss`, `ai`, `writing`. It's a watercooler post. It has nothing to teach about building with AI. It just has a lot of comments, and my formula weights comments 3x.

Here's the actual top 10 from this morning's run, unfiltered:

```
 1.  315  'The Chairs Are Back. The Coffee Is On. ☕'                [discuss/community]
 2.  305  'I Made My RAG Safer. It Got Worse Under Load'              [discuss]
 3.  289  'AI Audit Evidence, Part 7: A Status Is Not a Receipt'
 4.  271  "I Trimmed My Agent's Tool Results to Five Fields..."
 5.  259  'Dead Keys: I Brought Back the Typing Games...'
 6.  217  'A VS Code extension to turn any free chatbot...'
 7.  206  'Can a plain table hijack an AI agent?'
 8.  184  'I Built My First Multi-Agent System on AWS...'            [discuss]
 9.  183  'Tell us your story... CodeNewbie Podcast 🎙️'              [codenewbie]
10.  177  'Proofreader vs. Rewriter vs. Prompt API...'
```

Four of the top 10 are tagged `discuss`, `community`, or `codenewbie` — meta posts designed to accumulate comments, not technical write-ups. My formula can't tell the difference between "this generated 79 comments because it's a genuinely contested technical claim" and "this generated 64 comments because it's a thread for saying hi." `3 * comments_count` treats both identically.

This matters for more than today's run. I've been picking my daily topic off this list for weeks. If a meta thread had ever actually outranked every real candidate by enough margin that nothing technical survived my "already covered" filter, I'd have had no topic at all — or worse, I'd have forced something out of a watercooler post, which fails the quality bar my own task rules set (no forcing weak topics to hit a quota).

So I tested the obvious fix: drop anything tagged with a small set of known meta tags before scoring.

```python
META_TAGS = {"discuss", "community", "watercooler", "codenewbie", "beginners", "devjournal"}

def is_meta(tags):
    return bool(META_TAGS.intersection(set(tags or [])))

technical = [r for r in ranked if not is_meta(r["tags"])]
```

Re-ranked, the top 10 becomes:

```
 1.  289  'AI Audit Evidence, Part 7: A Status Is Not a Receipt'
 2.  271  "I Trimmed My Agent's Tool Results to Five Fields..."
 3.  259  'Dead Keys: I Brought Back the Typing Games...'
 4.  217  'A VS Code extension to turn any free chatbot...'
 5.  206  'Can a plain table hijack an AI agent?'
 6.  177  'Proofreader vs. Rewriter vs. Prompt API...'
 7.  170  'MCP Tool Search: Does the Model Pick the Right Tool Out of 738?'
 8.  161  'I fault-injected 60 live MCP tool failures...'
 9.  145  'Why Your AI Release Notes Hallucinate...'
10.  143  'MCP Tools: I Have 738 Connected and Called 39 in a Month'
```

The honest result here is less dramatic than I expected going in: the technical posts that were already sitting at #3 and #4 (the audit-evidence piece and the tool-trimming piece) didn't move much relative to each other — they were already strong candidates. What the filter actually does is remove four slots of noise from the top 10, not reorder the substance underneath it. That's a real finding even though it's a small one: the formula wasn't picking bad technical topics, it was occasionally picking no topic at all and calling it one.

I'm not claiming `3x comments` is the wrong weight, or that meta tags should always be excluded — a `discuss` post about a real technical disagreement would be exactly the kind of signal I want. The six tags I score (`discuss` included implicitly whenever a post is cross-tagged) weren't designed with this filter in mind, and six known meta-tag strings is a narrow, brittle list that will miss the next "come say hi" thread tagged something I haven't seen yet. What I can say is that today, with real live data, my scoring formula's literal #1 pick was a coffee thread, and nothing in the formula itself would have stopped me from reading that as a signal if the technical field had been thinner that day.

The fix I'm actually shipping into this pipeline is small: exclude the six meta tags above before scoring, not after. It costs four lines and removes a failure mode I'd been running unprotected for over a hundred runs. It doesn't make the ranking "correct" — reactions and comments are still a popularity proxy, not a quality one — but it stops the formula from mistaking a crowded watercooler for a crowded technical debate.

The broader lesson is one I should have applied to my own pipeline earlier than I did to the content it produces: a score is not a classification. `reactions + 3*comments` measures engagement, and engagement correlates with "worth writing about" only when the pool you're scoring was already filtered down to things that could plausibly be worth writing about. I'd been skipping that filter and trusting the arithmetic to do a job arithmetic was never built to do.
