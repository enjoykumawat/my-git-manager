#!/usr/bin/env python3
"""AI commit message generator — reads staged diff, returns a Conventional Commit."""
import subprocess

SYSTEM = (
    "You are a git commit message generator. "
    "Output ONLY the commit message — no explanation, no markdown, no quotes. "
    "Follow Conventional Commits: type(scope): subject. "
    "Types: feat, fix, docs, style, refactor, test, chore. "
    "Subject: imperative, lowercase, max 72 chars."
)

diff = subprocess.check_output(["git", "diff", "--staged"], text=True)
if not diff.strip():
    print("Nothing staged. Run `git add` first.")
    raise SystemExit(1)

msg = subprocess.check_output(
    ["claude", "-p", SYSTEM + "\n\n" + diff],
    text=True,
).strip()
print(msg)
