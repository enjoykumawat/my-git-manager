#!/bin/sh
# Idempotent pre-flight for scheduled/resumed sessions: if HEAD is detached
# and the detached commit is main (or a fast-forward of it), reattach and
# fast-forward instead of leaving commits floating. Safe to run every time —
# no-ops if HEAD is already on main.
#
# Root cause this works around: this repo's sessions are provisioned by
# checking out a specific commit SHA, not the `main` ref, so every fresh
# or resumed session can start in detached HEAD. See bugs.md 2026-07-18.
set -e

if git symbolic-ref -q HEAD >/dev/null; then
    exit 0  # already on a branch
fi

head_sha="$(git rev-parse HEAD)"

if git merge-base --is-ancestor main "$head_sha" 2>/dev/null; then
    git checkout main
    git merge --ff-only "$head_sha"
    echo "sync-main: reattached and fast-forwarded main to $head_sha"
else
    echo "sync-main: HEAD detached at $head_sha, not a descendant of main — needs manual review" >&2
    exit 1
fi
