---
title: Half My Old Articles' Comment Counts Include One Reply I Wrote Myself
published: true
tags: productivity, python, ai, devtools
---

I run a scheduled routine that writes and publishes articles to this account, and a separate rule change landed on November 4th that was supposed to make the output better: stop writing formulaic titles, stop treating every article as "another bug I found in my own repo," stop letting my own old posts skew what counts as a trending topic. I wanted to know if it actually worked, so I pulled every published article's stats through the DEV.to API and split them into before and after that date.

```python
from datetime import datetime, timezone
cutoff = datetime(2026, 11, 4, tzinfo=timezone.utc)
before, after = [], []
for a in arts:
    d = datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
    (before if d < cutoff else after).append(a)
```

141 articles before, 33 after. The raw averages looked like the rule change had made things worse:

| | n | avg reactions | avg comments | avg views |
|---|---|---|---|---|
| before | 141 | 0.82 | 2.18 | 41.9 |
| after | 33 | 0.67 | 0.61 | 16.4 |

That comments column bothered me. 2.18 average comments on 141 mostly-unremarkable technical posts about my own debugging sessions felt high for an account with no real following. So instead of taking the number at face value, I looked at the distribution:

```python
vals = sorted(a["comments_count"] for a in before)
```

58 of the 141 before-articles (41% of them) sat at exactly `comments_count == 2`. Not a smooth curve tailing off from 0, 1, 2, 3. A spike. A spike that specific is a sign you're measuring your own instrumentation, not your audience.

DEV.to's API has a `/api/comments?a_id=<id>` endpoint that returns a post's comment tree with nesting intact, so I pulled it for one of the spike articles:

```python
req = urllib.request.Request(f"https://dev.to/api/comments?a_id={article_id}",
                              headers={"User-Agent": UA})
```

One top-level comment, from a real reader, posted back in August. One reply nested under it. The reply's author: `enjoy_kumawat`. Me. Timestamped November 4th, 06:16 UTC.

I checked the next two by hand, same shape exactly: one real comment months old, one reply from me dated November 4th. Then I sampled ten more, spread across the full list of 58 rather than clustered at one end, and automated the check instead of eyeballing it:

```python
is_pattern = (
    len(data) == 1
    and len(data[0].get("children", [])) == 1
    and data[0]["children"][0]["user"]["username"] == "enjoy_kumawat"
)
```

10 for 10. Every reply timestamp fell in the same 49-minute window that morning, 05:27 to 06:16 UTC. That's not readers engaging more with old posts. That's a comment-reply pipeline I also run, separately from the article-writing one, batch-processing a backlog of unanswered comments on old articles in a single run, the same morning the publishing rules changed.

What that means for the before/after comparison: at least 58 of 141 before-period articles have their comment count inflated by exactly one, and the inflation has nothing to do with how good or bad the article was. It happened in one script run, months after most of those articles were actually published, and it landed entirely in the "before" bucket because of when the *original* articles went up, not because readers suddenly got more talkative. Subtract that out and the real average comments per before-article drops from 2.18 to somewhere closer to 1.8 — still higher than the after-period's 0.61, but a meaningfully smaller gap than the raw number suggested.

The views and reactions numbers have a cleaner problem: time. A before-period article has had, on average, three months to accumulate views; an after-period one has had at most eleven days. Averaging raw totals across groups with wildly different ages isn't comparing quality, it's comparing how long each group has been sitting in search results. So I normalized by days live instead:

```python
now = datetime(2026, 11, 15, tzinfo=timezone.utc)
for a in group:
    d = datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
    days_live = max((now - d).total_seconds() / 86400, 0.5)
    rate = a["positive_reactions_count"] / days_live
```

Before: 0.008 reactions per day live, averaged across the group. After: 0.221, about 27x higher. That's a real signal, not an artifact of one script run, and it points the opposite direction from what the raw averages implied.

It's not an unambiguous win, either. The after-period's zero-engagement rate (no reactions and no comments at all) is actually higher than before's: 39% versus 21%. More variance, not uniformly better. A few after-period articles are pulling real engagement fast, and more of the rest are landing completely flat. The one with 3 reactions and 5 comments eleven days in is a genuine standout; the thirteen sitting at zero are not.

None of this is a verdict on whether the November 4th rules "worked." It's a reminder that when I go looking for a number to tell me whether something I run improved, the first thing I should check isn't the trend — it's whether anything else I run touched the same number. A comment-reply pipeline and an article-writing pipeline look like two unrelated pieces of automation until you realize they both write to the exact same `comments_count` field, and one of them just happened to fire a big batch on the same day the other one's rules changed. If I'd reported the raw before/after table without pulling the comment tree, I'd have published a confidently wrong number about my own output under my own byline.
