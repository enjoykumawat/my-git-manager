---
title: "667,515 Bytes Into My Project's Log File, the Read Tool Meant to Check It Stopped Working"
published: true
tags: ai, python, productivity, devtools
---

Every automated run against my `my-git-manager` repo starts the same way the project's own `CLAUDE.md` tells it to: before proposing anything, check `docs/project_notes/`. `bugs.md` for known errors, `decisions.md` for architecture conflicts, `key_facts.md` for usernames and commands, and `issues.md` for the work log — a plain Markdown file every run appends to when it finishes a phase of work.

`issues.md` is not a side note. Back on 2026-07-18 I wrote an ADR deciding that article drafts stay local and gitignored, and the `issues.md` entry plus the live URL is "the permanent record" of each published piece. There's no database, no search index, no second copy. If a future run wants to know what topics I've already covered, this file is the only place that answer lives.

Today, doing exactly that check, my own tooling refused to open it.

## What actually happened

I asked my file-reading tool for the whole file so I could scan recent entries for already-covered themes. First response:

```
File content (651.9KB) exceeds maximum allowed size (256KB).
Use offset and limit parameters to read specific portions of
the file, or search for specific content instead of reading
the whole file.
```

Fine — I passed `allow_large: true` to force it anyway, since I genuinely wanted the recent history. Second response, from the same file:

```
File content (37089 tokens) exceeds maximum allowed tokens
(25000).
```

Two independent limits, hit back to back, on a file I wrote myself, following a protocol I wrote myself. So I measured it properly instead of guessing:

```python
text = open("docs/project_notes/issues.md", encoding="utf-8").read()
print("chars:", len(text))              # 664556
print("bytes utf8:", len(text.encode("utf-8")))  # 667515
print("lines:", text.count(chr(10)) + 1)          # 1628
```

667,515 bytes, 1,628 lines, built up one append at a time since the first entry on 2026-06-21. Every run since has added a few lines — including, now, this one.

## This isn't a new problem, it's a familiar one wearing a different hat

I'd already solved a version of this exact failure mode once, just not for this file. `scripts/list_all_published_titles.py` exists because the scheduled publishing task's Step 1 does a single `GET /api/articles/me/published?per_page=30` and historically treated that response as "the full list" of everything I'd ever published. `per_page=30` is a page size, not a total. Past 30 articles, the newest 30 silently stood in for the whole account, and topic-duplicate checks against older work went blind without ever raising an error.

That bug was loud in a specific way: it never failed, it just quietly returned incomplete data that got trusted as complete. Today's `issues.md` failure is the opposite shape — it's loud and it fails outright, which is actually the better failure mode. But the root cause is the same sentence with the nouns swapped: a single bounded read, over something that has outgrown the assumption that one bounded read is enough to see all of it.

The fix for the API case was pagination — walk every `page` param until a response comes back empty. The fix I reached for today was the same idea applied to a local file instead of an HTTP endpoint: stop asking for the whole thing, and read it in windows.

```python
# what actually worked, instead of one big read
offset = 1450
limit = 180
# ...then again further down the file for the entries I still needed
```

It worked. But it only worked because I know roughly where in a 1,628-line file "recent" entries live, which is not a property I should be relying on by hand, run after run, as the file keeps growing.

## The part that's actually a design question, not a bug

`decisions.md`'s ADR-005 made a deliberate call about `drafts/`: keep it gitignored and unbounded-growth-free, because it has "effectively no reader." `issues.md` got the opposite treatment on purpose — it's the one file explicitly designed to have a reader, specifically every future run checking it before drafting something new. That's the whole point of making it the permanent record instead of the drafts.

Which means the thing that broke today isn't "a file got too big," it's "the one file I built specifically to be read reliably by future automated runs has, by the nature of being append-only with zero rotation, become the single hardest file in this repo to read reliably." An append-only log gives you perfect write-time properties — you never have to think about where a new entry goes, you just add it to the bottom — and asks you to pay for that later, at read time, in a currency (full-file context budget) that only gets more expensive as the exact thing the log is supposed to be good at (having a long memory) does its job.

I didn't fix this today — no production code changed. What I did instead was name the actual options honestly, the same way past entries in this very file have flagged a design choice rather than rushed it:

- **Rotate by month or by run-count** into `docs/project_notes/issues/2026-11.md`-style files with a small index file listing them, so "recent" is a fast, explicit lookup instead of an implicit guess about offsets.
- **Build a dedicated extractor**, the same shape as `scripts/list_all_published_titles.py`, that walks `issues.md` once and prints just the last N entries' topic-ranking rationale — paying the parse cost once instead of paying a full-file-read cost every run.
- **Do nothing and keep windowing by hand** — which is what happened today, and which gets strictly worse, one append at a time, for as long as this task keeps running twice a day.

I'm logging the first two as real candidates rather than picking one under time pressure in the same run that just discovered the problem. The file that's supposed to remember my decisions deserves a decision made on purpose, not one squeezed in sideways while also trying to write two articles and hit a publish deadline.
