#!/usr/bin/env python3
"""Print every title this account has ever published on DEV.to, paginated.

Usage: python3 scripts/list_all_published_titles.py

Why this exists: the scheduled publishing task's Step 1 GETs
/api/articles/me/published?per_page=30 and Step 2 treats that response as
"the full list" of prior titles to check new topics against. per_page=30
is a page size, not a total — this account has published more than 30
articles since 2026-06-21, so a single unpaginated call silently drops
every older title from that comparison. See docs/project_notes/bugs.md
2026-08-04.

Reads DEV_TO_API from .env next to this script.
"""
import json, os, sys, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)


def load_env():
    try:
        f = open(os.path.join(REPO_ROOT, ".env"), encoding="utf-8")
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


def all_published_titles(key, per_page=30):
    """Every published article {title, published_at, url}, oldest call risk
    (a single per_page=N request) fully walked via the `page` param."""
    titles = []
    page = 1
    while True:
        req = urllib.request.Request(
            f"https://dev.to/api/articles/me/published?per_page={per_page}&page={page}"
        )
        req.add_header("api-key", key)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            batch = json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"dev.to API error {e.code}: {e.read().decode()[:400]}") from e
        if not batch:
            break
        titles.extend({"title": a["title"], "published_at": a["published_at"], "url": a["url"]}
                       for a in batch)
        page += 1
    return titles


def main():
    load_env()
    # Was a bare os.environ["DEV_TO_API"] — a container with no .env, a
    # typo'd key name, or a .env defining only GITHUB_TOKEN raised an
    # unhandled KeyError straight out of main(), instead of exiting through
    # this repo's own ERROR:-prefixed convention. server.py's _gh()/_dev()
    # and publish_devto.py's main() got this exact fix 2026-08-09; this
    # script — sharing the identical os.environ["DEV_TO_API"] shape and
    # written before that fix — was never revisited, and score_published.py
    # (written 2026-08-14, after that fix existed) got it right independently
    # without anyone going back to check this older sibling. Verified live:
    # `env -u DEV_TO_API python3 scripts/list_all_published_titles.py` raised
    # a raw `KeyError: 'DEV_TO_API'` traceback before this fix. See
    # docs/project_notes/bugs.md 2026-08-17 (third entry).
    key = os.environ.get("DEV_TO_API")
    if not key:
        sys.exit("ERROR: DEV_TO_API not set — add it to .env next to this script")
    titles = all_published_titles(key)
    for a in titles:
        print(f"{a['published_at']}  {a['title']}")
    print(f"\n{len(titles)} total published articles.", file=sys.stderr)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        # Stub urlopen to return 2 pages of 2, then an empty page.
        import io
        calls = []

        class FakeResp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        pages = [
            [{"title": "a", "published_at": "t1", "url": "u1"},
             {"title": "b", "published_at": "t2", "url": "u2"}],
            [{"title": "c", "published_at": "t3", "url": "u3"}],
            [],
        ]

        def fake_urlopen(req, timeout=30):
            calls.append(req.full_url)
            return FakeResp(json.dumps(pages[len(calls) - 1]).encode())

        urllib.request.urlopen = fake_urlopen
        result = all_published_titles("fake-key", per_page=2)
        assert len(result) == 3, result
        assert result[-1]["title"] == "c", result
        assert len(calls) == 3, calls  # stopped only once a page came back empty

        # main() used to read `os.environ["DEV_TO_API"]` directly — a
        # missing/unset credential (no .env, a typo'd key name) raised a
        # bare, unhandled KeyError instead of exiting through this repo's
        # own ERROR:-prefixed convention, the same gap server.py's
        # _gh()/_dev() and publish_devto.py's main() were fixed for
        # 2026-08-09 — this script, sharing the identical shape, was never
        # revisited. See docs/project_notes/bugs.md 2026-08-17 (third entry).
        _saved_dev_key = os.environ.pop("DEV_TO_API", None)
        try:
            try:
                main()
                assert False, "missing DEV_TO_API must exit, not silently proceed"
            except SystemExit as e:
                assert e.code is not None and "DEV_TO_API not set" in str(e.code), e.code
            except KeyError:
                assert False, "must exit through ERROR: convention, not a bare KeyError"
        finally:
            if _saved_dev_key is not None:
                os.environ["DEV_TO_API"] = _saved_dev_key

        # `k` (the env var NAME half of a parsed .env line) was never
        # stripped — a `KEY = value` line (spaces around `=`) put a trailing
        # space in the environment variable name, so a later
        # os.environ.get("DEV_TO_API") never finds what .env just set. See
        # docs/project_notes/bugs.md 2026-08-12. load_env() here has no path
        # argument (always REPO_ROOT/.env), so this writes/removes a real
        # REPO_ROOT/.env — only safe because this repo never ships one.
        _env_path = os.path.join(REPO_ROOT, ".env")
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
    else:
        main()
