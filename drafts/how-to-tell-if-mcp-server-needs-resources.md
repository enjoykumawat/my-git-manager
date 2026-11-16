---
title: How to Tell Whether Your MCP Server Actually Needs Resources, Not Just Tools
published: true
tags: mcp, python, devtools, ai
---

A trending MCP post this week made the case that enforcement belongs in the layer that can't be talked out of it — a database role, not application code. It's a good argument, and it made me look at a different layer-choice in my own MCP server that I'd never actually revisited since I made it: every single thing `server.py` exposes is a `@mcp.tool()`. Not one `@mcp.resource()`. Not one `@mcp.prompt()`.

```bash
$ grep -n "@mcp\.\(tool\|resource\|prompt\)" server.py
242:@mcp.tool()
266:@mcp.tool()
300:@mcp.tool()
317:@mcp.tool()
361:@mcp.tool()
480:@mcp.tool()
630:@mcp.tool()
644:@mcp.tool()
```

Eight tools, zero of anything else. The MCP spec gives implementers three primitives, and this server has been using exactly one of them since it was built.

## What the other two are actually for

Tools, Resources, and Prompts aren't three labels for the same thing with different names. They're wired differently into a client:

- **Tools** are model-invoked. The LLM decides, mid-conversation, whether to call `get_repo_stats("my-git-manager")` based on what it thinks it needs. Side effects are expected and fine.
- **Resources** are addressable, read-only content — a URI the client can fetch (`resources/read`) and list (`resources/list`) *without* a model deciding anything. A client UI can show a resource browser; a user can attach a resource to a conversation before the model ever runs.
- **Prompts** are reusable templates the client surfaces as a menu — "summarize this PR," filled in with arguments — not something the model calls on its own.

Lumping all three into "tool" isn't wrong, exactly. The spec doesn't require anyone to use all three. But it does mean giving up capabilities a client might otherwise expose for free.

## Sorting my own 8 tools by what they actually are

I went through `server.py` function by function and classified each one by whether it has a side effect or just returns data:

| Tool | Side effect? | Takes a parameter? |
|---|---|---|
| `get_github_profile()` | No | No |
| `list_repos(sort, limit)` | No | Yes |
| `get_repo_stats(repo)` | No | Yes |
| `list_articles(per_page)` | No | Yes |
| `get_article_stats(article_id)` | No | Yes |
| `create_article(...)` | Yes (publishes) | Yes |
| `update_article(...)` | Yes (mutates live content) | Yes |
| `generate_commit_message(diff)` | No side effect, but not addressable (needs a fresh `diff` every call) | Yes |

Five of the eight are pure reads. `create_article` and `update_article` are genuinely tool-shaped — nobody should be able to fetch "publish this article" as a static resource. `generate_commit_message` is read-only but the input changes every call, so it isn't addressable by a stable URI either — it stays a tool regardless.

The five reads are the interesting case. `get_github_profile()` in particular takes no arguments and the underlying GitHub profile doesn't change within a session. That's close to the textbook resource case: something a client could list and read without spending a model turn deciding to call it.

## What it would look like as a resource

I didn't change `server.py` for this — this is a sketch of the alternative, not a shipped fix — but the SDK makes the swap small:

```python
# current: a tool, callable by the model
@mcp.tool()
def get_github_profile() -> dict:
    return _gh("/user")

# alternative: a resource, listable and readable by the client directly
@mcp.resource("github://profile")
def get_github_profile_resource() -> dict:
    return _gh("/user")
```

`list_repos` is the harder case, because it isn't a plain GET with no arguments — it takes `sort` and `limit`. Resources support that through URI templates (`github://repos/{sort}`), but the template still has to enumerate the parameter space up front in a way a tool's Python-typed arguments don't need to. For `sort: str = "updated", limit: int = 10` with effectively unbounded `limit` values, that's a worse fit than it looks at first — the tool signature is the more natural shape for an arbitrary integer, and a resource URI template would, in practice, need to flatten `limit` into a small enumerated set or drop the parameter and let the client fetch everything.

## Why "all tools" was probably still the right call here

The honest answer isn't "I should rewrite five of these as resources." It's that the choice is mostly moot for how this server is actually used: the only client that has ever talked to it is a conversational agent (Claude Desktop, via `mcp dev server.py` or the direct config in `key_facts.md`) where tool-calling is the entire wiring surface in practice. A resource that's listable in principle buys nothing if the client never renders a resource browser and the only consumer is an LLM that would just call a tool to read it anyway. The spec primitive that would matter here is the one that matches *this client's* actual UI, not the one that matches the data's shape in the abstract.

That's the actual decision rule, not "reads should be resources, writes should be tools" as a blanket mapping:

- If the only consumer is a model deciding what to fetch mid-conversation, a tool is the right call even for a parameterless read — resources don't get you anything extra there.
- If the client has (or might grow) a UI that lets a human browse or attach content without the model in the loop, a resource for the stable, no-argument reads is worth the URI-template friction for the ones that still need a parameter space.
- Prompts are worth adding only when there's a fixed, reusable template a user would pick from a menu — this server has no such template; every call here is parameterized by live data, not by a user picking a predefined prompt.

Eight tools and nothing else wasn't an oversight I'm fixing — three of the eight checks above land on "tool is still correct," and the other five land on "would be correct only for a client this server has never had." The spec gives you three primitives so you can match a client's actual integration surface. If you only have one kind of client, having tried only one primitive isn't a gap.
