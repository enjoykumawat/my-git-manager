#!/usr/bin/env python3
"""DEV.to comment pipeline. Stdlib only.

Usage:
    python reply_comments.py pending   # JSON of unreplied comments not yet drafted
    python reply_comments.py audit     # JSON: drafted replies never actually posted on-site

Skips comments already replied to on-site by ME, and comments whose id_code
already appears in drafts/comment_replies.md (= reply already drafted).
The dev.to API cannot post comments or reactions for normal users (verified
2026-07-18: POST /api/comments is 404, POST /api/reactions is 401), so drafted
replies are pasted manually via each comment_url.

`drafted` is not `posted`: the paste step is manual and this pipeline runs
unattended, so `audit` cross-checks every id_code in drafts/comment_replies.md
against the live on-site thread and reports which ones still have no reply
from ME — the file's growth is otherwise invisible to the pipeline itself.

Reads DEV_TO_API from .env next to this script.
"""
import json, os, re, sys, urllib.request

ME = "enjoy_kumawat"
HERE = os.path.dirname(os.path.abspath(__file__))
DRAFTS = os.path.join(HERE, "drafts", "comment_replies.md")


def load_env():
    try:
        f = open(os.path.join(HERE, ".env"), encoding="utf-8")
    except FileNotFoundError:
        return
    for line in f:
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def api(path):
    req = urllib.request.Request("https://dev.to/api" + path)
    req.add_header("api-key", os.environ.get("DEV_TO_API", ""))
    # dev.to blocks any User-Agent containing "urllib" (case-insensitive), not
    # just the literal default — see docs/project_notes/bugs.md 2026-07-25.
    # Any string avoiding that substring works; it doesn't need to look like a browser.
    req.add_header("User-Agent", "Mozilla/5.0")
    return json.load(urllib.request.urlopen(req, timeout=30))


def strip_html(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


def latest_message(comment):
    """The most recently created message anywhere in this comment's subtree."""
    latest = comment
    for c in comment["children"]:
        candidate = latest_message(c)
        if candidate["created_at"] > latest["created_at"]:
            latest = candidate
    return latest


def needs_reply(comment):
    """True if the newest message in this thread isn't from ME yet.

    Distinct from the old "did I ever post in this subtree" check, which
    was true forever after a single reply, even if the other side posted
    a fresh follow-up afterward. This checks who spoke last.
    """
    return latest_message(comment)["user"]["username"] != ME


def _pending_entry(comment, drafted_codes):
    """The dict to surface for this thread, or None if nothing's pending.

    Keys off the *latest* unanswered message's id_code, not the thread
    root's. A dedup check keyed on the root goes stale the moment a
    second round happens: the root gets one draft, its id_code lands in
    drafted_codes, and every later follow-up in that thread — each with
    its own id_code dev.to assigns it — stays permanently invisible,
    because the check never looks past the root. See
    docs/project_notes/bugs.md 2026-08-02.
    """
    if not needs_reply(comment):
        return None
    latest = latest_message(comment)
    if latest["id_code"] in drafted_codes:
        return None
    return {
        "id_code": latest["id_code"],
        "author": latest["user"]["username"],
        "comment_url": f"https://dev.to/{ME}/comment/{latest['id_code']}",
        "body": strip_html(latest["body_html"]),
    }


def pending():
    try:
        drafted_text = open(DRAFTS, encoding="utf-8").read()
    except FileNotFoundError:
        drafted_text = ""
    drafted_codes = set(re.findall(r"^## (\S+)", drafted_text, re.M))
    out = []
    for a in api(f"/articles?username={ME}&per_page=100"):
        if not a["comments_count"]:
            continue
        for c in api(f"/comments?a_id={a['id']}"):
            entry = _pending_entry(c, drafted_codes)
            if entry:
                out.append({**entry, "article": a["title"]})
    return out


def replied_anywhere_in_subtree(comment):
    """True if ME appears anywhere below this comment, at any depth.

    `c["children"]` only holds the *direct* replies — a reply to my own
    reply lands as a grandchild, not a child, of the original comment `c`.
    See docs/project_notes/bugs.md 2026-08-01.
    """
    return any(
        ch["user"]["username"] == ME or replied_anywhere_in_subtree(ch)
        for ch in comment["children"]
    )


def audit():
    try:
        drafted_text = open(DRAFTS, encoding="utf-8").read()
    except FileNotFoundError:
        drafted_text = ""
    drafted_codes = set(re.findall(r"^## (\S+)", drafted_text, re.M))
    unposted = []
    for a in api(f"/articles?username={ME}&per_page=100"):
        if not a["comments_count"]:
            continue
        for c in api(f"/comments?a_id={a['id']}"):
            if c["id_code"] not in drafted_codes:
                continue
            if not replied_anywhere_in_subtree(c):
                unposted.append({
                    "id_code": c["id_code"],
                    "article": a["title"],
                    "comment_url": f"https://dev.to/{ME}/comment/{c['id_code']}",
                })
    return {"drafted": len(drafted_codes), "never_posted": unposted}


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        def msg(user, ts, children=None, id_code="x", body="body"):
            return {"user": {"username": user}, "created_at": ts, "children": children or [],
                    "id_code": id_code, "body_html": f"<p>{body}</p>"}

        # I replied once (day 1) — no follow-up since. Handled.
        answered = msg("x", "2026-07-24T08:00:00Z", [msg(ME, "2026-07-25T10:00:00Z")])
        assert not needs_reply(answered)

        # I replied once (day 1), then they followed up again (day 2). Still open.
        followed_up = msg("x", "2026-07-24T08:00:00Z", [
            msg(ME, "2026-07-25T10:00:00Z"),
            msg("x", "2026-07-26T09:00:00Z"),
        ])
        assert needs_reply(followed_up)

        # Untouched top-level comment. Open.
        assert needs_reply(msg("x", "2026-07-24T08:00:00Z"))

        # My reply nested two levels deep (root -> their reply -> my reply),
        # the shape a real back-and-forth thread takes. Not a direct child
        # of the root — audit() used to miss this entirely.
        nested_reply = msg("x", "2026-07-20T08:00:00Z", [
            msg("x", "2026-07-20T09:00:00Z", [msg(ME, "2026-07-21T10:00:00Z")]),
        ])
        assert replied_anywhere_in_subtree(nested_reply)
        assert not replied_anywhere_in_subtree(msg("x", "2026-07-24T08:00:00Z"))

        # Round 1: root comment "aaa" drafted, no reply posted yet — pending.
        root_round1 = msg("x", "2026-07-24T08:00:00Z", id_code="aaa", body="original question")
        assert _pending_entry(root_round1, drafted_codes=set())["id_code"] == "aaa"

        # Round 2: I posted my reply on-site, then x followed up with a NEW
        # comment "bbb" nested under my reply. The old code kept using the
        # root's id_code ("aaa") for both the dedup check and the returned
        # body — "aaa" being in drafted_codes made the entire thread
        # disappear from pending() forever, and even without that, the
        # surfaced body would have been the stale original question, not
        # the actual follow-up.
        root_round2 = msg("x", "2026-07-24T08:00:00Z", id_code="aaa", body="original question",
                           children=[
                               msg(ME, "2026-07-25T10:00:00Z", id_code="myreply1", children=[
                                   msg("x", "2026-07-26T09:00:00Z", id_code="bbb",
                                       body="follow-up question"),
                               ]),
                           ])
        entry = _pending_entry(root_round2, drafted_codes={"aaa"})
        assert entry is not None, "follow-up must still surface even though the root was drafted"
        assert entry["id_code"] == "bbb", entry
        assert entry["body"] == "follow-up question", entry
        # And once "bbb" itself has been drafted, the thread correctly drops out.
        assert _pending_entry(root_round2, drafted_codes={"aaa", "bbb"}) is None
        print("selftest ok")
    elif sys.argv[1:2] == ["pending"]:
        load_env()
        print(json.dumps(pending(), indent=2))
    elif sys.argv[1:2] == ["audit"]:
        load_env()
        print(json.dumps(audit(), indent=2))
    else:
        sys.exit(__doc__)
