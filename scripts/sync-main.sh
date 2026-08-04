#!/bin/sh
# Idempotent pre-flight for scheduled/resumed sessions: if HEAD is detached
# and the detached commit is main (or a fast-forward of it), reattach and
# fast-forward instead of leaving commits floating. Safe to run every time —
# no-ops if HEAD is already on main.
#
# Root cause this works around: this repo's sessions are provisioned by
# checking out a specific commit SHA, not the `main` ref, so every fresh
# or resumed session can start in detached HEAD. See bugs.md 2026-07-18.
#
# Fetches origin/main first: the pinned-SHA checkout that produces the
# detached HEAD doesn't go through a `main` refspec fetch, so the cached
# refs/remotes/origin/main can already be behind it at session start,
# ahead of anything this script itself does. See bugs.md 2026-07-22.
#
# Also (re-)installs git hooks every run: .git/hooks/ is untracked, so
# scripts/install-hooks.sh being run once in one container's clone doesn't
# carry over to the next fresh container — it has to run again on every
# session, and nothing else in this repo's workflow called it automatically.
# See bugs.md 2026-07-27.
set -e

HERE="$(cd "$(dirname "$0")/.." && pwd)"
"$HERE/scripts/install-hooks.sh" >/dev/null

git fetch origin main -q 2>/dev/null || true

if git symbolic-ref -q HEAD >/dev/null; then
    exit 0  # already on a branch
fi

head_sha="$(git rev-parse HEAD)"

if git merge-base --is-ancestor main "$head_sha" 2>/dev/null; then
    git checkout main
    git merge --ff-only "$head_sha"
    echo "sync-main: reattached and fast-forwarded main to $head_sha"
elif git merge-base --is-ancestor "$head_sha" main 2>/dev/null; then
    # head_sha is BEHIND main, not ahead — the opposite of the case above,
    # but just as safe: every commit at head_sha already exists on main, so
    # checking out main loses nothing. Treating this like a genuine
    # divergence (the old else branch) blocked automatic recovery for a
    # case where none of the caller's own instructions are needed. See
    # docs/project_notes/bugs.md 2026-08-04.
    git checkout main
    echo "sync-main: HEAD detached at $head_sha was already contained in main; reattached to main ($(git rev-parse main))"
else
    echo "sync-main: HEAD detached at $head_sha, not a descendant of main — needs manual review" >&2
    exit 1
fi
