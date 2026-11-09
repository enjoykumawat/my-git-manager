---
title: Across Three Pull Requests to Three Different Projects, Only One Ever Got a Human Review
published: true
tags: opensource, github, productivity, ai
---

I sent three pull requests to three different open source projects over about three weeks this summer: `nodejs/undici`, `vercel/eve`, and `google-gemini/gemini-cli`. All three fixed real, verifiable problems. All three had tests. Only one of them ever had a maintainer actually look at the code.

I went back this week and checked the current state of each one, because I'd been telling myself a story about why two of them stalled, and the story was wrong.

## undici #5446: the one that got reviewed

This PR cleaned up `Dispatcher.md` after a reviewer (`metcoder95`) pointed out the docs I'd added duplicated a section that already existed elsewhere. I cut the ~285-line `## Pre-built interceptors` block down to a 3-line pointer at the real source of truth, `Interceptors.md`, and removed nine now-dead link references.

```diff
- ## Pre-built interceptors
- (285 lines re-documenting dump, retry, redirect, decompress,
-  responseError, dns, cache, and deduplicate interceptors...)
+ See [Interceptors](Interceptors.md) for the full list of
+ built-in interceptors and their options.
```

Opened June 21. `metcoder95` reviewed it the next day and asked for the cleanup above. I pushed the fix. `mcollina` approved and merged it June 29 — eight days, two human reviewers, one substantive back-and-forth about whether the docs were actually correct, not just present.

## eve #454: closed, zero reviews, policy change

This one fixed a real bug: a failed subagent model call (404 from an unresolvable model slug) was getting swallowed and reported to the parent orchestrator as a successful, empty result. One missing `config.mode === "task"` check on the terminal branch of the tool loop, right next to an identical check that already existed on the non-terminal branch.

```ts
// before: terminal branch ignored config.mode entirely
if (classification === "terminal") {
  return { done: true, output: "" };
}

// after: matches the check the non-terminal branch already had
if (classification === "terminal") {
  if (config.mode === "task") {
    return { done: true, output: "", isError: true };
  }
  return { done: true, output: "" };
}
```

I wrote a regression test, confirmed it failed before the fix and passed after, ran the full `packages/eve` suite clean, added a changeset, and signed off every commit under the DCO since I had no GPG key configured. Opened July 1.

It sat for over three months. On October 8, a maintainer closed it — not with a code comment, but with: pull requests are now limited to Vercel team members, and external PRs are being closed. Zero reviews. Zero inline comments. The "No reviews" state on the PR page is the entire record of technical engagement it ever got.

What stung is that this wasn't a surprise rule invented in October. I went back and read `vercel/eve`'s `CONTRIBUTING.md` this week, and it already said, in June: *"External contributions should come through issues rather than unsolicited pull requests."* I had the fix, I had the regression test, and I skipped the one sentence that would have told me to file an issue first and let a maintainer decide whether to invite a PR.

## gemini-cli #28401: closed by a bot, one review comment

This fix addressed a real security-adjacent problem: the shell tool forwarded unbounded command output straight into the model's context with no byte limit, verified against a reporter's 40,319-byte repro. I added a codepoint-safe truncation helper and wired it into both the normal-completion and aborted-command paths:

```ts
const MAX_LLM_OUTPUT_BYTES = 32 * 1024; // 32 KiB

function truncateLlmOutput(output: string): string {
  const bytes = Buffer.byteLength(output, 'utf8');
  if (bytes <= MAX_LLM_OUTPUT_BYTES) return output;
  // head+tail split, truncated on a UTF-8 codepoint boundary so we
  // never cut a multi-byte character in half
  return headTailTruncate(output, MAX_LLM_OUTPUT_BYTES);
}
```

Four unit tests, a clean `tsc` and `eslint` run, 93/93 existing shell tests still green after a rebase onto current `upstream/main`. I opened it July 14, linked to the triaged issue (#28090), which had no existing PR against it.

One human reviewer — `gemini-code-assist`, an automated review bot — left a single inline comment on the `takeBytes` implementation. No maintainer human ever weighed in. On July 29, a triage bot closed the PR: open for 14 days without a `help wanted` label, and nobody with permission had applied one, despite my asking in a follow-up comment.

## What actually decided the outcome

I used to tell myself the eve and gemini-cli fixes just hadn't been "seen yet," as if more patience would have fixed it. Checking this week, that's not what happened. Both PRs were closed by a *process* — a contribution policy and a staleness bot — that had nothing to do with the code. Neither one ever reached the point where a human maintainer evaluated whether the fix was correct.

The undici PR is the outlier not because the fix was better engineered (all three had tests, all three were verified before/after), but because undici has no "team members only" gate and no staleness bot standing between an opened PR and a reviewer's queue.

The actual, checkable lesson: before I invest the hours writing a fix, a regression test, and a changeset, I now spend five minutes checking two things a repo will usually tell me directly:

1. **`CONTRIBUTING.md`, read for restriction language, not just style rules.** "External contributions should come through issues" is a flat rejection of unsolicited PRs, written down in advance. It cost eve's maintainers thirty seconds to close the PR and cost me three months of thinking it was still in a review queue.
2. **Does an issue already exist with a maintainer-applied label, and does the repo auto-close PRs without one?** If a bot is going to close an unlabeled PR on a clock, that clock started the moment I opened it, not the moment someone with triage permission noticed it.

Neither check is novel advice in the abstract. What changed is that I now actually run it before opening the PR, because I have the receipts for what skipping it costs: one merge, two closures, and zero disagreement from a maintainer about whether either fix was right.
