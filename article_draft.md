# I Fixed the "AI Commit Messages" Problem in 20 Lines of Python

You've probably seen that trending post — *"I Asked AI to Write My Commit Messages and It Was Embarrassing."*

Same. But instead of accepting embarrassing output, I fixed it.

Here's the thing: the problem isn't AI writing commit messages. The problem is *how* you ask it. One clear system prompt + the actual diff = surprisingly good results.

## The Setup

No new packages. No API key. If you have [Claude Code](https://claude.ai/code), you're already set.

```python
#!/usr/bin/env python3
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
```

That's it. 20 lines. Uses the `claude` CLI under the hood — no API key, no config, just your existing Claude Code OAuth session.

## Why It Works

**The system prompt does the heavy lifting.** Three constraints:
1. `Output ONLY the commit message` — no preamble, no explanation
2. `Follow Conventional Commits` — `feat`, `fix`, `chore`, etc.
3. `max 72 chars` — keeps it readable in git log

**The diff is the context.** You're not asking "write a commit message". You're asking "given these exact changes, what happened?" That's a much more answerable question.

## Usage

```bash
# No setup needed if you have Claude Code. Just:
git add .
python /path/to/git_commit.py
# → feat(server): add AI commit message generator via Claude CLI
```

Or wire it into a git alias:

```bash
git config --global alias.ai '!python /path/to/git_commit.py'
# git ai
```

## The Results

Before:
```
update stuff
fix bug
WIP
added the thing
```

After:
```
feat(api): add generate_commit_message tool to MCP server
fix(auth): handle expired token on refresh
refactor(db): extract query builder into separate module
```

## As an MCP Tool Too

I also wrapped it as an MCP tool so Claude Code can call it directly from any conversation:

```python
@mcp.tool()
def generate_commit_message(diff: str) -> str:
    """Generate a Conventional Commits message from a git diff string."""
    full = SYSTEM + "\n\n" + diff
    return subprocess.check_output(["claude", "-p", full], text=True).strip()
```

Full project: [github.com/enjoy-kumawat/my-git-manager](https://github.com/enjoy-kumawat/my-git-manager)

---

20 lines. No new dependencies. No API key. Conventional Commits every time.

The embarrassing part was waiting this long to build it.
