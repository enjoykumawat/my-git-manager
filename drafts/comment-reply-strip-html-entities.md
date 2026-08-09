---
title: "My Comment-Reply Pipeline Was Feeding Me Garbled HTML Entities Instead of the Actual Comment"
published: true
tags: python, debugging, devtools, mcp
---

I have a small script, `reply_comments.py`, that pulls unanswered comments off my DEV.to articles and drafts replies to a markdown file so I can paste them in by hand. The API doesn't let a normal account post comments (that's its own bug I've written about before), so this draft-then-paste loop is the whole workflow. Every reply I've ever sent has come from reading the `body` field this script prints.

Today I went looking for a bug distinct from everything already logged for this repo, and I ended up re-reading `strip_html()`, the function that turns a comment's raw `body_html` into the plain text I actually read:

```python
def strip_html(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()
```

It does exactly one thing: strip HTML tags with a regex, then collapse whitespace. It's been in the file since the script was written and nobody had audited it on its own — every prior pass through this pipeline was about pagination, thread-depth walking, or dedup keys, never the text-extraction step itself.

Here's the problem. DEV.to's API returns `body_html` as *rendered* HTML. A correct renderer has to HTML-entity-escape a commenter's own literal `<`, `>`, `&`, and quote characters, or they'd get mistaken for markup. So a comment that reads, in plain English:

> isn't it faster with a Q&A cache? Try List<String> instead.

comes back from the API as something like:

```html
<p>isn&#39;t it faster with a Q&amp;A cache? Try List&lt;String&gt; instead.</p>
```

`strip_html()`'s regex only ever targets `<[^>]+>` — actual tags. It has no idea what to do with `&#39;`, `&amp;`, `&lt;`, `&gt;`. Those aren't tags, so the regex leaves them untouched. The whitespace collapse doesn't touch them either. What comes out the other end, into the exact field I read to draft a reply, is:

```
isn&#39;t it faster with a Q&amp;A cache? Try List&lt;String&gt; instead.
```

That's not a cosmetic nit. On a dev-focused comment section, `&`, `<`, and `>` show up constantly — generics, comparisons, "foo & bar," code snippets pasted into a comment. Every one of those got mangled on the way into my drafting queue, and I never noticed because garbled-but-readable text doesn't throw an exception. It just reads a little off, and I'd been mentally auto-correcting it without registering that the script was wrong.

I confirmed it with a quick stub before touching anything:

```python
>>> strip_html("<p>List&lt;String&gt; and Q&amp;A, isn&#39;t it?</p>")
"List&lt;String&gt; and Q&amp;A, isn&#39;t it?"
```

Still escaped. The fix is one import and one function call — Python's stdlib already has the unescaper:

```python
import html

def strip_html(h):
    """Plain text of a dev.to comment's body_html, for drafting replies.

    dev.to's rendered HTML entity-escapes a commenter's own literal <, >, &,
    and quote characters right alongside the actual tags it wraps the
    comment in. Stripping tags alone leaves those entities untouched, so a
    comment quoting code with generics (List<String>) or using "&" came back
    as literal "&lt;"/"&amp;" text in the exact field a reply gets drafted
    from.
    """
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
```

Order matters here: strip tags first, *then* unescape entities. If you unescape first, a comment that legitimately contains the literal text `&lt;script&gt;` (someone quoting HTML in a comment, which happens a lot on a dev blog) would decode into something that looks like a real tag and get eaten by the tag-stripping regex on the next pass. Doing it in this order means only entities describing the commenter's *real* characters get decoded, after anything that was actually markup is already gone.

Rerunning the same stub after the fix:

```python
>>> strip_html("<p>List&lt;String&gt; and Q&amp;A, isn&#39;t it?</p>")
"List<String> and Q&A, isn't it?"
```

That's the comment as it was actually written.

I didn't stop at the standalone function, though — this repo has a documented pattern of a fix looking right on a helper in isolation and then not actually reaching the caller. So I round-tripped it through `_pending_entry()`, the function that builds the dict `pending()` actually prints:

```python
entry = _pending_entry(
    msg("x", "2026-07-24T08:00:00Z", id_code="ent1", body="A&amp;B &lt;ok&gt;"),
    drafted_codes=set(),
)
assert entry["body"] == "A&B <ok>", entry
```

That passes now too, which is the part that actually matters — the fix has to hold all the way to the field a human reads, not just at the function that happens to contain the bug.

I also added both of those as permanent `--selftest` cases instead of just eyeballing the fix once and moving on. This repo has burned itself before on exactly that: a fix verified by hand at the time, never turned into a regression test, quietly uncovered again months later. `reply_comments.py --selftest` now exercises this directly, so if some future change to `strip_html()` reintroduces the gap, it fails loud instead of just reading slightly wrong forever.

The bigger lesson for me wasn't really about HTML entities specifically. It's that "the obvious implementation" of a text-transformation function — strip tags, done — can be wrong in a way that never crashes, never shows up in a stack trace, and never trips an exception handler. It just quietly degrades the one thing a human downstream is relying on to be accurate. Those bugs don't get caught by better error handling. They get caught by actually reading the function's real output against real input, which is a much easier check to skip than it should be.
