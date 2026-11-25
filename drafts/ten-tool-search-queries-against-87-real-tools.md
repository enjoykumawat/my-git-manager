---
title: Ten Tool-Search Queries Against 87 Real Tools, and the Two That Never Showed Up
published: true
tags: mcp, ai, claudecode, devtools
---

A trending post this week asked whether a model can pick the right tool out of 738 when an MCP client exposes that many at once. I don't run a server anywhere near that size — the one I maintain for my own GitHub and DEV.to presence has exactly 8 tools — but the session I was writing this article in happened to be sitting on a much smaller, completely real version of the same problem, and I could just run the experiment instead of speculating about it.

Claude Code's current agent harness defers a chunk of its own tool list. Instead of handing the model every tool definition up front, it lists bare names and loads the full schema only when a `ToolSearch` call matches one. At the moment I ran this, my session had 87 distinct deferred tool names sitting behind that search: the built-in scheduling, task-tracking, and artifact tools, plus everything two attached MCP servers (GitHub and a job-search connector) had registered. That's retrieval over real tool definitions, in the exact mechanism the trending post was asking about, just two orders of magnitude smaller. So I picked ten things I'd plausibly want to do, phrased each as a natural request rather than a tool name, and fired them at `ToolSearch` one at a time.

For each query I had a specific tool in mind before I ran it, and I recorded whether that tool showed up in the top 5 results and at what rank:

```
query                                                    expected tool                top rank
send a message to another agent                         SendMessage                   1
edit a jupyter notebook cell                             NotebookEdit                  1
find a library's current documentation                  resolve-library-id            1
stop a running background task                           TaskStop                      1
search for a plugin to install                           SearchPlugins                 2
look at a file inside an MCP resource                    ReadMcpResourceTool            1-2 (both resource tools)
schedule a task to run later / check scheduled tasks     CronCreate                     3 (TaskStop, TaskCreate ranked above it)
watch a long-running background process for completion  Monitor                        not in top 5
look up a github PR's review comments                    pull_request_read              not in top 5
resume work later without losing progress                (no clear single tool)         n/a — ambiguous by design
```

Six of ten landed cleanly, several at rank 1. That's the boring, expected result, and it's worth saying plainly: for a query that uses roughly the same words as the tool's own name or description, retrieval over 87 real definitions worked fine. The interesting part is the two genuine misses, because both point at the same underlying failure mode from different directions.

**The miss that surprised me most** was `Monitor`. I asked for "watch a long-running background process for completion" — which is close to a paraphrase of that tool's actual docstring, which opens with "Start a background monitor that streams events from a long-running script." It didn't appear anywhere in the top 5. What came back instead was a mix of `ArtifactComments`, `ArtifactData`, `TaskStop`, and `CronCreate` — tools that share surface vocabulary ("background," "watch," "task") without doing the thing I asked for. My best guess, and it's only a guess since I can't see the ranking internals, is that `Monitor`'s actual docstring is dense with cron/polling-vs-streaming caveats that dilute the embedding, while `CronCreate`'s docstring repeats "schedule," "watch," and "background" in a tighter, more query-shaped way despite being the wrong tool for a live-streaming request.

**The second miss** was asking to "look up a github pull request's review comments." The tool pool has a real read tool for this — `pull_request_read` — and it never showed up. All five results were write-side PR tools: `update_pull_request`, `update_pull_request_branch`, `pull_request_review_write`, `add_comment_to_pending_review`, `create_pull_request`. Every one of those descriptions mentions "pull request" and "review" somewhere, and in a tool pool skewed toward GitHub's write operations (this account's attached GitHub server has roughly 50 tools, and most of them create, update, or merge something), a read-intent query got outvoted by sheer vocabulary overlap with the write tools.

The one ambiguous case is worth a mention too: "schedule a task to run later and check on existing scheduled tasks" surfaced `TaskStop` and `TaskCreate` — my session's generic todo-list tools — ahead of `CronCreate`, the tool that actually schedules anything. "Task" means two unrelated things in this tool pool (a to-do item vs. a cron job), and the query's literal keyword won the match over the semantic one.

None of this is a knock on `ToolSearch` specifically — ten queries against one index on one day isn't a benchmark, and I'd expect the ranking to behave differently with a different embedding model or a different mix of attached servers. But the shape of the failure is exactly the one the trending post's "pick the right tool out of 738" framing was gesturing at, and now I've watched it happen at a scale I could fully inspect: retrieval degrades first on read-intent queries dropped into a write-heavy pool, and on queries whose words accidentally overlap a less relevant tool's description more than they overlap the right tool's.

For my own 8-tool server this doesn't matter yet — small enough that an agent just gets handed the full list. But if I ever grow it past the point where tools get deferred, the lesson from this is concrete: lead each tool's description with the verb a caller would actually use for the intent, not just the noun for the resource it touches. `get_repo_stats` reads; nothing in my server's docstrings says "read" or "look up" anywhere, they just describe what comes back. That's exactly the gap that burned the `pull_request_read` query above, and it's a one-line fix per tool once you know to look for it.
