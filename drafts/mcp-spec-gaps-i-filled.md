---
title: Three Gaps I Had to Fill Because the MCP Spec Leaves Them Open
published: true
tags: mcp, security, python, devtools
---

A post titled ["MCP Is Dead Simple. And That's Exactly the Problem"](https://dev.to/sylwia-lask/mcp-is-dead-simple-and-thats-exactly-the-problem-5811) has been doing well this week, and the core claim matches something I've bumped into directly while running my own MCP server: the protocol itself is close to nothing. A tool is a name, a description, a JSON schema for its inputs, and a return value. That's it. Everything that actually makes a server safe or correct to run (how a token gets scoped, what happens when two writes race each other, how a parameter that's allowed to be absent is allowed to be absent) is left for the implementer to invent. Nobody checks your homework.

I run a small FastMCP server (`server.py` in my `my-git-manager` repo) that wraps the GitHub and DEV.to REST APIs so an agent can check my repo stats or manage my blog posts. Building it, I hit three specific places where the spec stayed quiet and I had to pick an answer myself. None of these are exotic; they're the kind of thing every MCP server author runs into and solves slightly differently, which is exactly why it's worth writing down what I chose and why.

## Gap 1: the spec doesn't make "read-only" a real guarantee

My `GITHUB_TOKEN` has `repo, user` scope, full write access, because that's what GitHub token creation hands you if you want to read private repo data at all. There's no fine-grained "read commits and issues but never write" scope on classic tokens. Nothing in MCP's tool definitions enforces that a tool described as read-only actually stays read-only; the schema describes inputs and outputs, not side effects. If I write a GitHub-calling function today and someone (or some agent-generated patch) adds a `method="DELETE"` call inside it next month, the protocol will never notice.

So the guarantee has to live in code, not in the schema:

```python
def _gh(path, method="GET", data=None):
    if method != "GET":
        raise ValueError(f"_gh is read-only — got method={method!r}")
    if data is not None:
        raise ValueError("_gh is read-only — got a data payload on a GET call")
    token = os.environ.get("GITHUB_TOKEN")
    ...
```

That second check matters as much as the first. A `data` payload attached to a nominal GET request doesn't escalate the HTTP verb, but it's a sign something upstream thinks this call is supposed to carry a body, which means the caller's mental model of what `_gh` does has already drifted from what `_gh` actually does. I'd rather fail loudly on that drift than let it through silently. Every tool in this server that touches `_gh` is read-only by construction: there's no write path to accidentally wire up, because the function that talks to GitHub physically can't send one.

## Gap 2: a schema that says "optional" doesn't mean the runtime agrees

MCP tool parameters get turned into a JSON schema automatically, in my case by FastMCP reading Python type hints and handing them to Pydantic. I had a tool parameter written the way most Python code writes an optional list:

```python
def create_article(title: str, body_markdown: str,
                    tags: list[str] | None = None, published: bool = False) -> dict:
```

That reads as "tags is optional, pass nothing or pass None." What Pydantic actually generated was a schema where `tags` is a required array type with a default of `null`, which is a different claim. A caller that explicitly sent `tags: null` got rejected at the validation layer, before my function's own `if tags:` guard ever ran. The type hint and the generated contract disagreed, and the disagreement surfaced as a confusing 422 from a layer underneath my own code, not as anything I wrote.

The fix isn't exotic. It's `Optional[list[str]]` handled explicitly, or a default of `[]` instead of `None` if the semantics allow it. But the point stands: MCP's schema generation is only as honest as whatever library turns your function signature into JSON Schema, and that library's idea of "optional" and Python's idea of "optional" are not guaranteed to be the same idea. You find out the hard way, from a validation error with no stack trace pointing at your code.

## Gap 3: nothing stops two calls from racing each other

My `update_article` tool lets an agent preview a diff against a live DEV.to post, get it approved, then send the write. Between the preview and the confirmed write, nothing in MCP's request/response model prevents the live article from changing underneath: a different tool call, a different session, me editing it by hand. The protocol has no concept of a transaction spanning two tool calls.

So I built one:

```python
def _article_fingerprint(before):
    basis = "\x1f".join(f"{f}={before.get(f)!r}" for f in ("title", "body_markdown"))
    return hashlib.sha256(basis.encode()).hexdigest()
```

A preview call returns this fingerprint alongside the diff. The confirmed write can optionally pass `expected_fingerprint` back; if the live article's current fingerprint doesn't match, the write is rejected instead of silently clobbering whatever changed in between. It's deliberately optional: a caller that skips preview entirely and forces a write on the first call is a legitimate, different use case, not a bug. But without building this myself, "preview then confirm" is just two independent calls that happen to be adjacent in a conversation, with nothing actually tying them together.

## The pattern

None of these three are MCP bugs. The spec was never going to specify token scoping, Pydantic's null-handling quirks, or application-level optimistic locking; that's not what a tool-calling protocol is for. But "the protocol is simple" and "the thing you're building is simple" are different claims, and it's easy to let the first one convince you of the second. Every one of these gaps is a place where I had thirty seconds of feeling confident my schema said what I meant, followed by finding out it didn't. The fix each time was the same: stop trusting the schema to express a guarantee and write the guarantee in code where I can actually see it.
