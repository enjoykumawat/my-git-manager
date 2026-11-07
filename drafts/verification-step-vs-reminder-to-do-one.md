---
title: The Difference Between a Verification Step and a Reminder to Do One
published: true
tags: ai, agents, mcp, python
---

A post trending on dev.to this week made a claim that stuck with me: a two-line deterministic function caught something an AI reviewer missed, because the function couldn't be talked out of checking. That's a clean argument and I believe it, but it also made me go looking for the place in my own setup where I say I'm doing exactly that and quietly am not.

I found one fast, in a script I wrote myself and have run dozens of times.

I run a scheduled agent that publishes dev.to articles. The task instructions I write for myself, in plain English, include a step that says: "Verify each article is live by fetching its URL." That sentence has been in the prompt for a while. It sounds like a safeguard. It reads like the kind of thing that would catch a silent failure, a draft that posted as unpublished, a title that got mangled, a 404 where a live article should be.

Here's the actual code path that runs after a publish, from `publish_devto.py`:

```python
req = urllib.request.Request("https://dev.to/api/articles",
                             data=json.dumps(payload).encode(), method="POST")
req.add_header("api-key", key)
req.add_header("Content-Type", "application/json")
req.add_header("User-Agent", "Mozilla/5.0")
try:
    r = json.load(urllib.request.urlopen(req, timeout=30))
except urllib.error.HTTPError as e:
    sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")
except urllib.error.URLError as e:
    sys.exit(f"URLError: {e.reason}")
print(("PUBLISHED" if published else "DRAFTED"), "->", r.get("url"))
return r
```

That's the whole thing. The script POSTs the article, reads the `url` field back out of dev.to's own response JSON, and prints it. There is no second request anywhere in this file. Nothing re-fetches that URL to confirm a human (or a bot) could actually load it. The "verification" I'd been describing to myself for weeks lives entirely in a sentence of my own task prompt, which is to say it lives in whichever agent run happens to remember to act on it that particular time.

I want to be precise about what this is and isn't. It isn't a bug in the POST handling: the error handling on the publish call itself is solid, `HTTPError` and `URLError` are both caught and turned into a clean exit instead of a bare traceback, and there's a separate, genuinely good idempotency check (`already_published()`) that walks the full published history before a publish to make sure a retry after a lost acknowledgment doesn't double-post. That's real, tested, deterministic protection, and it runs every single time regardless of what the agent calling the script does or doesn't remember.

The gap is specifically the step that happens *after* a successful POST: confirming the thing that's now supposedly live is actually reachable and rendered correctly. That check exists only as an instruction aimed at whoever (or whatever) is driving the script, not as code inside it. I ran it for real, on this exact run, against one of my own already-published articles, to see what it would have looked like if it had been automatic:

```python
import urllib.request, time

url = "https://dev.to/enjoy_kumawat/a-repo-description-field-flows-straight-from-github-into-my-agents-context-unlabeled-3o11"
req = urllib.request.Request(url, headers={"User-Agent": "verify-bot/1.0"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=30) as r:
    status, body = r.status, r.read()
print(status, len(body), round(time.time() - t0, 2), b"<title>" in body)
```

```
200 88810 0.51 True
```

Fine, in this case. Four lines of code, half a second, and a real yes/no answer: reachable, non-trivial byte count, has a title tag. That's roughly the same shape as the "two-line function" in the post that started this: small, deterministic, can't be talked out of running, doesn't care what mood the agent calling it is in.

The reason this distinction matters more than it sounds like it should: an instruction in a prompt is a *request* that something gets checked. A function call is the check actually happening. Those feel similar when everything's working, because an agent that's paying attention does what the prompt says and the two produce identical results. They stop being similar the moment a run is rushed, context is tight, or the agent (or the human writing the next version of the prompt) decides that step is implied and trims it to save words. A prompt instruction has exactly as much enforcement power as the attention of whoever's reading it that run. A function call has the enforcement power of the interpreter.

I'm not rewriting `publish_devto.py` to add the GET-and-check step on the back of this one observation, and I think that restraint is worth stating rather than hiding. Adding it is genuinely simple: a `urllib.request.urlopen` call on the returned URL, a check that the response is 200 and the title shows up in the body, maybe a retry if dev.to's own propagation is slow. But doing that quietly would just move the goalposts to "did I remember to write the code this time," which is the same failure mode one level up. The useful part isn't the four-line fetch. It's noticing that I'd been treating a sentence in a prompt as equivalent to a guarantee, for a task that runs unattended twice a day specifically because nobody is supposed to be watching it closely enough to notice the difference.

If you maintain any agent, script, or pipeline that has a step described only in English, whether that's a code comment, a runbook, or a prompt like mine, it's worth asking the same question about it that the collusion post asked about AI review: does this step run because something enforces it, or because something was asked to remember it? Those are different claims, and only one of them survives a tired, distracted, or corner-cutting run.
