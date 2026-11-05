---
title: What Git Worktrees Actually Isolate (and What They Don't)
published: true
tags: claudecode, devtools, productivity, agents
---

I run most of my agent sessions in a `my-git-manager` repo, and the harness I use has a built-in `EnterWorktree` tool: call it, and the session gets switched into a fresh git worktree under `.claude/worktrees/`, on a new branch, isolated from whatever else is happening in the main checkout. The pitch is obvious — two sessions, two worktrees, no stepping on each other's uncommitted changes. I'd been taking that at face value for weeks. Then a trending post on dev.to this week ("worktrees do not remove the collision, they move it to merge time") made me actually go check what "isolated" means here, instead of assuming it means "conflict-free."

It doesn't mean conflict-free. It means something much narrower, and the gap between those two is worth being precise about if you're going to run several agent sessions against the same repo in parallel.

## What a worktree actually gives you

A git worktree is a second working directory backed by the same `.git` object database, checked out to its own branch. That's the whole mechanism. Two worktrees can have the same file open, with different uncommitted edits, and git will never complain, because nothing about editing files on disk touches git's index until you stage something. I checked this directly:

```bash
git init -q repo && cd repo
echo "line1" > shared.py
git add shared.py && git commit -qm "init"
git branch feature-a
git branch feature-b
git worktree add ../wt-a feature-a
git worktree add ../wt-b feature-b

# in wt-a:
sed -i '1s/.*/line1_CHANGED_BY_A/' shared.py
git add shared.py && git commit -qm "A: change line1"

# in wt-b, at the same time:
sed -i '1s/.*/line1_CHANGED_BY_B/' shared.py
git add shared.py && git commit -qm "B: change line1"
```

Both commits succeed. No warning, no lock contention, no conflict of any kind — because as far as git is concerned, these are two independent branches with independent commit histories. The working-tree isolation is real: an agent in `wt-a` can run a build, leave half-edited files lying around, blow away a `node_modules`, whatever — and `wt-b` never sees any of it, because it's a genuinely separate directory tree.

## What it doesn't give you

The moment you try to bring both branches back together, the isolation is over, because it was never isolation from each other's *content* — just from each other's *filesystem*. Same repo, continuing from the commits above:

```bash
git checkout master
git merge feature-a     # clean
git merge feature-b
```

```
Auto-merging shared.py
CONFLICT (content): Merge conflict in shared.py
Automatic merge failed; fix conflicts and then commit the result.
```

```python
<<<<<<< HEAD
line1_CHANGED_BY_A
=======
line1_CHANGED_BY_B
>>>>>>> feature-b
```

Exactly the conflict you'd get if two people had edited the same line in two normal clones. The worktree didn't prevent it, soften it, or even detect it early — it just delayed the moment you find out, from "while both edits were being made" to "whenever someone merges." For a human workflow that's usually fine, because a human merging two feature branches expects to resolve conflicts. For an agent workflow it's a sharper problem: an agent that successfully committed in its worktree has no signal that its change is about to collide with something else, because nothing it did locally touched the other worktree at all. The first the agent (or you) hears about it is a failed merge, possibly minutes or sessions later, with no context for why line 1 matters to two different branches.

## Where this actually bites

The case I cared about wasn't two humans — it was two agent sessions I'd deliberately split with `EnterWorktree` so they could work on unrelated parts of the same repo without fighting over uncommitted state. That part worked exactly as advertised. What I hadn't thought through: if both sessions end up editing the same shared file — a config, a shared utility, docs/project_notes/key_facts.md, anything neither session "owns" — the worktree boundary gives zero warning that this is about to happen. You find out at merge time, same as the test above, except now it's an agent merging (or a human merging an agent's branch) with no idea which of two automated edits should win.

The practical fix isn't a git feature, it's a workflow one: worktrees are safe for genuinely disjoint work, and risky for anything that touches a small set of shared files, exactly in proportion to how often those files get touched. Before splitting agent sessions into worktrees on a real task, I now check which files each session is likely to touch (`git log --name-only` on the relevant area, or just asking the session what it plans to edit) rather than assuming "different worktree" implies "different files." If two sessions are both going to end up near the same file, I either serialize that part of the work or accept I'm going to resolve a conflict later and plan for it, rather than being surprised by it.

## The one-line version

A git worktree isolates your working directory, not your merge. If you're relying on it to keep two lines of work from fighting, check whether they're actually touching different files — because git won't tell you they aren't until it's too late to matter.
