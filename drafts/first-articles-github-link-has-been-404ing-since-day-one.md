---
title: My First Published Article Links to a GitHub User That Doesn't Exist. It's Been Live and Broken for 45 Days.
published: true
tags: debugging, python, devtools, productivity
---

Ninety-two articles into this account, every fix I've written up has been about this repo's *code* — a `urllib` call with no except block, a path that resolves differently depending on which of two documented install methods you used, a dedup check keyed on the wrong id. What none of the 92 ever did was go back and re-read one of the 92 themselves.

So I did that today, and the account's second-ever article — "I Fixed the 'AI Commit Messages' Problem in 20 Lines of Python," published 2026-06-21, still live — has had a broken GitHub link in it for 45 days. Nobody caught it because nothing in this repo's pipeline, or in any of the 91 posts published after it, ever re-checks a previously-published article's own body.

## What's actually wrong

The article's closing line:

```markdown
Full project: [github.com/enjoy-kumawat/my-git-manager](https://github.com/enjoy-kumawat/my-git-manager)
```

`enjoy-kumawat` — with a hyphen. My real GitHub username, documented in this repo's own `key_facts.md`, is `enjoykumawat` — no separator at all. This isn't the underscore-vs-no-separator bug this repo already fixed once (`bugs.md`, 2026-06-21, "Username Underscore Mismatch" — `.env`'s `GITHUB_USERNAME` held the DEV.to-style value `enjoy_kumawat` with an underscore, and `ADR-003` hardcoded the correct GitHub username as a constant to stop it leaking into API calls). That fix touched exactly one thing: the `GITHUB_USERNAME` constant `_gh()` builds URLs from in `server.py` and `publish_devto.py`. It never touched, and had no way to touch, a URL typed directly into an article's prose. This is a third spelling of the same handle — not the correct one, not the DEV.to one — sitting in a file no code path ever reads.

## Where it came from

`article_draft.md`, still sitting at the repo root, is the source markdown for that exact article — `key_facts.md`'s own Project Files table says so: *"Source for DEV.to article (published 2026-06-21) — `post_article.py`, the script that posted it, was removed 2026-07-16 as a superseded duplicate of `publish_devto.py`."* The typo is baked into the source file itself:

```
$ grep -n "enjoy-kumawat" article_draft.md
93:Full project: [github.com/enjoy-kumawat/my-git-manager](https://github.com/enjoy-kumawat/my-git-manager)
```

`post_article.py` posted this file back on day one, before `publish_devto.py` existed, before there was a tag-truncation rule, before there was a duplicate-title check — before basically every hardening pass this account has ever written about. The typo went live with it and has outlived the script that shipped it by seven weeks.

## Verifying it's actually dead, not just ugly

My first instinct was to `curl` the URL and check the status code. That's the wrong tool here, and it cost me a false positive later in this same investigation (more on that below) — GitHub's anti-bot layer 403s plenty of pages that are completely real, including, as I found out, `github.com/modelcontextprotocol/python-sdk` fetched with a browser-style User-Agent. A 403 from `curl` proves GitHub is suspicious of the client, not that the repo doesn't exist.

`git ls-remote` doesn't have that problem — it's the actual protocol a clone uses, and GitHub's response for a genuinely nonexistent (or private-and-inaccessible) repo has a distinct, unambiguous shape:

```
$ git ls-remote https://github.com/enjoy-kumawat/my-git-manager.git
fatal: could not read Username for 'https://github.com': terminal prompts disabled

$ git ls-remote https://github.com/enjoykumawat/my-git-manager.git
f31350f69d45bcde886043f0e5f42228777d2465	HEAD
f31350f69d45bcde886043f0e5f42228777d2465	refs/heads/main
```

I ran the hyphenated URL against a control — a deliberately made-up repo name (`enjoykumawat/definitely-fake-xyz999`) — three separate times. All three gave the identical `could not read Username` failure, with the identical exit code 128. The real repo, same command, same session, resolves cleanly every time. That's about as close to "verified live" as a dead link gets without an HTTP status code to point at.

## The near-miss that almost made this a worse fix

The article has a sibling problem I initially thought I'd found too: the account's very *first* article, "I built an MCP server that lets Claude manage my GitHub profile and DEV.to articles," links to `github.com/enjoykumawat/developer-presence-mcp` — a repo name this project hasn't gone by since before I started tracking it in `key_facts.md`. Same `curl` 403 pattern I'd just decided not to trust for the first bug. I almost fixed it anyway, on the theory that the repo had been renamed to `my-git-manager` and the old link just never got updated — that's a plausible story, and it's the kind of thing this account's whole publishing pipeline does elsewhere (README paths, hooks paths, `.env` paths all drifted this same way at some point).

I ran `git ls-remote` on it before touching the live article, expecting the same "could not read Username" failure I'd just gotten for the actual bug. Instead:

```
$ git ls-remote https://github.com/enjoykumawat/developer-presence-mcp.git
729c41d145d0a2a4542de5b76d9ecbc21d7d2958	HEAD
729c41d145d0a2a4542de5b76d9ecbc21d7d2958	refs/heads/main
```

A real SHA, a real `main` branch. Pulling the README off it confirmed it's a genuine, separate, still-live repo — an earlier snapshot of this same project under its original name, apparently never deleted when the newer `my-git-manager` repo took over. I'd already PUT a "fix" to that article's live body before running this check (swapping `developer-presence-mcp` for `my-git-manager` everywhere), caught it was wrong, and PUT the original text straight back:

```python
a2 = get_article(3954657)
body2 = a2["body_markdown"]
reverted = body2.replace("my-git-manager", "developer-presence-mcp")
r2 = put_article(3954657, reverted)
```

Confirmed via a follow-up GET that the article matches its original body exactly. No harm done, but it's a clean illustration of why "the fetch 403'd" isn't evidence of anything on its own — it would have replaced one working, correctly-owned link with an unrelated repo, based on a hunch that happened to be wrong, verified by the same shallow check that gave me the false lead in the first place.

## The actual fix

For the one link that really is dead, I didn't touch `server.py` or `publish_devto.py` — there's no code bug here, just a stale live document. `update_article`'s whole reason for existing (`bugs.md`, 2026-07-27: *"a wrong or hallucinated article_id used to silently overwrite whatever it pointed at with no trace"*) is exactly the tool for this, so I used the same PUT-with-diff shape it implements, directly against the live article:

```python
a1 = get_article(3954807)
body1 = a1["body_markdown"]
fixed1 = body1.replace("enjoy-kumawat", "enjoykumawat")
r1 = put_article(3954807, fixed1)
```

Then re-fetched the article and confirmed the string `enjoy-kumawat` no longer appears anywhere in the live body, and that `git ls-remote` against the corrected URL resolves cleanly. Also fixed the same typo in `article_draft.md`, the local source, so a future re-read of that file doesn't reintroduce it.

Before treating this as an isolated typo, I pulled every published article's body (all 92, paginated) and extracted every `github.com/...` link across the entire account. After the fix, there are exactly three distinct GitHub links used anywhere in 92 articles — this project's repo, the MCP Python SDK, and one OSS PR link — and all three now resolve. The hyphenated typo was the only dead one, and it was there from the account's second post onward, never touched by anything published after it.

The pattern here isn't "check your links once." It's that a repo that spends this much effort hardening its *own* code — except blocks, idempotency guards, path resolution across install methods — has zero mechanism pointed at the thing it actually ships: the published articles themselves. Ninety-one follow-up posts audited `server.py`, `reply_comments.py`, `publish_devto.py`, three different hook-path arithmetic bugs. Not one re-read what article #2 actually says.
