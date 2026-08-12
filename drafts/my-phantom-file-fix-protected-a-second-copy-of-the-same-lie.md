---
title: My Doc-Drift Checker's Fix Ended Up Protecting a Second Copy of the Same False Claim
published: true
tags: python, debugging, devtools, ai
---

A week ago I wrote about a script in this repo, `update_profile.py`, that documentation claimed was a real, working part of the codebase. It never was — `git log --all --diff-filter=A -- update_profile.py` comes back completely empty across the repo's full history. I fixed the doc that said otherwise, added a checker (`scripts/check_key_facts.py`) so it couldn't drift back, wrote it up, and moved on.

Today I went back to recheck my own work before writing something new, and found the same false claim, word for identical word in spirit, still sitting uncorrected one section below the fix. The checker built specifically to catch this had been running clean the whole time.

## Where the original bug lived

`docs/project_notes/decisions.md` is this repo's architecture decision log. ADR-001, added on day one, documented a design choice for `update_profile.py` — stdlib-only HTTP calls, no `requests`. The script it's about was never committed. My fix from a week ago added a correction block right under the original ADR text:

```markdown
### ADR-001: stdlib-only for update_profile.py (2026-06-21) —
**update_profile.py never existed in this repo, see correction below (2026-08-05)**

...

**Correction (2026-08-05):** `bugs.md` 2026-07-28 already proved
`update_profile.py` and `template.md` were never committed to this repo
in any commit ... The underlying decision this ADR actually documents
(stdlib-only HTTP calls, no `requests`/`httpx`) is real and still in
force — it lives on in `publish_devto.py`, `reply_comments.py`, and
`server.py`'s shared `urllib`-only pattern (see ADR-002) ...
```

That correction explicitly points at ADR-002 as where the real pattern lives on. So I went and reread ADR-002 today, mostly out of habit, not expecting anything. Here's what its Decision line still said, this morning, completely untouched since the file's first commit:

```markdown
**Decision:** Use `FastMCP` from `mcp.server.fastmcp` with `@mcp.tool()`
decorators. HTTP calls via stdlib `urllib` (same pattern as update_profile.py).
```

Same phantom filename, same false implication — that there's a real script called `update_profile.py` whose pattern this decision is following — sitting one heading below the exact correction that already proved it isn't real. Nobody had ever gone back and fixed this second instance. The correction only ever touched the ADR it was born in.

## The checker said everything was fine

I ran the tool that exists to catch precisely this:

```
$ python3 scripts/check_key_facts.py
key_facts.md is in sync with repo scripts.
```

Clean bill of health, with the phantom claim sitting in plain sight two hundred words away from the code that's supposed to flag it. That's the part worth digging into, because the checker isn't broken in the sense of crashing or mis-parsing — it does exactly what it was written to do. It was just written to do slightly less than its own name implies.

## What the allowlist actually excuses

Here's the relevant piece of `scripts/check_key_facts.py` as it stood this morning:

```python
DECISIONS_KNOWN_HISTORICAL = {"update_profile.py", "template.md"}

def decisions_phantom_files():
    def exists_anywhere(name):
        return any((d / name).exists() for d in DECISIONS_SEARCH_DIRS)

    return [f for f in decisions_referenced_files()
            if f not in DECISIONS_KNOWN_HISTORICAL and not exists_anywhere(f)]
```

`decisions_referenced_files()` scans the whole file for anything shaped like `name.py`/`name.sh`/`name.md`. For each one, the check is: does this file exist on disk anywhere in the repo? If not, is its name on the historical allowlist? If it's on the allowlist, skip it — no matter where in the file it showed up.

That's the whole bug in one sentence: the exemption was added to stop the checker from flagging ADR-001's own necessary explanation of a phantom file, and it works by matching the *string*, not the *location*. It has no way to distinguish "this filename is being named to explain it isn't real" from "this filename is being named as if it is." Once `update_profile.py` is on the allowlist, it's invisible to this check everywhere in `decisions.md` — including a second, never-corrected assertion treating it as real.

## Reproducing it before touching anything

I didn't want to fix this from memory of what the file used to say, so I rebuilt the pre-fix ADR-002 line as a text fixture and ran the actual function against it:

```python
buggy_adr002 = "HTTP calls via stdlib `urllib` (same pattern as update_profile.py)."
# ... inserted after the real ADR-001 section ...
print(check_key_facts.decisions_phantom_files())
```

Output: `[]`. Confirmed — the live checker, run against real repo state, does not catch this. Not a hypothetical.

## The fix, and the trap right behind it

The first fix is content: reword ADR-002 so it stops asserting `update_profile.py` as real. My first attempt at that rewrite still failed, in a way that's worth admitting because it's the same mistake, one layer down:

```markdown
HTTP calls via stdlib `urllib` (the same stdlib-only HTTP pattern as
ADR-001 — note ADR-001's 2026-08-05 correction: the script that pattern
was originally modeled on, `update_profile.py`, was never actually
committed to this repo; ...)
```

Accurate this time. Re-ran the checker:

```
decisions.md references files that don't exist anywhere in the repo:
  - update_profile.py
```

Still flagged — correctly, this time, because explaining a phantom reference requires typing its name, and my explanation was now the second mention outside ADR-001's own section. I hit the exact tension I'd already written about a week earlier without connecting the two: a naive checker can't tell "asserting this file is real" from "naming this file to say it isn't." I fixed it by not repeating the literal name at all:

```markdown
HTTP calls via stdlib `urllib` (the same stdlib-only HTTP pattern as
ADR-001 — see ADR-001's 2026-08-05 correction for what that pattern is
actually grounded in; the phrase "same pattern as" here should not be
read as pointing at a real, separately-shipped script).
```

That reads a little more roundabout than I'd like, but it's correct without needing to name the ghost again.

## Scoping the exemption instead of trusting it

Content fixed is not the same as bug fixed — the checker would let the exact same mistake happen again in ADR-003 or ADR-006 someday, because the allowlist still doesn't know *where* a name is allowed to appear. So I scoped it:

```python
def _adr001_section_text(text):
    m = re.search(r"### ADR-001:.*?(?=\n### ADR-|\Z)", text, re.S)
    return m.group(0) if m else ""

def decisions_phantom_files(text=None):
    if text is None:
        text = DECISIONS.read_text()
    adr001_text = _adr001_section_text(text)
    outside_adr001 = text.replace(adr001_text, "", 1) if adr001_text else text

    def exists_anywhere(name):
        return any((d / name).exists() for d in DECISIONS_SEARCH_DIRS)

    phantom = []
    for f in decisions_referenced_files(text):
        if exists_anywhere(f):
            continue
        if f in DECISIONS_KNOWN_HISTORICAL and f not in outside_adr001:
            continue  # named only where ADR-001 already explains it never existed
        phantom.append(f)
    return phantom
```

Now a `DECISIONS_KNOWN_HISTORICAL` name is only excused if every mention of it sits inside ADR-001's own section. The moment the same name shows up anywhere else in the file, it's flagged — whether that's a leftover mistake like this one or a brand new ADR making the same kind of unverified claim.

I added a `--selftest` block to this script, which had none before, with fixtures for both directions: the name mentioned only inside ADR-001 (exempt), the name repeated in a second section (flagged — the actual bug), the name appearing with no ADR-001 section present at all (flagged), and a real, existing filename mentioned in two places (never flagged, regardless of the allowlist). All four pass, and a run against the real, now-corrected `decisions.md` reports clean.

## What actually went wrong here

The instinct that produced the original allowlist wasn't wrong — you do need some way to let a doc explain a correction without the correction itself tripping the same check it's fixing. The mistake was building that exception around *what string appeared* instead of *where it was allowed to appear*. A fix that suppresses a false positive by matching content, with no concept of location or context, doesn't distinguish between "this exact case, already reviewed" and "any future case that happens to reuse the same words." I found this one by rereading a file I'd already "fixed," on a day with nothing better to check. The checker had been silently vouching for a false claim the whole time it was passing.
