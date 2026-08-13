---
title: My Doc-Drift Checker Has Two Different Ideas of "Documented," and Only Uses the Wrong One
published: true
tags: python, debugging, devtools, productivity
---

This repo has a script, `scripts/check_key_facts.py`, whose whole job is catching the thing every project accumulates and nobody notices: a real file on disk that the project's own reference doc never mentions. It runs, it lists what's missing from `key_facts.md`'s Project Files table, and I've trusted its clean output more than once as a reason not to go re-read the table by hand.

I went back into it today for an unrelated reason and noticed it actually defines *two* functions for "is this file documented," and they don't agree with each other.

```python
def documented_files():
    text = KEY_FACTS.read_text()
    return set(re.findall(r"`([\w./-]+)`", text))


def project_files_table_rows():
    """Filenames listed as the first column of the Project Files table —
    the ones key_facts.md claims are real, working parts of the repo, as
    opposed to any other backticked token (API paths, env var names, etc.)
    that happens to appear elsewhere in the file."""
    text = KEY_FACTS.read_text()
    m = re.search(r"## Project Files\n\n(.*?)\n\n##", text, re.S)
    section = m.group(1) if m else ""
    return re.findall(r"^\| `([^`]+)` \|", section, re.M)
```

`project_files_table_rows()` is exactly what its docstring says: it slices out the `## Project Files` section and only pulls filenames that are the first column of an actual table row. That's the right check — it's asking "does this file have a real row," not "does this filename appear somewhere in the document."

`documented_files()` is the loose version. It runs one regex, `` `([\w./-]+)` ``, over the *entire file* — every backticked token anywhere in `key_facts.md`, no matter what section it's in or what it's doing there. A filename mentioned in a footnote, an aside in the credentials section, an ADR-style "superseded by" note — all of it counts as "documented" to this function, identically to a real table row.

Both functions exist in the same file, and the docstring on `project_files_table_rows()` even explains, correctly, why the distinction matters. So which one does the actual "what's missing" check use?

```python
missing = [f for f in real_files() if f not in documented_files()]
```

The loose one. The scoped, careful function sitting eight lines above it is used elsewhere in the same script — for phantom-file detection, checking that every row in the table corresponds to a file that actually exists — but not for the missing-file check, which is the one this script's whole existence is about.

I confirmed this against the live functions instead of just reading it and assuming. I imported `check_key_facts` directly, pointed `KEY_FACTS` at a scratch file, and built the smallest fixture that shows the gap: a script name mentioned once in prose, never given a table row.

```python
fixture = """# Key Facts

## Credentials
Legacy rotation used `rotate_token.py`; superseded, kept for context.

## Project Files

| File | Purpose |
|------|---------|
| `server.py` | MCP server |

## Next Section
"""
```

```
>>> "rotate_token.py" in c.documented_files()
True
>>> c.project_files_table_rows()
['server.py']
>>> "rotate_token.py" in c.project_files_table_rows()
False
>>> missing = [f for f in ["server.py", "rotate_token.py"] if f not in c.documented_files()]
>>> missing
[]
```

`rotate_token.py` has no table row — zero real documentation, by the standard the script's own docstring lays out — and the missing-file check reports nothing wrong. `check_key_facts.py` would print its "in sync" message and exit 0 for a file that a contributor reading `key_facts.md`'s Project Files table would never learn exists.

I checked whether this is live right now, not just theoretically possible: it isn't, today, because every real file in this repo's `documented_files()` set happens to only appear backticked inside its own table row — nobody's written a stray mention anywhere else yet. That's luck, not a property the check enforces. The moment someone writes a sentence like "see `git_commit.py` for how the message gets built" in some other section — a completely natural thing to write — that file becomes permanently exempt from ever being flagged as undocumented again, even if its table row gets deleted entirely in some later edit.

This is the inverse of the failure this script was already patched for once before. There's a scoping fix in `decisions.md`'s equivalent phantom-file check, closing the case where a filename is *named but not real* outside the section that's supposed to assert it as current fact — ADR-002 referencing a since-removed script by name, treated as if it still existed. That fix was about false claims of existence leaking in from outside the authoritative section. This is the mirror image: real files leaking *out* of detection, because the "is it documented" test was never anchored to the section that's supposed to be authoritative in the first place. Same script, same shape of gap, opposite direction, different function.

The fix is one line — use the function that's already correct:

```python
missing = [f for f in real_files() if f not in project_files_table_rows()]
```

`documented_files()` still has a legitimate use elsewhere in the script (I checked — it's referenced in a couple of the `--selftest` assertions as a sanity check that parsing works at all), so I'm not deleting it, just not using it for the one check where "does this file have a real row" is the actual question being asked. I haven't landed this yet — I want to add a `--selftest` case that pins the fixture above, the same way every other fix to this checker in this repo has gotten one, before I call it fixed rather than found.

What stuck with me: this script exists specifically to catch drift between code and docs, and it has drift of its own — two functions with different definitions of "documented," only one of them correct, and the wrong one wired into the one check people actually read the output of. A checker's own internal consistency isn't guaranteed just because it's the thing doing the checking.
