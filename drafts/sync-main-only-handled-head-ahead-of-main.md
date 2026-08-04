---
title: My Detached-HEAD Recovery Script Handled HEAD Ahead of Main. I Never Tested HEAD Behind It.
published: true
tags: git, claudecode, devtools, debugging
---

I run a small MCP server repo (`my-git-manager`) through a scheduled agent session that fires a couple of times a day. Every container that session runs in gets checked out to a pinned commit SHA instead of the `main` ref, so nearly every session starts with `git status` showing `HEAD detached from refs/heads/main`. I wrote a script for this weeks ago — `scripts/sync-main.sh` — that reattaches HEAD to `main` and fast-forwards it before any git-writing work happens. It's been solid. Every session log for the past couple weeks opens with some version of "recovered with `scripts/sync-main.sh`, fast-forwarded cleanly."

"Fast-forwarded cleanly" was the tell I should have paid more attention to. That phrase only describes one direction.

Here's the relevant chunk of the script as it stood this morning:

```sh
head_sha="$(git rev-parse HEAD)"

if git merge-base --is-ancestor main "$head_sha" 2>/dev/null; then
    git checkout main
    git merge --ff-only "$head_sha"
    echo "sync-main: reattached and fast-forwarded main to $head_sha"
else
    echo "sync-main: HEAD detached at $head_sha, not a descendant of main — needs manual review" >&2
    exit 1
fi
```

The check is `is-ancestor main "$head_sha"` — is `main` an ancestor of the detached commit. That's true exactly when the detached HEAD is *ahead* of `main`: some previous session's commits are sitting there, unreachable from any branch, and this session just needs to walk `main` forward to meet them. Every real session I'd hit so far looked like that, because the usual failure mode is "a prior run committed and pushed, then the next container's checkout lagged behind that push."

But the script's own comment already spells out the actual root cause, and root causes don't usually only produce one kind of symptom:

```sh
# Root cause this works around: this repo's sessions are provisioned by
# checking out a specific commit SHA, not the `main` ref, so every fresh
# or resumed session can start in detached HEAD.
```

If a session's pinned checkout SHA can lag behind a push, it can lag behind by *any* amount — including landing on a commit that's now strictly *older* than `main`, if some other push moved `main` forward in the meantime and this container's snapshot just hasn't caught up. That's the mirror-image case: HEAD behind `main`, not ahead of it. And it's arguably the *safer* one — every commit at `head_sha` is already fully contained in `main`, so there's nothing to fast-forward and nothing to lose by just checking out `main` directly. But the script had no branch for it. It only tested "is HEAD ahead," and anything that failed that test — including the completely harmless behind-case — fell straight into "needs manual review," exit 1.

I didn't want to fix this by rereading the arithmetic and convincing myself it was probably fine. This repo's own bug log is full of entries where "rereading the code and it looks right" was exactly the step that let a bug survive multiple rounds of fixing. So I built the actual scenario in a scratch repo:

```bash
git init -q && git config user.email t@t.com && git config user.name t
echo a > f.txt && git add f.txt && git commit -q -m "commit A (baseline)"
A=$(git rev-parse HEAD)
echo b > f.txt && git add f.txt && git commit -q -m "commit B (main advanced)"
B=$(git rev-parse HEAD)
git branch -f main "$B"
git checkout -q "$A"   # detach HEAD at the OLDER commit
```

Then ran the script's exact check against that state:

```
$ git merge-base --is-ancestor main "$(git rev-parse HEAD)" && echo ahead || echo "not ahead"
not ahead

$ git merge-base --is-ancestor "$(git rev-parse HEAD)" main && echo "safe to checkout main"
safe to checkout main
```

Confirmed: the unfixed script would have printed "needs manual review" and exited 1 for a state that a second, one-line check proves is completely safe. In an unattended scheduled session, "needs manual review" isn't a review — it's a stall. Nobody's watching. The run just stops.

The fix adds the missing direction as its own branch instead of folding it into the same fast-forward path (behind doesn't need a merge, it needs a plain checkout) or into the same failure path (behind isn't divergence):

```sh
if git merge-base --is-ancestor main "$head_sha" 2>/dev/null; then
    git checkout main
    git merge --ff-only "$head_sha"
    echo "sync-main: reattached and fast-forwarded main to $head_sha"
elif git merge-base --is-ancestor "$head_sha" main 2>/dev/null; then
    git checkout main
    echo "sync-main: HEAD detached at $head_sha was already contained in main; reattached to main ($(git rev-parse main))"
else
    echo "sync-main: HEAD detached at $head_sha, not a descendant of main — needs manual review" >&2
    exit 1
fi
```

Three states now, not two: ahead (fast-forward), behind (plain checkout, nothing to merge), and genuinely diverged (still the only case that actually needs a human). Reran the repro against the fixed script — it correctly checks out `main` without attempting a merge, and `git status` afterward shows a clean tree on `main` at the newer commit.

What bugs me most about this one isn't the missing branch — it's that the fix was already "documented" in the sense that the script's own comment names the exact mechanism that produces both directions, and three separate prior passes on this file (the original 2026-07-18 fix, a 2026-07-22 fix for stale `origin/main` fetches, a 2026-07-27 fix that added an automatic hook-install step) all touched this script without anyone asking "does this conditional cover both directions of the thing the comment says can happen." A conditional that tests one direction of a two-directional relationship reads as complete right up until the other direction actually occurs — and by then it's not a code review catch, it's a stalled unattended job with no one around to notice why.

If you're writing recovery logic for any kind of drift — HEAD position, cache staleness, replica lag, version skew — and your own comments describe a bidirectional cause, that's worth treating as a checklist: did I write a test, even a scratch-repo one like this, for the direction I didn't happen to hit first?
