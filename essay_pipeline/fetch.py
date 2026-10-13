"""Polite fetching: robots.txt, per-domain rate limiting, local HTML cache.

Blocks are never worked around: a disallowed or unverifiable robots.txt means
the page is skipped and the reason is returned for the run log.
"""
import hashlib
import json
import random
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

from . import config


@dataclass
class FetchResult:
    url: str
    html: str | None
    fetched_at: str | None
    from_cache: bool
    skipped: str | None = None  # event type when not fetched
    detail: str = ""


class PageCache:
    def __init__(self, cache_dir: Path):
        self.dir = cache_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]

    def get(self, url: str) -> tuple[str, dict] | None:
        k = self._key(url)
        html_p, meta_p = self.dir / f"{k}.html", self.dir / f"{k}.json"
        if not (html_p.exists() and meta_p.exists()):
            return None
        return html_p.read_text(encoding="utf-8"), json.loads(meta_p.read_text(encoding="utf-8"))

    def put(self, url: str, html: str, meta: dict) -> None:
        k = self._key(url)
        (self.dir / f"{k}.html").write_text(html, encoding="utf-8")
        (self.dir / f"{k}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


class PoliteFetcher:
    def __init__(self, cache: PageCache, session=None, sleep=time.sleep, clock=time.monotonic,
                 delay=lambda: random.uniform(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS),
                 offline: bool = False):
        self.cache = cache
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self._sleep, self._clock, self._delay = sleep, clock, delay
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | str] = {}
        self.offline = offline

    def _wait_turn(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            remaining = self._delay() - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_hit[host] = self._clock()

    def _robots_for(self, url: str):
        """Return a RobotFileParser, or a string explaining why robots.txt
        could not be established (which means: do not fetch)."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        robots_url = origin + "/robots.txt"
        self._wait_turn(parts.netloc)
        rp = urllib.robotparser.RobotFileParser(robots_url)
        try:
            resp = self.session.get(robots_url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as e:
            result = f"robots.txt unreachable ({type(e).__name__})"
        else:
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                result = rp
            elif resp.status_code in (401, 403):
                rp.disallow_all = True
                result = rp
            elif 400 <= resp.status_code < 500:
                rp.allow_all = True  # no robots.txt => no restrictions
                result = rp
            else:
                result = f"robots.txt returned HTTP {resp.status_code}"
        self._robots[origin] = result
        return result

    def check_robots(self, url: str) -> tuple[bool, str]:
        rp = self._robots_for(url)
        if isinstance(rp, str):
            return False, rp
        if not rp.can_fetch(config.USER_AGENT, url):
            return False, "disallowed by robots.txt"
        return True, ""

    def get(self, url: str, refresh: bool = False) -> FetchResult:
        cached = None if refresh else self.cache.get(url)
        if cached:
            html, meta = cached
            return FetchResult(url, html, meta.get("fetched_at"), from_cache=True)
        if self.offline:
            return FetchResult(url, None, None, False, skipped="not_cached",
                               detail="offline run and page is not in cache")

        current = url
        for _ in range(config.MAX_REDIRECTS + 1):
            ok, why = self.check_robots(current)
            if not ok:
                event = "robots_disallowed" if why.startswith("disallowed") else "robots_unavailable"
                return FetchResult(url, None, None, False, skipped=event, detail=f"{current}: {why}")
            self._wait_turn(urlsplit(current).netloc)
            try:
                resp = self.session.get(current, timeout=config.REQUEST_TIMEOUT_SECONDS,
                                        allow_redirects=False)
            except requests.RequestException as e:
                return FetchResult(url, None, None, False, skipped="fetch_error",
                                   detail=f"{current}: {type(e).__name__}: {e}")
            if resp.status_code in (301, 302, 303, 307, 308) and "Location" in resp.headers:
                current = urljoin(current, resp.headers["Location"])
                continue
            if resp.status_code != 200:
                return FetchResult(url, None, None, False, skipped="fetch_error",
                                   detail=f"{current}: HTTP {resp.status_code}")
            fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.cache.put(url, resp.text, {
                "url": url, "final_url": current, "status": resp.status_code,
                "content_type": resp.headers.get("Content-Type"), "fetched_at": fetched_at,
                "user_agent": config.USER_AGENT, "renderer": "requests",
            })
            return FetchResult(url, resp.text, fetched_at, from_cache=False)
        return FetchResult(url, None, None, False, skipped="fetch_error", detail="too many redirects")

    def get_rendered(self, url: str, refresh: bool = False) -> FetchResult:
        """Playwright fetch for pages that need JavaScript. Same robots.txt,
        rate-limit and cache rules as get()."""
        cached = None if refresh else self.cache.get(url)
        if cached:
            html, meta = cached
            return FetchResult(url, html, meta.get("fetched_at"), from_cache=True)
        if self.offline:
            return FetchResult(url, None, None, False, skipped="not_cached",
                               detail="offline run and page is not in cache")
        ok, why = self.check_robots(url)
        if not ok:
            event = "robots_disallowed" if why.startswith("disallowed") else "robots_unavailable"
            return FetchResult(url, None, None, False, skipped=event, detail=why)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return FetchResult(url, None, None, False, skipped="fetch_error",
                               detail="source needs JavaScript but playwright is not installed")
        self._wait_turn(urlsplit(url).netloc)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=config.USER_AGENT)
            resp = page.goto(url, wait_until="networkidle", timeout=config.REQUEST_TIMEOUT_SECONDS * 1000)
            status = resp.status if resp else None
            html, final_url = page.content(), page.url
            browser.close()
        if status != 200:
            return FetchResult(url, None, None, False, skipped="fetch_error", detail=f"HTTP {status}")
        if urlsplit(final_url).netloc != urlsplit(url).netloc:
            ok, why = self.check_robots(final_url)
            if not ok:
                return FetchResult(url, None, None, False, skipped="robots_disallowed",
                                   detail=f"{final_url}: {why}")
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.cache.put(url, html, {
            "url": url, "final_url": final_url, "status": status, "content_type": "text/html",
            "fetched_at": fetched_at, "user_agent": config.USER_AGENT, "renderer": "playwright",
        })
        return FetchResult(url, html, fetched_at, from_cache=False)
