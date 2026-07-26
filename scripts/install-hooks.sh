#!/bin/sh
# Copies hooks/* into .git/hooks/ for this clone.
#
# git only ever executes hooks from .git/hooks/ (or wherever core.hooksPath
# points) — a hooks/ directory committed to the repo has no effect on its
# own. .git/ is never tracked, and core.hooksPath is a machine-local git
# config, so neither `git clone` nor a fresh container checkout wires this
# up automatically. Every new clone/container needs this run once.
# See docs/project_notes/bugs.md 2026-07-26.
set -e

HERE="$(cd "$(dirname "$0")/.." && pwd)"

for f in "$HERE"/hooks/*; do
    name="$(basename "$f")"
    cp "$f" "$HERE/.git/hooks/$name"
    chmod +x "$HERE/.git/hooks/$name"
    echo "install-hooks: installed .git/hooks/$name"
done
