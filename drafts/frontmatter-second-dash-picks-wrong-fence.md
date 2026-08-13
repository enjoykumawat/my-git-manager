---
title: My Frontmatter Parser Checks for Too Few Delimiters. It Never Checked for Too Many.
published: true
tags: python, debugging, devtools, ai
---

I fixed this script's frontmatter parser a week ago. A draft with an unclosed `---` block used to blow up with a bare `ValueError: not enough values to unpack`, and I patched it to raise a clean, actionable error instead. I wrote that fix up, verified it with a stubbed repro, added a `--selftest` case for it, called it done.

Then I went back to write today's articles and actually looked at the line I "fixed" instead of the error path around it.

```python
def parse(text):
    meta = {}
    body = text
    if text.lstrip().startswith("---"):
        parts = text.lstrip().split("---", 2)
        if len(parts) < 3:
            raise ValueError(
                "frontmatter opened with '---' but never closed with a second '---' delimiter"
            )
        _, fm, body = parts
        ...
```

`split("---", 2)` doesn't split on lines that are `---`. It splits on the *literal substring* `"---"`, anywhere in the text, and stops after the second one it finds. My fix only handles the case where it finds fewer than two — an unclosed fence. It says nothing about what happens when the second `"---"` it finds isn't the closing fence at all, because a third one showed up first, buried inside a frontmatter value.

That's not a hypothetical. I write these article titles myself, and "before/after" is a phrase I reach for constantly:

```
---
title: My Before---After Refactor
tags: ai, python, refactor
published: true
---
real body starts here
```

`split("---", 2)` finds the em-dash-style `---` inside the title *before* it finds the real closing fence on its own line. So the split points land in the wrong place entirely:

```python
>>> from publish_devto import parse
>>> meta, body = parse(text)
>>> meta
{'title': 'My Before'}
>>> body
'After Refactor\ntags: ai, python, refactor\npublished: true\n---\nreal body starts here\n'
```

The title got truncated to `"My Before"`. `tags` and `published` never got parsed as frontmatter fields at all — they're sitting in the body now, as literal text, along with the real closing fence and a stray leftover `---`. If I ran this through `publish_devto.py` as-is, that garbage would go live as the opening lines of the article.

The part that makes this worse than a crash: it doesn't crash. `len(parts)` is still exactly 3 — one before the first `---`, one between the first and second, one after. My guard clause (`if len(parts) < 3`) never fires, because three parts is exactly what a *correctly* closed frontmatter block also produces. The check I added last week can't tell "found the closing fence" from "found some other dashes first and happened to land on three pieces anyway." Same shape, different meaning, no way to distinguish them from the count alone.

And it compounds through the rest of `main()`. `meta.get("published", "false")` defaults to `"false"` when `published` isn't a recognized key — which, here, it isn't, because it never got parsed out of `fm` at all; it's just a line of unparsed text sitting in the corrupted `body`. So an article I explicitly marked `published: true` in the draft would get POSTed as a **draft** instead, silently, with zero errors anywhere in the pipeline. The duplicate-publish guard, `already_published()`, is gated on `published` being true — so it never even runs. I'd have no idea any of this happened until I went to verify the live URL and found nothing there, or found a draft with three lines of raw YAML-looking text sitting above the real content.

The reason last week's fix didn't catch this is the same reason most fixes don't catch their sibling bugs: I was staring at the failure I'd just seen (`ValueError: not enough values to unpack`, a crash, a stack trace pointing right at the line) and I fixed exactly that shape of input. A too-few-delimiters draft. I never asked what a too-*many*-delimiters draft does, because nothing had shown me one yet. The fix closed the loud failure and left the quiet one completely untouched, sitting one line above it in the same function.

The actual bug is that `split("---", 2)` is the wrong primitive for this job. It doesn't know what a "fence" is — it just counts substring occurrences. What I want is: find lines that are *exactly* `---` on their own, and treat the first two of those as the frontmatter boundary, ignoring any `---` that shows up mid-line as part of a value. That's a `splitlines()` and an index scan, not a `str.split` call:

```python
def parse(text):
    lines = text.lstrip().splitlines()
    if lines and lines[0].strip() == "---":
        try:
            close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
        except StopIteration:
            raise ValueError(
                "frontmatter opened with '---' but never closed with a second '---' delimiter"
            )
        fm = "\n".join(lines[1:close])
        body = "\n".join(lines[close + 1:]).lstrip("\n")
        meta = {}
        for line in fm.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
    else:
        meta, body = {}, text
    ...
```

This treats `---` as a line-level delimiter, the way the format actually intends it, instead of a substring search over the whole blob. A `before---after` title inside the frontmatter block no longer looks like a fence, because it isn't one — it's not alone on its line.

I haven't shipped this fix yet. I want a `--selftest` case for it first, the same discipline the too-few-delimiters fix got, and I want to check whether any of the ~130 drafts already sitting in this repo's `drafts/` folder happen to contain a mid-value `---` that's been silently mis-parsed this whole time without me noticing. Given how often "before/after," "step-by-step," and plain old typed-out em dashes show up in article titles about before/after code changes, I'd be surprised if this is the first time it's fired — I'm just the first time I've gone looking for it as its own bug instead of as a variant of the one I already fixed.

The lesson that actually generalizes: when you fix a parser's crash on malformed input, check what it does on input that's malformed in the *opposite* direction — not just less of the delimiter you expected, but more of it, showing up somewhere you didn't expect to have to guard against. A guard clause that only checks `len(parts) < N` is silent about every other value `len(parts)` could take that still happens to equal what you wanted.
