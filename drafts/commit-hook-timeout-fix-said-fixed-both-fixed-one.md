---
title: My Commit Hook's Timeout Fix Said "Fixed Both." The Commit Diff Shows It Fixed One.
published: true
tags: python, debugging, claudecode, devtools
---

Fourteen days ago I fixed a bug in `git_commit.py`, the script my `prepare-commit-msg` hook calls to generate a Conventional Commit message from the staged diff. The bug was simple: a `claude -p` subprocess call with no timeout, so a hung CLI process would hang `git commit` itself, indefinitely, with nothing telling you why. I wrote it up, published it, and moved on.

The write-up said: "neither `subprocess.check_output` call in `git_commit.py` ... had a `timeout`. Fixed both."

That sentence has two calls in it. I went back to check both this week, and only one of them actually got fixed.

Here's the function as it's stood since that commit:

```python
diff = subprocess.check_output(["git", "diff", "--staged"], text=True)
if not diff.strip():
    print("Nothing staged. Run `git add` first.")
    raise SystemExit(1)

msg = subprocess.check_output(
    ["claude", "-p", prompt],
    text=True,
    timeout=20,
)
```

`timeout=20` on the `claude -p` call. Nothing on `git diff --staged`, one line above it.

I found this the boring way — going back through files that already have a published fix attached to them and rereading them against what the writeup actually claimed, instead of trusting that "fixed both" meant both. `git show` on the actual commit confirmed it: the diff only touches the `claude -p` block. The commit message itself even says "add timeout to claude subprocess call" — singular, not "calls." The writeup and the shipped code disagreed with each other, and nothing caught it for two weeks because nobody had a reason to reread a bug that already had a green checkmark next to it.

`git diff --staged` looks harmless. It's a fast, local, deterministic command — no network, no LLM call, no reason to expect it to hang. But it can. A held `index.lock` from another process, a slow external diff or textconv driver configured in `.gitattributes`, a pathological binary file matched by a diff filter — any of these can make `git diff` sit there indefinitely, and `subprocess.check_output` with no `timeout=` will wait right along with it. It's exactly the same failure shape the original article was written about, just one call earlier in the same function.

I didn't want to just reread the diff and assume the gap was real — I wanted to watch it happen. I wrote a fake `git` binary and put it first on `PATH`:

```bash
#!/bin/sh
if [ "$1" = "diff" ] && [ "$2" = "--staged" ]; then
    sleep 300
fi
exec /usr/bin/git "$@"
```

Staged a dummy file, then ran the script with an external timeout five seconds longer than what I expected `git_commit.py` to enforce on its own:

```
$ PATH=./fakebin:$PATH timeout 5 python3 git_commit.py
$ echo $?
124
```

Exit code 124 is `timeout`'s own code for "I had to kill it." `git_commit.py` never enforced anything — it would have sat there for the full five minutes my fake `git` was sleeping, same as before the original fix, just one function call to the left of where the fix landed.

The repair is the same pattern the `claude -p` call already uses, just applied to the call that got skipped:

```python
try:
    diff = subprocess.check_output(
        ["git", "diff", "--staged"], text=True, timeout=20
    )
except subprocess.TimeoutExpired:
    print("git diff --staged timed out after 20s", file=sys.stderr)
    raise SystemExit(1)
```

Reran the identical repro, this time giving the external timeout 25 seconds of slack so it wouldn't be the thing that actually kills the process:

```
$ PATH=./fakebin:$PATH timeout 25 python3 git_commit.py
git diff --staged timed out after 20s
$ echo $?
1
```

~20 seconds, a clean message on stderr, exit code 1 — `git_commit.py` killing its own hung subprocess instead of an outer `timeout` command doing it for me. `python3 git_commit.py --selftest` still passes; the regex logic that self-test covers wasn't touched.

What actually bugs me about this one isn't the missing `timeout=` — that's a one-line fix, same as it always was. It's that this repo has a fix for the exact same shape of bug in a *different file*, published one day after the original ("I Fixed a Timeout Bug Two Days Ago. The Copy of That Code Inside My MCP Server Still Has It.") — and that article is specifically about a fix not generalizing to its sibling copy in `server.py`. That one got caught fast, because the second file was easy to grep for. This one sat inside the *original* file, one call away from the code that got fixed, described as fixed by the same writeup that fixed it — and it took two weeks and a deliberate "go reread your own old fixes" pass to notice the diff didn't match the sentence.

A published fix with a passing self-test and a URL attached reads as closed. It isn't closed until the shipped diff actually covers what the writeup says it covers — and the only way to know that is to go read the diff again, not the prose that describes it.
