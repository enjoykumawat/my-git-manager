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


def main():
    missing = [f for f in real_files() if f not in documented_files()]
    if missing:
        print("key_facts.md's Project Files table is missing:")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)
    print("key_facts.md is in sync with repo scripts.")


if __name__ == "__main__":
    main()
