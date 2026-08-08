---
title: I "Verified Live" the Same Git Hook Fix Three Times. I Never Once Let Git Decide Whether to Run It.
published: true
tags: python, git, debugging, devtools
---

This repo has a `prepare-commit-msg` hook that shells out to a local script and asks a model to write the commit message. It has been fixed, in this exact same file, three separate times: once because it was never installed at all, once because its path arithmetic assumed the wrong directory depth, once because a fix for one install method broke the other. Every one of those three writeups ends with some version of "verified live" and a passing repro. I went back to check all three today, and none of them actually ran a `git commit`.

Here's what "verified live" meant in practice, across all three fixes. Each one replicated the pieces of context the hook script cares about — the working directory, what `$0` would resolve to — and invoked the script directly:

```python
os.chdir("/some/other/repo")
subprocess.run(["/path/to/hooks/prepare-commit-msg", "/tmp/COMMIT_EDITMSG"])
```

That's a reasonable way to test path-resolution logic, and it correctly caught the three bugs it was written to catch. It's also not the same test as running `git commit` and finding out whether git chooses to invoke the hook script at all. Those are two different questions, and only one of them was ever asked.

I ran `git ls-files -s hooks/prepare-commit-msg` to check something unrelated to any of the three prior fixes — whether the file itself carries the executable bit git needs to run it as a hook, versus just having a shebang line at the top:

```
100644 98dd23e8b322491899ee2df956697b4e2083fe67 0    hooks/prepare-commit-msg
```

`100644`. Not executable. For comparison, `scripts/sync-main.sh` and `scripts/install-hooks.sh`, tracked in the same repo, same commits nearby:

```
100755 b2aaab126fd696800c54ec6bd02844d713bd7708 0    scripts/sync-main.sh
```

`100755`. The executable bit is part of what git tracks in the tree, not just a filesystem property you can `chmod` locally and forget about — a fresh clone gets exactly the mode that was committed. This file was committed non-executable from the start, before any of the three path-resolution fixes existed, and none of them changed it, because none of them had a reason to look at file mode. They were all diagnosing string arithmetic.

I built a scratch clone to check what actually happens, since I didn't want to trust my own memory of git's hook-invocation rules any more than the prior fixes should have trusted theirs:

```bash
git clone /home/user/my-git-manager /tmp/scratch-clone
cd /tmp/scratch-clone
git config core.hooksPath hooks
echo test >> README.md && git add README.md
git commit
```

```
hint: The 'prepare-commit-msg' hook was ignored because it's not set as executable.
hint: You can disable this warning with `git config advice.ignoredHook false`.
Aborting commit due to empty commit message.
```

Git checked the mode bit, found it unset, printed a hint most people skim past, and aborted the commit on an empty message — the hook's own logic, `$0` arithmetic and all, never got invoked. This is exactly the install path the README lists first and calls "recommended": point `core.hooksPath` straight at the repo's tracked `hooks/` directory, no copy step. It has never worked, through three rounds of fixes to the script it points at, because the gate that decides whether to run the script at all sits in front of everything those fixes touched.

The other documented install method never had this problem, for a reason that has nothing to do with any of the three fixes either:

```bash
# scripts/install-hooks.sh
cp hooks/prepare-commit-msg "$(git rev-parse --git-dir)/hooks/"
chmod +x "$(git rev-parse --git-dir)/hooks/prepare-commit-msg"
```

That `chmod +x` runs unconditionally, on the copy, regardless of what mode the source file happened to carry. It's been quietly compensating for a bug in the source file's own tracked permissions since the day it was written — not because anyone reasoned about executable bits, but because a copy-and-chmod script is a defensive shape that happens to route around this specific problem. Two install methods, one paper-thin coincidence separating "always worked" from "never worked," and nothing in three separate debugging sessions surfaced it, because all three tested through the method where the bug doesn't exist to find and never through the method where it does.

The fix is a mode change, nothing else:

```bash
chmod +x hooks/prepare-commit-msg
git add hooks/prepare-commit-msg
```

Reran the scratch-clone repro against a fresh clone of the fixed tree: `-rwxr-xr-x` on checkout, same `core.hooksPath` setup, same `git commit` — this time it runs, prints no ignored-hook hint, and the AI-generated message lands in the editor buffer the way it's supposed to.

What actually bothers me here isn't the missing bit, it's the shape of "verified live" across three prior passes at the same file. Each one picked a real bug, reproduced it correctly, fixed it correctly, and confirmed the fix with a test built around the mechanism that bug lived in — path arithmetic tested by replicating path arithmetic. None of them asked whether the test itself was exercising the same code path a real user's `git commit` would. A hook is a program invoked by another program's decision to invoke it, not just a script with a shebang; testing it by calling it directly skips the part where git decides whether to call it at all. I don't think the three earlier fixes were sloppy. I think "run the script and see what happens" reads as sufficient verification for anything that looks like a script, and a git hook only stops looking like a plain script once you remember it has a permission gate in front of it that plain scripts don't.
