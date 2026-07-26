#!/usr/bin/env python3
"""AI commit message generator — reads staged diff, returns a Conventional Commit."""
import re
import subprocess
import sys

SYSTEM = (
    "You are a git commit message generator. "
    "Output ONLY the commit message — one line, no explanation, no markdown, no quotes, "
    "no co-author lines, no signatures, no AI references. "
    "Follow Conventional Commits: type(scope): subject. "
    "Types: feat, fix, docs, style, refactor, test, chore. "
    "Subject: imperative, lowercase, max 72 chars."
)

# Bare substrings ("llm", "claude", "anthropic") over-matched: any commit
# genuinely about this project's own AI-calling code (e.g. "retry llm calls
# on 429") got erased entirely. These patterns target actual attribution
# signatures instead — see docs/project_notes/bugs.md 2026-07-22 / 2026-07-26.
_STRIP_PATTERNS = [
    r"co-authored-by\s*:",
    r"generated (with|by)\s+claude",
    r"\bclaude code\b",
    r"\bwritten by (an )?(ai|llm|claude|chatgpt|copilot)\b",
    r"\bai-generated\b",
    r"🤖",
]
_STRIP_RE = re.compile("|".join(_STRIP_PATTERNS), re.IGNORECASE)

diff = subprocess.check_output(["git", "diff", "--staged"], text=True)
if not diff.strip():
    print("Nothing staged. Run `git add` first.")
    raise SystemExit(1)

try:
    raw = subprocess.check_output(
        ["claude", "-p", SYSTEM + "\n\n" + diff],
        text=True,
        timeout=20,
    ).strip()
except subprocess.TimeoutExpired:
    print("claude -p timed out after 20s", file=sys.stderr)
    raise SystemExit(1)

# Safety filter — drop any line that looks like attribution
msg = "\n".join(
    l for l in raw.splitlines()
    if not _STRIP_RE.search(l)
).strip()

print(msg)
