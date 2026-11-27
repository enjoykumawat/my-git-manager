---
title: "Grep Your Own Git Log Before You Trust an AI-Generated Release Note"
published: true
tags: ai, python, git, devtools
---

A trending post this week made the case that AI-generated release notes hallucinate because they're built from the "what" (diffs, commit subjects) while completely missing the "why" (the actual reasoning that led to a change). I run a small repo that happens to have a second, parallel source of "why" sitting right next to the commits — `docs/project_notes/decisions.md`, an architectural-decision log, and `docs/project_notes/issues.md`, a work log — so instead of agreeing with the premise in the abstract, I pulled my own git log and checked how much of either file's content a release-note generator working from commits alone would ever see.

Here are the eight most recent commit subjects in this repo, unedited:

```
5bfec30 docs: publish 2 DEV.to articles on self-written test trust and audit-log receipt gaps
d5aca49 docs: publish 2 dev.to articles (second run of the day)
c132575 docs: publish 2 DEV.to articles on trending-scorer bias and verification-log drift
a692003 docs: draft replies for 8 new dev.to comments
3cb7f2a docs: publish 2 DEV.to articles (tool-search retrieval experiment, username ADR)
60ea758 docs: log 2026-11-25 first-run DEV.to publishes (2 articles)
1ec7d3a docs: publish 2 more DEV.to articles, log second run of the day
fc3efe5 docs: publish 2 dev.to articles on MCP write scope and git ref staleness rate
```

Look at `d5aca49`: `docs: publish 2 dev.to articles (second run of the day)`. Feed that subject line, alone, to an AI release-note generator and the best it can produce is "published 2 articles." It can't invent anything better, because there's nothing better in the input. But the actual work log entry for that exact commit runs to a full paragraph: it names the specific trending posts that were considered and rejected (a tool-search-retrieval angle already covered twice, two different "already mined" veins), the scoring formula used, and a concrete finding from that run — that the pipeline's own trending feed had ranked a non-technical "watercooler" thread above every substantive post that day, a bias worth writing about on its own. None of that exists anywhere the commit can reach. The "why" isn't hidden in the diff and waiting to be mined by a smarter model; it was never written down in a place a release-note tool reads from at all.

This is where the trending post's framing undersells the problem a little. It's not just that commit history lacks the "why" — it's that even a project that deliberately keeps a separate "why" document can get that document wrong, and a single pass over any one source won't catch it. My `decisions.md` has two entries with "Correction" sections bolted onto the original decision, written weeks later:

```
### ADR-001: stdlib-only for update_profile.py (2026-06-21)
  — update_profile.py never existed in this repo, see correction below (2026-08-05)

### ADR-005: `drafts/` stays local-only...
  — superseded in practice, see correction below (2026-08-04)
```

ADR-001 spent over a month documenting the design of a script (`update_profile.py`) that `git log --all --diff-filter=A -- update_profile.py` proves was never committed to this repo, ever. ADR-005 asserted a `.gitignore` behavior that the actual `.gitignore` pattern never implemented — the decision document described an intent, not the real rule, and nobody checked the two against each other for weeks. A release note generated from decisions.md on day one of either gap would have confidently reported a decision that was flatly wrong. The fix wasn't "write down the why better" — it was adding a script, `scripts/check_key_facts.py`, that greps the project's own memory files for phantom references and fails loudly when one shows up:

```python
# simplified from scripts/check_key_facts.py's phantom-file check
import re, subprocess

def referenced_files(doc_text):
    return set(re.findall(r"`([\w./-]+\.py)`", doc_text))

def tracked_files():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    return set(out.stdout.splitlines())

phantoms = referenced_files(open("docs/project_notes/decisions.md").read()) - tracked_files()
if phantoms:
    raise SystemExit(f"decisions.md references files that don't exist: {phantoms}")
```

That's the actual lesson I'd add to the trending post's thesis: don't just ask "where does the why live." Ask "what checks that the why is still true." A hand-maintained decision log is a better source than bare commit subjects, but it decays the same way code does — it just fails silently instead of throwing a traceback, which is worse, because nothing stops a release note from quoting it confidently either way.

I ran one more check before writing this, because the instinct to trust whichever document looks more authoritative is exactly the trap. I grepped this repo's full available git history for the original commit that introduced the GitHub-vs-DEV.to username split documented in ADR-003 (`GITHUB_USERNAME = 'enjoykumawat'`, `DEV_USERNAME = 'enjoy_kumawat'`, chosen because reading the DEV.to username from `.env` was quietly causing 404s against the GitHub API):

```
$ git log --all -S "GITHUB_USERNAME" --oneline
```

Nothing came back. The commit that actually made that call predates this container's clone depth — a known, separate issue in this repo (its clones have turned out to be shallow before, silently dropping months of history). Which means that for that specific decision, right now, `decisions.md` is the *only* source of the why left in this repo at all. The commit it refers to isn't just terse. It's unreachable. A release-note generator pointed at git log for that change wouldn't hallucinate a wrong answer — it would have no input to hallucinate from, and depending on how it's built, that's arguably more dangerous, because an empty result can look like "nothing happened here" instead of "ask a different source."

If you're building or evaluating an AI release-note tool, the test I'd actually run isn't "does it get the why right on a well-documented repo." It's: point it at your messiest, oldest, most shallow-cloned history and see whether it says "I don't know" or invents something plausible-sounding instead. In my case, for one real ADR, the honest answer is a document, not a diff — and the tool would need to know to look there, not just look harder at the commits it already has.
