---
title: Only 4 of My 53 Logged Bugs Were the Test Suite's Own Fault
published: true
tags: debugging, python, ai, agents
---

A post trending in the agents tag this week claims that changing the scaffold around a model moved benchmark scores +39 points, while changing the model itself only moved them 10. I can't run that benchmark, but I do have something adjacent: a year-ish of bug postmortems for a small MCP server I maintain, every one logged with an Issue, Root Cause, Solution, and Prevention section. If "the scaffold matters more than the model" is right, I'd expect a decent chunk of my own bugs to trace back to the test harness itself being wrong, not the code it was testing. So I counted.

```python
import re
text = open('docs/project_notes/bugs.md', encoding='utf-8').read()
entries = re.split(r'\n### ', text)[1:]
print(len(entries))                                    # 53
print(sum('selftest' in e.lower() for e in entries))    # 30
print(sum(any(k in e.lower() for k in ('fixture','stub','mock')) for e in entries))  # 25
```

53 postmortems. The word "selftest" shows up in 30 of them, "fixture," "stub," or "mock" in 25. My scaffold is everywhere in this log, which is what you'd expect from a repo that runs a `--selftest` block on every script. The more interesting question is narrower: in how many of those 53 was the thing that was actually broken the test harness itself, as opposed to the production code the harness was supposed to be checking? So I filtered the Root Cause section of each entry for language that specifically blames the test setup rather than the logic under test:

```python
rc_pattern = re.compile(
    r'selftest|fixture|stub|never (drove|called|reached|exercised|ran)'
    r'|direct(ly)? as plain python', re.I)

def root_cause(entry):
    m = re.search(r'\*\*Root Cause\*\*:(.*?)(\n- \*\*Solution\*\*|\Z)', entry, re.S)
    return m.group(1) if m else ''

scaffold_fault = [e for e in entries if rc_pattern.search(root_cause(e))]
print(len(scaffold_fault))   # 4
```

Four. Out of 53. That's a smaller number than I expected going in, and I think it's actually the more honest finding: most of the bugs in this log were caught by the scaffold doing its job, not caused by the scaffold failing at it. The selftest suite mentions are mostly "ran the selftest, it passed, here's the new case I added," supporting evidence that the scaffold worked, not that it was broken.

The four where it genuinely was the scaffold's fault are worth looking at individually, because they're not the same failure shape.

**The test exercised a different code path than production.** `update_article`'s optional parameters (`title: str = None`) looked fine when called directly in Python: a `None` default just applies. They were broken under the real MCP framework, because FastMCP builds its validation schema from the type annotation, not the default, and `str = None` schemas as a required string that rejects `null`. Five separate hardening passes on this function had all tested it by calling the Python function directly, never through the actual `mcp.call_tool()` path a real client uses:

```python
# what every prior test did: never hits pydantic validation
update_article(article_id=42, title=None)

# what a real MCP client does: this is what actually broke
await mcp.call_tool("update_article", {"article_id": 42, "title": None})
```

The logic wasn't wrong in a way five rounds of testing should have missed. The tests were just checking the wrong layer.

**The test harness had a side effect it never accounted for.** The `--selftest` fixture for `update_article` stubbed the network call, but not the module-level audit log path, so every CI-style run of `--selftest` appended six real lines to the real production log file. `wc -l logs/article_updates.jsonl` went from 12 to 18 after one run, 18 to 24 after the next. Nobody wrote a logic bug; the test itself was quietly corrupting state outside its own sandbox.

**A single-threaded test structurally can't see a race.** This one's still open, and I think it's the most honest entry in the whole log. `publish_devto.py`'s duplicate-publish guard checks "is this title already live" and then POSTs. Every previous fix to that guard, pagination, fail-open on network errors, was verified with a single-threaded stubbed repro. None of those tests could ever have caught the actual bug: two overlapping runs racing the check-then-post window, both reading "not published," both posting, two duplicate articles. Forcing the interleaving with a `threading.Barrier` reproduces it in seconds. The fix that would obviously work, a local lock file, was written and deliberately not shipped, because this pipeline runs as a fresh container per invocation; a lock file in one container is invisible to the next one, so it would pass every local test while doing nothing against the failure mode that actually matters. That's logged as unfixed, on purpose, rather than shipped as a fix that only looks like one.

**Verified live, never made permanent.** The fourth case is the quietest: a fix gets checked once with a hand-rolled stubbed repro in a terminal, confirmed working, and then nobody turns that repro into a `--selftest` case that survives the session. The next person (or the next me) has no way to know the scenario was ever tested at all.

What I take from the 4-out-of-53 number isn't "my test suite is great." It's that the scaffold and the code under test fail independently, and they fail in different, recognizable shapes. Three of these four are the same underlying mistake with different costumes: the test ran, passed, and told you nothing, because it was checking a path, a side effect, or a timing window that wasn't the one that could actually break. If you're trying to apply "fix the scaffold, not just the model" to your own project, grepping your bug log for "selftest" won't tell you where the scaffold itself is lying to you. You have to go to each Root Cause and ask whether the test that should have caught this ran the real path, in the real framework, under the real concurrency, or a convenient stand-in for all three.
