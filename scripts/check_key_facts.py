#!/usr/bin/env python3
"""Flag repo scripts not mentioned in key_facts.md's Project Files table.

Usage: python3 scripts/check_key_facts.py
Exits 1 (and lists what's missing) if any tracked script isn't referenced
anywhere in key_facts.md. Exits 0 if the table is in sync.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY_FACTS = ROOT / "docs" / "project_notes" / "key_facts.md"
DECISIONS = ROOT / "docs" / "project_notes" / "decisions.md"
# issues.md is deliberately excluded: it's an append-only historical log
# (ADR-005), so a past entry naming a since-removed file is a legitimate
# record, not stale-and-currently-asserted fact. decisions.md is not
# append-only in that sense — an ADR's prose is presented as still true.
DECISIONS_SEARCH_DIRS = (ROOT, ROOT / "docs" / "project_notes", ROOT / "drafts",
                          ROOT / "scripts", ROOT / "hooks")
# Named only inside ADR-001's 2026-08-05 correction, to explain that they were
# never real — not asserted as current fact, so not phantom-in-the-flagged sense.
# Same shape as key_facts.md's .env exception below.
#
# This exemption is scoped to ADR-001's own section text (see
# _adr001_section_text()/decisions_phantom_files() below), not the whole
# file. A blanket by-name exemption would silently excuse a *new* mention
# of the same phantom filename anywhere else in decisions.md too — which is
# exactly what happened: ADR-002 asserted "(same pattern as
# update_profile.py)" as if the script were real, and the blanket version
# of this exemption hid that from every run of this checker until it was
# caught by hand and fixed 2026-08-12 (bugs.md same date). Scoping the
# exemption to where the name is actually being explained as historical —
# not just mentioned — closes that gap for any future ADR that reuses one
# of these names the same way.
DECISIONS_KNOWN_HISTORICAL = {"update_profile.py", "template.md"}
# hooks/ files are git hooks — named by git, conventionally no extension —
# so they're tracked unconditionally instead of by suffix like scripts/ and root.
TRACKED = [(ROOT, (".py", ".sh")), (ROOT / "scripts", (".py", ".sh")), (ROOT / "hooks", None)]


def real_files():
    found = []
    for d, exts in TRACKED:
        if not d.exists():
            continue
        for p in d.iterdir():
            if p.is_file() and (exts is None or p.suffix in exts):
                found.append(p.relative_to(ROOT).as_posix())
    return sorted(found)


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


def decisions_referenced_files(text=None):
    """Filename-shaped tokens in decisions.md's prose. Unlike key_facts.md's
    Project Files table, decisions.md doesn't consistently backtick
    filenames (e.g. ADR-001's title, "same pattern as update_profile.py"),
    so this scans raw text for a name.ext shape instead of parsing backticks."""
    if text is None:
        text = DECISIONS.read_text()
    return sorted(set(re.findall(r"\b[\w-]+\.(?:py|sh|md)\b", text)))


def _adr001_section_text(text):
    """The slice of decisions.md's text spanning ADR-001 alone (its heading
    up to, but not including, the next '### ADR-' heading, or EOF). The
    only place `update_profile.py`/`template.md` are legitimately named —
    to explain, in the 2026-08-05 correction, that they never existed.
    A mention of either name anywhere OUTSIDE this slice is a fresh claim,
    not a repeat of the already-vetted historical explanation."""
    m = re.search(r"### ADR-001:.*?(?=\n### ADR-|\Z)", text, re.S)
    return m.group(0) if m else ""


def decisions_phantom_files(text=None):
    if text is None:
        text = DECISIONS.read_text()
    adr001_text = _adr001_section_text(text)
    # Only the first occurrence is stripped out deliberately: if ADR-001's
    # own heading/text were ever duplicated elsewhere that's a separate
    # problem this check isn't trying to catch.
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


if "--selftest" in sys.argv:
    # Regression case for bugs.md 2026-08-12: DECISIONS_KNOWN_HISTORICAL
    # used to be a blanket by-name exemption, so ADR-002 asserting "(same
    # pattern as update_profile.py)" — a fresh, uncorrected phantom claim —
    # was silently excused just because ADR-001 elsewhere explains the same
    # filename never existed. The exemption is now scoped to ADR-001's own
    # section text; these fixtures exercise both sides of that scoping.
    _ADR001_ONLY = """### ADR-001: stdlib-only for update_profile.py (2026-06-21)

**Correction:** `update_profile.py` and `template.md` were never committed
to this repo. See ADR-002.

### ADR-002: FastMCP for MCP server (2026-06-21)

**Decision:** Use FastMCP. HTTP calls via stdlib urllib.
"""
    _ADR002_REPEATS_IT = """### ADR-001: stdlib-only for update_profile.py (2026-06-21)

**Correction:** `update_profile.py` and `template.md` were never committed
to this repo. See ADR-002.

### ADR-002: FastMCP for MCP server (2026-06-21)

**Decision:** Use FastMCP. HTTP calls via stdlib urllib (same pattern as
update_profile.py).
"""
    _NO_ADR001_AT_ALL = """### ADR-002: FastMCP for MCP server (2026-06-21)

**Decision:** Use FastMCP. HTTP calls via stdlib urllib (same pattern as
update_profile.py).
"""
    _REAL_FILE_MENTIONED_TWICE = """### ADR-001: stdlib-only for update_profile.py (2026-06-21)

References server.py once.

### ADR-002: uses server.py again, a real file, from any section.
"""

    # 1. Named only within ADR-001's own correction -> exempted, not phantom.
    assert decisions_phantom_files(_ADR001_ONLY) == []
    # 2. Same name repeated in ADR-002, outside ADR-001's section -> the
    #    2026-08-12 bug: must now be flagged, not silently excused.
    assert decisions_phantom_files(_ADR002_REPEATS_IT) == ["update_profile.py"]
    # 3. No ADR-001 section at all (nothing to scope the exemption to) ->
    #    still flagged, exemption never applies without ADR-001 present.
    assert decisions_phantom_files(_NO_ADR001_AT_ALL) == ["update_profile.py"]
    # 4. A real, existing file mentioned in multiple sections is never
    #    flagged regardless of DECISIONS_KNOWN_HISTORICAL scoping.
    assert decisions_phantom_files(_REAL_FILE_MENTIONED_TWICE) == []
    # 5. project_files_table_rows()/documented_files() still work against
    #    the real key_facts.md (pre-existing behavior, unchanged by this fix).
    assert "server.py" in project_files_table_rows()
    assert "server.py" in documented_files()
    print("selftest ok")
    raise SystemExit(0)


def main():
    ok = True
    missing = [f for f in real_files() if f not in documented_files()]
    if missing:
        ok = False
        print("key_facts.md's Project Files table is missing:")
        for f in missing:
            print(f"  - {f}")
    # .env is documented as intentionally never committed (key_facts.md says
    # so in its own row) — its absence on disk is by design, not drift.
    phantom = [f for f in project_files_table_rows() if f != ".env" and not (ROOT / f).exists()]
    if phantom:
        ok = False
        print("key_facts.md's Project Files table documents files that don't exist on disk:")
        for f in phantom:
            print(f"  - {f}")
    decisions_missing = decisions_phantom_files()
    if decisions_missing:
        ok = False
        print("decisions.md references files that don't exist anywhere in the repo:")
        for f in decisions_missing:
            print(f"  - {f}")
    if ok:
        print("key_facts.md is in sync with repo scripts.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
