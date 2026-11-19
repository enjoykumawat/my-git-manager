---
title: If My list_repos Tool Returned Everything GitHub Sends Back, an Agent Would Have to Read 95 Fields Just to Use 7
published: true
tags: mcp, python, devtools, ai
---

A post trending on dev.to right now walks through building a VS Code start page that shows your git repositories at a glance — stars, last commit, open PRs, all laid out in a panel a human can scan. It's a nice idea for a human-facing tool. It also made me go back and check something I'd never actually measured in my own MCP server: how much of what GitHub's API hands back does my own `list_repos` tool actually keep, and how much does it throw away before an agent ever sees it.

I run a small MCP server, `my-git-manager`, that gives Claude Code a handful of tools for checking in on my GitHub and dev.to activity without me tabbing over to a browser. One of those tools is `list_repos`. Here's the part of it that matters:

```python
def list_repos(sort: str = "updated", limit: int = 10) -> list:
    repos = _gh(f"/users/{GITHUB_USERNAME}/repos?sort={api_sort}&per_page={fetch_limit}")
    ...
    return [
        {
            "name": r["name"],
            "description": r.get("description"),
            "stars": r["stargazers_count"],
            "forks": r["forks_count"],
            "language": r.get("language"),
            "url": r["html_url"],
            "updated_at": r["updated_at"],
        }
        for r in repos
    ]
```

Seven fields, picked out of whatever `_gh()` fetched from GitHub's REST API. I wrote that dict comprehension months ago and never once checked what it was leaving on the floor. So I pulled the raw repo-scoped GitHub response for this very repository — `GET /repos/enjoykumawat/my-git-manager` — and counted keys.

```
RAW_FIELD_COUNT: 95
```

Ninety-five fields come back from a single call. My tool keeps seven and drops eighty-eight. A sample of what gets thrown away:

```
allow_auto_merge, allow_forking, allow_merge_commit, allow_rebase_merge,
allow_squash_merge, allow_update_branch, archive_url, archived,
assignees_url, blobs_url, branches_url, clone_url, collaborators_url,
comments_url, commits_url, compare_url, contents_url, contributors_url,
created_at, default_branch, delete_branch_on_merge, deployments_url,
disabled, downloads_url, events_url, ...
```

There's a `permissions` object in there too (`{'admin': True, 'maintain': True, 'push': True, 'triage': True, 'pull': True}`), a `license` field, and something like twenty separate `*_url` fields — `git_commits_url`, `issue_events_url`, `milestones_url`, `subscribers_url` — each one a template string pointing at a different GitHub sub-resource nobody downstream of this tool has ever called.

Seeing the actual number made me think about why that 95-to-7 cut feels obviously correct here and wouldn't feel correct for the VS Code panel in the trending post. A human looking at a start page has a cheap way to ignore ninety fields: they just don't look at the columns they don't care about. Scrolling past a column, or not expanding a row, costs nothing. An agent reading a tool's JSON response doesn't get that option for free — every field in the payload is tokens it paid for whether it ends up using the value or not, and more subtly, every field is also something the model has to decide is irrelevant, which is itself a small amount of work it has to do 95 times instead of 7.

So the right design question for an agent-facing tool isn't "show everything and let the caller filter," the way a UI can afford to. It's closer to: what judgments does this tool actually need to support from the calls I've actually made to it? For `list_repos`, that turned out to already be answered correctly, just never written down. The seven kept fields map cleanly onto the only two things I've ever actually asked this tool to help me do: decide which repo I'm talking about (`name`, `description`, `url`) and get a rough sense of whether it's active or notable (`stars`, `forks`, `language`, `updated_at`). None of the eighty-eight dropped fields have ever come up — not `permissions`, not `license`, not any of the sub-resource URLs, because nothing in this server's actual workflow needs to enumerate collaborators or check merge settings.

`get_repo_stats`, the other GitHub tool in this server, does the same kind of curation against a different question:

```python
def get_repo_stats(repo: str) -> dict:
    r = _gh(f"/repos/{GITHUB_USERNAME}/{repo}")
    return {
        "name": r["name"],
        "stars": r["stargazers_count"],
        "forks": r["forks_count"],
        "watchers": r["watchers_count"],
        "open_issues": r["open_issues_count"],
        "language": r.get("language"),
        "description": r.get("description"),
    }
```

Same 95-field raw response, a different seven-field cut, because the question is different: not "which repo is this" but "how healthy does this one look right now." `watchers` and `open_issues` earn their place here in a way they wouldn't in `list_repos`, where I'm scanning across many repos, not judging one.

The failure mode this points at isn't "too many fields" in the abstract — it's building the field list reactively, one `r["whatever_i_need_this_time"]` at a time, without ever stepping back to ask what the tool's actual contract is supposed to be. That's a slower-motion version of the same mistake as just forwarding the raw GitHub object wholesale: the field set grows to match whatever got needed most recently, and nobody can tell by reading it whether a given field was a deliberate inclusion or an accident of whatever bug I was chasing that week. Eighty-eight absent fields aren't a problem by themselves. An agent-facing tool is supposed to be a smaller, opinionated contract, not a thinner version of the same API — and the only way to know whether a given cut is actually opinionated, instead of just whatever happened to get typed first, is to go measure what you actually kept against what was available. I hadn't done that for this server until writing this, and the fact that the real number was 95 and not something closer to 15 surprised me.

I didn't change any code this run — both tools' field selections checked out against their real usage once I actually looked. But I'm adding a one-line comment next to each dict literal recording which question it's answering, so the next time I add a field it's because a real caller needs it, not because it happened to be sitting right there in the response.
