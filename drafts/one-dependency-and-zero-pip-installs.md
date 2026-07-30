---
title: My Repo Has One Pinned Dependency and Zero pip install Calls. I Didn't Design That for Security.
published: true
tags: security, python, ai, devtools
---

Slopsquatting has been getting a lot of attention lately — the attack where someone registers a package name that a coding model likes to hallucinate, and waits for an agent (or a human copy-pasting from one) to `pip install` it. I went looking through my own project for exposure to it and found something I hadn't planned for: there isn't any. Not because I audited dependencies for it. Because the project only has one dependency, and I never once let an agent choose a package name for me.

That's worth digging into, because the reason I ended up here had nothing to do with supply-chain security when I made the call.

## the actual decision

`requirements.txt` in my-git-manager is one line:

```
mcp[cli]>=1.28.0,<2.0.0
```

That's it. The GitHub-profile updater, the MCP server, the dev.to publishing pipeline — all of it runs on stdlib `urllib.request`, `json`, and `base64`. The ADR that set this in motion, from back when I built the first script, reads:

```
### ADR-001: stdlib-only for update_profile.py

**Decision:** Use Python stdlib only (urllib.request, base64, json) — no
requests or third-party libs.

**Alternatives Considered:**
- requests → rejected (requires pip install, adds friction)
- httpx → rejected (same reason)

**Consequences:** Zero-dependency script; slight verbosity in HTTP call
setup.
```

The reasoning was pure convenience. The script needed to run on a fresh checkout without a setup step. `requests` meant one more thing to install before the thing worked. I picked stdlib because I didn't want to run `pip install` at all, for a script that small.

I didn't think about it again until this week, writing a scheduled task that runs twice a day, unattended, in a sandbox — a routine that hits an ImportError or wants to add retry logic is exactly the situation where an agent reaches for `pip install <plausible-sounding-package>`. Except mine can't, because the instruction it's actually running under says:

> Use python3 with urllib from the stdlib for all HTTP calls.

That line was written to keep the sandbox self-contained, not to block slopsquatting. But it does both.

## why the mechanism matters more than the outcome

Slopsquatting works on a specific gap: a model asked to solve a problem ("add exponential backoff to this HTTP client") will sometimes name a package that sounds right and isn't real — `requests-retry-utils`, `http-backoff-lib`, that kind of thing — because it's pattern-matching on naming conventions from training data, not checking a package index. If the person or agent running the suggestion trusts the name and runs `pip install` unverified, and an attacker got there first with a real package under that exact name, the install runs arbitrary code with the current user's permissions. No CVE, no known-bad hash — it's a brand new name nobody flagged, because nobody had a reason to flag it before the model suggested it.

The defense people usually reach for is checking the package against a known-bad list or scanning for typosquats of things you already use. That's necessary but it's downstream — it assumes the install already happened or is about to. The stronger position is not letting an agent's `pip install` suggestion reach a shell at all, which is what a stdlib-only constraint does by accident: there's no dependency-adding code path in the routine to exploit, because the routine was never written to have one.

I'm not arguing stdlib-only is the right call generally — plenty of real projects need a real dependency tree, and refusing to ever add one just pushes the same problem to whoever adds the fifth one under deadline pressure without the habit I happen to have here. What I'm arguing is narrower: when a friction-reduction decision also collapses an entire class of install-time attack surface to zero, that's worth noticing and keeping, not something to "graduate" away from once the project gets more complex.

## what I'd actually check before trusting a suggested install

For the one dependency I do have, here's the verification I'd want before pinning a new one on an agent's word, since "just don't have dependencies" doesn't scale to every project:

```python
import json
import urllib.request

def pypi_exists(pkg: str) -> dict | None:
    """Return PyPI metadata for pkg, or None if it doesn't exist."""
    url = f"https://pypi.org/pypi/{pkg}/json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

info = pypi_exists("requests-retry-utils")
if info is None:
    print("does not exist on PyPI — do not install")
else:
    releases = info.get("releases", {})
    print(f"exists, {len(releases)} releases, first: {min(releases) if releases else 'n/a'}")
```

A package that's zero days old with one release and a name that exactly matches what the model just said out loud is not proof of anything by itself, but it's a five-second check against a `pip install` command an agent just handed you, and it costs less than the incident it might prevent. The real fix, same as the one I already had, is smaller than that: don't let an agent's guess at a package name become a shell command without a human or a script standing between the two. Mine just happened to get that for free, three years before slopsquatting had a name.
