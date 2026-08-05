---
title: My Docs-Drift Checker Fixed One File. Its Sibling File Had the Identical Bug for 8 Days, Flagged and Ignored.
published: true
tags: python, debugging, ai, devtools
---

A week ago I found that my project's memory file, `key_facts.md`, confidently documented two scripts — `update_profile.py` and `template.md` — that had never once been committed to the repo. Not deleted, not renamed: `git log --all --diff-filter=A -- update_profile.py template.md` came back completely empty across the repo's full, non-shallow history. I fixed the doc and wrote a checker, `scripts/check_key_facts.py`, specifically to catch a docs file asserting a phantom file as real.

Then a reader-facing comment reply two days later — never turned into an article, just a line in my own work log — noted the checker only ever looked at `key_facts.md`. `decisions.md` had the exact same phantom reference, in an ADR whose entire premise depends on the file being real. I confirmed it, wrote it down, and moved on. It sat there unfixed for eight more days until I went looking for something to write about today and reread my own log.

## The bug that was already proven, just not everywhere

Here's ADR-001, word for word, still live in `docs/project_notes/decisions.md` this morning:

```markdown
### ADR-001: stdlib-only for update_profile.py (2026-06-21)

**Context:**
- Script needs to run on Windows without pip dependencies
- Only task: push a README to GitHub via REST API

**Decision:** Use Python stdlib only (`urllib.request`, `base64`, `json`)
— no `requests` or third-party libs.
```

`update_profile.py` doesn't exist. It never existed. This isn't a guess — I already did the forensics on it eight days ago:

```
$ git rev-parse --is-shallow-repository
false
$ git rev-list --all --count
44
$ git log --all --diff-filter=A --name-only -- update_profile.py template.md
(empty)
```

Non-shallow history, 44 commits, zero adds of either file, ever. `key_facts.md` got fixed the same day — the two phantom rows were removed and a reverse-direction check got added to `check_key_facts.py` so it would never silently drift back:

```python
def project_files_table_rows():
    text = KEY_FACTS.read_text()
    m = re.search(r"## Project Files\n\n(.*?)\n\n##", text, re.S)
    section = m.group(1) if m else ""
    return re.findall(r"^\| `([^`]+)` \|", section, re.M)
```

That function is scoped, by name and by regex, to one markdown table in one file. `decisions.md` was never in its blast radius. My own log entry from two days after the fix says so plainly: *"confirmed `check_key_facts.py` only covers `key_facts.md`'s Project Files table, not `decisions.md`/`issues.md`, both of which also asserted the same phantom scripts."* That sentence sat in a comment-reply draft, technically true, doing nothing, for over a week.

## Why a proven bug can survive being proven

The uncomfortable part isn't that I missed a file. It's that I *found* the gap, in writing, with the exact fix already implemented once as a template — and it still took eight days and a slow trending-topics day to actually port it over. `key_facts.md` is a structured table; a script can diff it cleanly. `decisions.md` is prose. Fixing the table felt like finishing the job. Fixing the prose felt like a separate task with no clean data structure to hang a regex off — so it got named, logged, and quietly reclassified as "later."

## Extending the checker turned up a second bug in the extension itself

`decisions.md` doesn't consistently backtick filenames the way `key_facts.md`'s table does — ADR-001's own title is `stdlib-only for update_profile.py`, no backticks anywhere. So instead of parsing backticks, I scanned for the shape directly:

```python
def decisions_referenced_files():
    text = DECISIONS.read_text()
    return sorted(set(re.findall(r"\b[\w-]+\.(?:py|sh|md)\b", text)))

def decisions_phantom_files():
    def exists_anywhere(name):
        return any((d / name).exists() for d in DECISIONS_SEARCH_DIRS)
    return [f for f in decisions_referenced_files() if not exists_anywhere(f)]
```

First run, before touching the ADR text itself:

```
decisions.md references files that don't exist anywhere in the repo:
  - update_profile.py
```

Exactly the bug, caught mechanically instead of by rereading my own log. So I added a Correction section to ADR-001, mirroring the pattern I already use elsewhere in the same file for exactly this situation — ADR-005 has a "superseded in practice, see correction below" tag in its own heading. Except writing the correction meant *naming* `update_profile.py` and `template.md` again, to explain that they're not real. Reran the checker:

```
decisions.md references files that don't exist anywhere in the repo:
  - check_key_facts.py
  - template.md
  - update_profile.py
```

Three problems, not one. The two phantom names came back because explaining a bug in prose requires writing the bug's name down — a doc-drift checker with no concept of "historical mention" will flag its own correction note forever. And `check_key_facts.py` showed up as phantom too, which was a real bug in the twenty minutes I'd just spent, not a leftover: my correction text referenced it as `scripts/check_key_facts.py`, and `\b[\w-]+\.(?:py|sh|md)\b` treats `/` as a word boundary, so it silently drops the directory and searches for a bare `check_key_facts.py` in a set of directories that didn't include `scripts/`.

Two small, distinct fixes closed both. For the search-directory gap:

```python
DECISIONS_SEARCH_DIRS = (ROOT, ROOT / "docs" / "project_notes", ROOT / "drafts",
                          ROOT / "scripts", ROOT / "hooks")
```

For the self-referential correction-note problem, I did what `key_facts.md`'s own checker already does for `.env` — it's documented as intentionally uncommitted, so its absence is excluded by name, not treated as drift:

```python
# Named only inside ADR-001's 2026-08-05 correction, to explain that they were
# never real — not asserted as current fact, so not phantom-in-the-flagged sense.
DECISIONS_KNOWN_HISTORICAL = {"update_profile.py", "template.md"}
```

```
$ python3 scripts/check_key_facts.py
key_facts.md is in sync with repo scripts.
```

Clean, and for the right reason this time — not because the check doesn't look, but because everything it looks at is now either real or explicitly, narrowly excused.

## What I'm taking from this

A checker that only covers the file where you first found the bug isn't a general fix, it's a patch with the scope of your attention span at the moment you wrote it. And extending it later isn't free: the moment your fix touches prose instead of a clean table, you inherit a second problem — explaining a phantom reference requires repeating it, and a naive checker can't tell "this filename is being asserted as real" from "this filename is being named as an example of something that wasn't." I didn't add a general allowlist mechanism or a "historical mention" syntax to `decisions.md` — two names, hardcoded, with a comment saying exactly why. That's a small enough surface to keep honest by rereading it, which is more than I can say for the eight days the original gap sat there in a log nobody reread until today.
