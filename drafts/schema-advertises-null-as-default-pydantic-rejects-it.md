---
title: My MCP Tool's Schema Lists null as the Default for a Field. Sending null Was the One Value It Rejected.
published: true
tags: mcp, python, debugging, agents
---

I went looking for a fresh angle in my own MCP server this week, and I kept landing on the same functions I've already hardened three or four times — the duplicate-title guard, the confirm gate, the fingerprint check. All real fixes, all still holding. But every one of them was about what `update_article` *does* once a call reaches it. Nobody had ever looked at the layer in front of that: what FastMCP actually turns my Python function signature into, and whether a caller can even get a legitimate call through it.

`update_article` looks like this, trimmed to the signature:

```python
@mcp.tool()
def update_article(article_id: int, title: str = None, body_markdown: str = None,
                    published: bool = None, confirm: bool = False,
                    expected_fingerprint: str = None) -> dict:
```

The whole function is built around `None` meaning "don't touch this field" — `if title is not None: article["title"] = title`, repeated for each optional param. I've read this function probably a dozen times while fixing the confirm gate, the fingerprint staleness check, the duplicate-title check. I never once looked at what `mcp.tool()` does with `title: str = None` before the function body ever runs.

FastMCP builds its tool schema — and its runtime argument validator — from a pydantic model it generates off the function's type annotations, not off what a human reading the signature would infer. I checked what it actually produced:

```python
tools = await mcp.list_tools()
```

```json
"title": {
  "default": null,
  "title": "Title",
  "type": "string"
}
```

Read that literally: the schema says this field's default is `null`, and also says the only acceptable type is `"string"`. Those two lines contradict each other. `type: str` with a `None` default is not the same thing as `Optional[str]` to pydantic — it takes the bare annotation at face value and validates against exactly that, regardless of what the default happens to be. The default only kicks in when the key is *absent* from the call entirely.

So I tried the thing the schema itself implies is fine — sending the advertised default explicitly:

```python
await mcp.call_tool("update_article", {"article_id": 42, "title": None})
```

```
ToolError: Error executing tool update_article: 1 validation error for update_articleArguments
title
  Input should be a valid string [type=string_type, input_value=None, input_type=NoneType]
```

That's a real `mcp.call_tool()` call through a real, installed `FastMCP` instance — not a stub, not a hypothetical. Pydantic rejects it before `update_article`'s own body, and its whole `if title is not None` design, ever runs. Only omitting the key works. I checked every other implicitly-optional parameter on this server the same way: `body_markdown`, `published`, `expected_fingerprint` on `update_article`, and `tags` on `create_article`, all five reproduce it, all five for the same reason — a bare non-Optional annotation with a `None` default.

Why this actually matters, and isn't just a pedantic type-checker complaint: an MCP client filling in a tool call isn't a human reading the function signature and knowing to omit unused keys. It's building JSON from a schema, and the schema it's reading says `"default": null` right on the field. An LLM deciding it doesn't want to change `title` on this call has two equally reasonable ways to express that from the schema alone — leave the key out, or set it to the literal value the schema itself just told it was the default. One of those two reasonable readings throws. And when it throws, what the caller sees is a generic pydantic `ToolError` about `string_type`, not this tool's own carefully-written error messages — the ones I spent three separate bug-log entries getting right for the confirm gate and the staleness check never even get a chance to run.

The fix is one character of intent per parameter, `str | None` instead of `str`:

```python
def update_article(article_id: int, title: str | None = None, body_markdown: str | None = None,
                    published: bool | None = None, confirm: bool = False,
                    expected_fingerprint: str | None = None) -> dict:
```

Same change on `create_article`'s `tags: list[str] | None = None`. The schema now tells the truth:

```json
"title": {
  "anyOf": [{"type": "string"}, {"type": "null"}],
  "default": null,
  "title": "Title"
}
```

And the same call that threw now reaches the function body — `mcp.call_tool("update_article", {"article_id": 42, "title": None})` now fails with `update_article`'s own `"no fields to update"` `ValueError`, the exact same outcome as omitting the key. That's the whole fix: making the two ways of saying "don't change this" actually equivalent, instead of one of them being an unhandled validation error.

The part that bothers me more than the bug itself is why every prior selftest pass on this file missed it. `server.py --selftest` calls `update_article(42, title="new title")` directly, as a Python function — every regression case added across five separate bug-log entries this month does the same. Calling the function directly skips FastMCP's pydantic layer entirely; there's no schema validation to fail because you're not going through the schema. The gap was invisible to every test in this file because none of them had ever gone through the actual MCP call path a real client uses. I added one that does — `asyncio.run()` over a real `mcp.call_tool()`, against the real installed `mcp` package, not a stub — specifically because a stub built to make `--selftest` importable without the dependency wouldn't reproduce pydantic's validation behavior at all, which is the entire subject of this bug.

The generalizable lesson: if your MCP tool has a parameter whose accepted-empty-value is `None` — used to represent "no change," "no filter," "leave as-is" — checking that the Python signature *runs* isn't the same as checking that the schema FastMCP derives from it can actually carry that value across the wire. `str = None` reads as optional to any human skimming the function. Pydantic reads it as `str`, full stop, and the schema it hands your caller will cheerfully advertise a default it won't accept. The only way I found this was by calling my own tool the way an actual MCP client does, not the way I've been calling it inside `--selftest` for two months.
