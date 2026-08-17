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
import html, json, os, re, sys, urllib.error, urllib.request

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
            # `k` was never stripped — a `KEY = value` .env line (spaces around
            # `=`) put a trailing space in the environment variable NAME. See
            # docs/project_notes/bugs.md 2026-08-12.
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def api(path):
    req = urllib.request.Request("https://dev.to/api" + path)
    req.add_header("api-key", os.environ.get("DEV_TO_API", ""))
    # dev.to blocks any User-Agent containing "urllib" (case-insensitive), not
    # just the literal default — see docs/project_notes/bugs.md 2026-07-25.
    # Any string avoiding that substring works; it doesn't need to look like a browser.
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"dev.to API error {e.code}: {e.read().decode()[:400]}") from e
    except urllib.error.URLError as e:
        # HTTPError (above) is itself a URLError subclass and only covers
        # responses with an actual HTTP status — a timeout, DNS failure, or
        # connection-refused on this call's `timeout=30` raises the plainer
        # URLError instead, which was still an uncaught raw traceback here
        # even after the 2026-08-03 HTTPError fix. Flagged live-verified-
        # but-unfixed in issues.md 2026-08-04, still open until now. See
        # docs/project_notes/bugs.md 2026-08-08.
        raise RuntimeError(f"dev.to API network error: {e.reason}") from e


def strip_html(h):
    """Plain text of a dev.to comment's body_html, for drafting replies.

    dev.to's API returns rendered HTML: the commenter's own literal <, >, &,
    and quote characters come back HTML-entity-escaped (any correct renderer
    has to do this so real content never gets mistaken for markup), sitting
    right alongside actual tags (<p>, <code>, ...) dev.to wraps the comment
    in. The tag-stripping regex below only ever removed the tags — nothing
    decoded the entities describing the commenter's real characters, so a
    comment like "isn't it faster with a Q&A cache?" or one quoting code
    with generics (List<String>) came back through pending()'s `body` field
    as literal "isn&#39;t ... Q&amp;A" / "List&lt;String&gt;" — the exact
    text a human (or an agent) drafting a reply reads to understand what was
    asked. See docs/project_notes/bugs.md 2026-08-09 (entity-unescape gap).
    """
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def my_articles():
    """Every article this account has published, walking `page` explicitly.

    `pending()`/`audit()` used to call `/articles?username=...&per_page=100`
    with no `page` param at all. Verified live against the real API: that
    exact call consistently comes back short — 98 of this account's 100
    published articles — missing precisely the 2 most recently published
    ones, while the identical call with `page=1` added returns the correct,
    full 100. This isn't the per_page=30 truncation already fixed for the
    publishing task's own novelty check (`scripts/list_all_published_titles.py`,
    bugs.md 2026-08-04) — that was a page-size-vs-total gap on a different
    endpoint (`/articles/me/published`); this is `/articles?username=...`
    silently serving a stale/cached page when `page` is omitted, confirmed by
    diffing the two calls' results directly. Effect here: `pending()`/`audit()`
    never even fetch comments for an account's newest 1-2 articles until
    they age out of whatever's causing the omitted-page response to lag, so
    a fresh comment on a just-published article can't surface as pending no
    matter how long it waits. Walking `page` explicitly from 1 also means
    this stops depending on the account staying under one per_page=100 page
    at all — the same near-miss flagged and deliberately deferred in
    bugs.md 2026-08-04 ("within roughly a week of hitting the same cap"),
    now closed as a side effect of fixing the caching gap. See
    docs/project_notes/bugs.md 2026-08-07.
    """
    articles = []
    page = 1
    while True:
        batch = api(f"/articles?username={ME}&per_page=100&page={page}")
        if not batch:
            break
        articles.extend(batch)
        page += 1
    return articles


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


def _pending_leaves(comment):
    """Yield every leaf comment in this subtree not authored by ME — i.e.
    every conversation branch nobody has replied to yet.

    `needs_reply()`/`latest_message()` only ever look at the single
    globally most-recent message across an entire top-level thread — a
    subtree walk that returns exactly one winner. That's correct for a
    thread that only ever grows one message at a time (the sequential
    case both those functions, and the 2026-08-02 root-vs-latest dedup
    fix built on them, were tested against), but a real dev.to thread can
    also *branch*: two different commenters both replying to the same
    parent comment as siblings, not to each other. `latest_message()`
    still returns only whichever sibling has the later timestamp — the
    other sibling, an equally real and equally unanswered leaf, is never
    considered at all. Worse, it's not just missed for one run: once ME
    replies to the newer branch, that reply becomes the new global
    "latest message," `needs_reply()` reports the whole thread as
    handled, and the older branch's leaf is permanently unreachable —
    nothing ever looks at it again. See docs/project_notes/bugs.md
    2026-08-12 (second entry).
    """
    if not comment["children"]:
        if comment["user"]["username"] != ME:
            yield comment
        return
    for child in comment["children"]:
        yield from _pending_leaves(child)


def _pending_entries(comment, drafted_codes):
    """Every still-open entry in this top-level thread — one per
    unanswered leaf/branch, not just a single "the" pending message."""
    for leaf in _pending_leaves(comment):
        if leaf["id_code"] in drafted_codes:
            continue
        yield {
            "id_code": leaf["id_code"],
            "author": leaf["user"]["username"],
            "comment_url": f"https://dev.to/{ME}/comment/{leaf['id_code']}",
            "body": strip_html(leaf["body_html"]),
        }


def pending():
    try:
        drafted_text = open(DRAFTS, encoding="utf-8").read()
    except FileNotFoundError:
        drafted_text = ""
    drafted_codes = set(re.findall(r"^## (\S+)", drafted_text, re.M))
    out = []
    for a in my_articles():
        if not a["comments_count"]:
            continue
        for c in api(f"/comments?a_id={a['id']}"):
            for entry in _pending_entries(c, drafted_codes):
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


def _walk_comments(comment):
    """Yield this comment and every comment in its subtree, at any depth.

    `audit()`'s own drafted-vs-posted match used to iterate straight over
    `api(f"/comments?a_id=...")`'s return value — which is only the
    THREAD ROOTS, one entry per top-level comment, with everything below
    it reachable only through nested "children" lists. That was fine back
    when `pending()` only ever drafted a reply to a thread's single root
    comment. It hasn't matched reality since the 2026-08-02 fix (a
    follow-up nested under my own reply is its own pending entry, using
    THAT comment's id_code, not the root's) and especially since the
    2026-08-12 `_pending_leaves()` fix (branching threads draft against
    each unanswered LEAF's id_code, at whatever depth it sits). `pending()`
    has drafted against non-root id_codes as the normal case for weeks;
    `audit()`'s outer loop was never updated to look past the root to find
    them. See docs/project_notes/bugs.md 2026-08-17 (second entry).
    """
    yield comment
    for child in comment["children"]:
        yield from _walk_comments(child)


def audit():
    try:
        drafted_text = open(DRAFTS, encoding="utf-8").read()
    except FileNotFoundError:
        drafted_text = ""
    drafted_codes = set(re.findall(r"^## (\S+)", drafted_text, re.M))
    unposted = []
    for a in my_articles():
        if not a["comments_count"]:
            continue
        for root_comment in api(f"/comments?a_id={a['id']}"):
            for c in _walk_comments(root_comment):
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

        # strip_html() must decode HTML entities after stripping tags, not
        # just remove tags and leave a commenter's real <, >, &, and quote
        # characters sitting in the output as literal "&lt;"/"&amp;"/"&#39;"
        # text — dev.to's rendered body_html escapes those exactly like any
        # correct HTML renderer must. See docs/project_notes/bugs.md 2026-08-09.
        assert strip_html("<p>List&lt;String&gt; and Q&amp;A, isn&#39;t it?</p>") == (
            "List<String> and Q&A, isn't it?"
        )
        # Round-trips through _pending_entries's real "body" field too, not
        # just the standalone helper.
        entries = list(_pending_entries(
            msg("x", "2026-07-24T08:00:00Z", id_code="ent1", body="A&amp;B &lt;ok&gt;"),
            drafted_codes=set(),
        ))
        assert len(entries) == 1 and entries[0]["body"] == "A&B <ok>", entries

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
        r1 = list(_pending_entries(root_round1, drafted_codes=set()))
        assert len(r1) == 1 and r1[0]["id_code"] == "aaa", r1

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
        r2 = list(_pending_entries(root_round2, drafted_codes={"aaa"}))
        assert len(r2) == 1, "follow-up must still surface even though the root was drafted"
        assert r2[0]["id_code"] == "bbb", r2
        assert r2[0]["body"] == "follow-up question", r2
        # And once "bbb" itself has been drafted, the thread correctly drops out.
        assert list(_pending_entries(root_round2, drafted_codes={"aaa", "bbb"})) == []

        # Branching thread: root -> my reply -> TWO SEPARATE commenters
        # (B, C) both reply to *my* reply as siblings, not to each other.
        # latest_message()/needs_reply() only ever look at the single
        # globally most-recent leaf in a subtree, so before this fix only
        # C's message (the later timestamp) ever surfaced — B's, an
        # equally real, equally unanswered comment from a different
        # person, was silently dropped and stayed dropped forever, even
        # after C's branch got a reply (which would make C's reply the
        # new "latest," marking the whole thread "handled"). See
        # docs/project_notes/bugs.md 2026-08-12 (second entry).
        branching = msg("userA", "2026-08-01T08:00:00Z", id_code="root1", body="original", children=[
            msg(ME, "2026-08-02T08:00:00Z", id_code="myreply1", children=[
                msg("userB", "2026-08-03T08:00:00Z", id_code="sibB", body="question from B"),
                msg("userC", "2026-08-05T08:00:00Z", id_code="sibC", body="question from C"),
            ]),
        ])
        branch_entries = list(_pending_entries(branching, drafted_codes=set()))
        branch_codes = sorted(e["id_code"] for e in branch_entries)
        assert branch_codes == ["sibB", "sibC"], branch_codes
        # Drafting one sibling leaves the other still pending.
        remaining = list(_pending_entries(branching, drafted_codes={"sibC"}))
        assert [e["id_code"] for e in remaining] == ["sibB"], remaining

        # audit()'s outer loop used to iterate only over the THREAD ROOTS
        # api() returns, matching drafted_codes against `c["id_code"]` for
        # just that top level. pending() has drafted against non-root
        # id_codes as the ordinary case since the 2026-08-02 (nested
        # follow-up) and 2026-08-12 (branching leaf) fixes — a comment
        # nested two levels deep, exactly like `root_round2`/`bbb` above,
        # is a completely normal drafted_codes entry today. audit() never
        # picked up that change: a drafted-but-never-actually-pasted reply
        # to a nested comment matched no root-level id_code at all and
        # silently vanished from `never_posted`, defeating the one thing
        # this function exists to catch. See docs/project_notes/bugs.md
        # 2026-08-17 (second entry).
        _orig_api_for_audit = api
        _audit_thread = msg("userA", "2026-08-01T08:00:00Z", id_code="aaa", body="original question",
                             children=[
                                 msg(ME, "2026-08-02T08:00:00Z", id_code="myreply1", children=[
                                     msg("userA", "2026-08-03T08:00:00Z", id_code="bbb",
                                         body="follow-up question"),
                                 ]),
                             ])

        def _fake_api_for_audit(path):
            if path.startswith("/articles?username="):
                return [{"id": 1, "title": "Test Article", "comments_count": 1}] if "&page=1" in path else []
            if path.startswith("/comments?a_id="):
                return [_audit_thread]
            raise AssertionError(path)

        globals()["api"] = _fake_api_for_audit
        _orig_drafts = DRAFTS
        import tempfile as _tempfile
        _tmp_drafts = _tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
        _tmp_drafts.write("## bbb\nSome drafted reply for the nested follow-up.\n")
        _tmp_drafts.close()
        globals()["DRAFTS"] = _tmp_drafts.name
        try:
            audit_result = audit()
            assert audit_result["drafted"] == 1, audit_result
            assert [u["id_code"] for u in audit_result["never_posted"]] == ["bbb"], (
                "a drafted-but-unposted reply to a NESTED comment must be caught by "
                "audit(), not silently missed because the outer loop only ever "
                "checked root-level id_codes: " + repr(audit_result)
            )
        finally:
            globals()["api"] = _orig_api_for_audit
            globals()["DRAFTS"] = _orig_drafts
            os.unlink(_tmp_drafts.name)

        # my_articles() must walk `page` explicitly rather than trusting a
        # single per_page=100 call — verified live against the real API that
        # omitting `page` returns a short, stale-looking result (98 of 100
        # real articles, missing the 2 newest) while paging explicitly from
        # page=1 returns all of them. Stub api() to return 2 full pages then
        # an empty one, matching that same "walk until empty" contract
        # scripts/list_all_published_titles.py already uses.
        _orig_api = api
        _calls = []

        def _fake_api(path):
            _calls.append(path)
            n = len(_calls)
            if n == 1:
                return [{"id": 1}, {"id": 2}]
            if n == 2:
                return [{"id": 3}]
            return []

        globals()["api"] = _fake_api
        try:
            got = my_articles()
        finally:
            globals()["api"] = _orig_api
        assert [a["id"] for a in got] == [1, 2, 3], got
        assert len(_calls) == 3, _calls  # stopped only once a page came back empty
        assert "page=1" in _calls[0] and "page=2" in _calls[1] and "page=3" in _calls[2], _calls

        # `k` (the env var NAME half of a parsed .env line) was never
        # stripped — a `KEY = value` line (spaces around `=`) put a trailing
        # space in the environment variable name, so a later
        # os.environ.get("DEV_TO_API") never finds what .env just set. See
        # docs/project_notes/bugs.md 2026-08-12. load_env() here has no path
        # argument (always HERE/.env), so this writes/removes a real
        # HERE/.env — only safe because this repo never ships one.
        _env_path = os.path.join(HERE, ".env")
        assert not os.path.exists(_env_path), (
            "refusing to overwrite a real .env for this selftest"
        )
        with open(_env_path, "w") as _f:
            _f.write("DEV_TO_API = spaced-value\n")
        try:
            os.environ.pop("DEV_TO_API", None)
            os.environ.pop("DEV_TO_API ", None)
            load_env()
            assert os.environ.get("DEV_TO_API") == "spaced-value", (
                "whitespace around '=' must not leave a trailing space in the env var NAME: "
                + repr(os.environ.get("DEV_TO_API"))
            )
            assert "DEV_TO_API " not in os.environ
        finally:
            os.unlink(_env_path)
            os.environ.pop("DEV_TO_API", None)
            os.environ.pop("DEV_TO_API ", None)

        print("selftest ok")
    elif sys.argv[1:2] == ["pending"]:
        load_env()
        print(json.dumps(pending(), indent=2))
    elif sys.argv[1:2] == ["audit"]:
        load_env()
        print(json.dumps(audit(), indent=2))
    else:
        sys.exit(__doc__)
