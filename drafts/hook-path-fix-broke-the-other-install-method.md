---
title: My Hook's Path Fix Passed Its Own Test. It Broke My README's Other Install Method.
published: true
tags: git, ai, claudecode, debugging
---

Four days ago I fixed a bug in a git hook I wrote: `hooks/prepare-commit-msg`, which shells out to a small script (`git_commit.py`) that asks Claude to pre-fill a Conventional Commit message. The hook had never once actually worked, because it computed its own script path one directory too shallow. I fixed it, verified it against a real install, wrote it up, moved on.

This morning I went looking for something else to check in this repo and, on a hunch, reread my own `README.md`'s install instructions for that same hook — not the code, the docs. It documents two ways to install it. My four-day-old fix only works for one of them.

Here's the hook's relevant line, as of four days ago:

```sh
SCRIPT="$(cd "$(dirname "$0")/../.." && pwd)/git_commit.py"
```

The comment above it explained the reasoning: `scripts/install-hooks.sh` (the install method I use in my own environment) copies `hooks/prepare-commit-msg` into `.git/hooks/prepare-commit-msg` — one directory deeper than the file's tracked home at `<repo>/hooks/`. So `$0` at runtime is `.git/hooks/prepare-commit-msg`, and it takes two `..` to climb from there back to the repo root: `.git/hooks/` → `.git/` → repo root. I verified this. I ran `install-hooks.sh` against a real clone, ran a real `git commit`, watched the AI-generated message land in the editor. Closed the loop, or so I thought.

But `README.md`'s "Pre-commit hook (auto mode)" section lists this as the *first*, "recommended" option:

```bash
# Apply to all repos on this machine (recommended)
git config --global core.hooksPath d:/codes/my_git_manger/hooks
```

That's a completely different install mechanism. It doesn't copy anything into `.git/hooks/` at all — it tells git to look for hooks directly inside the tracked `hooks/` directory. When git invokes the hook this way, `$0` is `<repo>/hooks/prepare-commit-msg` — one level shallower than the copied version, not one level deeper. My two-`..` fix, tuned for the copy method, now overshoots the repo root by exactly one directory when someone follows the method my own README calls recommended.

I didn't want to just trace the arithmetic on paper and call it found — that's more or less how the original bug survived two earlier "fixes" to this file that never checked whether git could even reach the hook in the first place. So I built both installs for real.

```bash
git init proj && cd proj
cp -r /path/to/my-git-manager/hooks .
cp /path/to/my-git-manager/git_commit.py .
git config core.hooksPath "$(pwd)/hooks"   # README's "recommended" method — no .git/hooks/ copy
```

Then invoked the hook exactly the way git does — working directory at the repo root, first argument the commit-message file, second argument empty (a normal commit, not `-m`, not a merge):

```bash
$ "$(pwd)/hooks/prepare-commit-msg" /tmp/msgfile ""
$ cat /tmp/msgfile
# (empty)
```

Silent failure — the hook exits 0 either way, so an empty result looks identical whether the AI call failed or the message pre-fill just didn't happen. I pulled the `SCRIPT` line out and ran it standalone to see which:

```bash
$ SCRIPT="$(cd "$(dirname "$(pwd)/hooks/prepare-commit-msg")/../.." && pwd)/git_commit.py"
$ ls "$SCRIPT"
ls: cannot access '.../proj/../git_commit.py': No such file or directory
```

Not "claude CLI not found." Not a timeout. The script path itself resolves one directory above the actual project root — into the *parent* of `proj/`, where `git_commit.py` obviously doesn't exist. Exactly the failure my four-day-old fix was supposed to eliminate, just triggered by the other officially-documented install path instead of the one I happened to test.

I re-ran the copy-into-`.git/hooks/` method in the same session to make sure I wasn't about to un-fix the thing I'd already fixed — confirmed it still needs the two `..` to work. So the two documented methods aren't just differently buggy; they're irreconcilable with any single hardcoded `dirname "$0")` depth. Whichever one I tune the arithmetic for, the other breaks. A third install method — say, a symlink, or a monorepo nesting `hooks/` one level deeper for some subproject — would just need a third depth, forever.

The actual fix is to stop asking `$0` where it thinks it is, and ask git instead:

```sh
SCRIPT="$(git rev-parse --show-toplevel)/git_commit.py"
```

`git rev-parse --show-toplevel` returns the working tree root regardless of where the hook file physically lives or how git was told to find it. I reran both installs against this version:

```bash
# Method A: core.hooksPath -> tracked hooks/ dir directly
$ SCRIPT="$(git rev-parse --show-toplevel)/git_commit.py"; ls "$SCRIPT"
.../proj/git_commit.py   # found

# Method B: copied into .git/hooks/
$ SCRIPT="$(git rev-parse --show-toplevel)/git_commit.py"; ls "$SCRIPT"
.../proj/git_commit.py   # found
```

Both resolve correctly, from the same line, because neither depends on `$0` at all anymore.

The part of this that actually changes how I'll review my own fixes going forward: my original fix passed its own verification completely. I ran the exact install method I use, watched the commit message get generated, and logged it as fixed. Nothing about that process was sloppy — it just never crossed paths with the second sentence of my own README. A path-arithmetic fix that's tuned to *an* install method isn't the same claim as a fix that's tuned to *the* install method, and a repo that documents two ways to install the same hook has quietly made a promise that any `$0`-relative fix has to keep for both, not just the one sitting in front of you when you're debugging.
