import requests

from essay_pipeline.fetch import PageCache, PoliteFetcher


class FakeResp:
    def __init__(self, status, text="", headers=None):
        self.status_code, self.text, self.headers = status, text, headers or {}


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls, self.headers = routes, [], {}

    def get(self, url, **kw):
        self.calls.append(url)
        r = self.routes.get(url)
        if isinstance(r, Exception):
            raise r
        return r or FakeResp(404)


def make(tmp_path, routes, **kw):
    clock = {"t": 0.0}
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        clock["t"] += s

    session = FakeSession(routes)
    f = PoliteFetcher(PageCache(tmp_path / "cache"), session=session, sleep=sleep,
                      clock=lambda: clock["t"], delay=lambda: 4.0, **kw)
    return f, session, sleeps


def test_robots_disallow_skips_page(tmp_path):
    f, s, _ = make(tmp_path, {"https://a.test/robots.txt": FakeResp(200, "User-agent: *\nDisallow: /private\n")})
    res = f.get("https://a.test/private/page")
    assert res.skipped == "robots_disallowed"
    assert "https://a.test/private/page" not in s.calls


def test_unreachable_robots_means_skip(tmp_path):
    f, s, _ = make(tmp_path, {"https://a.test/robots.txt": requests.ConnectionError("down")})
    res = f.get("https://a.test/page")
    assert res.skipped == "robots_unavailable"
    assert s.calls == ["https://a.test/robots.txt"]


def test_missing_robots_allows_and_caches(tmp_path):
    f, s, sleeps = make(tmp_path, {"https://a.test/page": FakeResp(200, "<p>hi</p>")})
    first = f.get("https://a.test/page")
    assert first.html == "<p>hi</p>" and not first.from_cache
    assert sleeps == [4.0]  # robots.txt then page on same host => one wait
    second = f.get("https://a.test/page")
    assert second.from_cache and s.calls.count("https://a.test/page") == 1


def test_redirect_target_checked_against_robots(tmp_path):
    f, s, _ = make(tmp_path, {
        "https://a.test/p": FakeResp(301, headers={"Location": "https://b.test/q"}),
        "https://b.test/robots.txt": FakeResp(200, "User-agent: *\nDisallow: /\n"),
    })
    assert f.get("https://a.test/p").skipped == "robots_disallowed"
    assert "https://b.test/q" not in s.calls


def test_offline_never_hits_network(tmp_path):
    f, s, _ = make(tmp_path, {}, offline=True)
    assert f.get("https://a.test/page").skipped == "not_cached"
    assert s.calls == []
