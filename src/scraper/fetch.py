"""Fetch pages politely and pull out their main body with trafilatura.

Used by both source paths: user-supplied URLs go straight to ``Fetcher.fetch_all``,
and the discovery agent calls the same method on the pages it picks.

  * robots.txt is checked (once per host) before every fetch, with an honest
    User-Agent. If robots.txt cannot be read (401/403/5xx/network), the host is
    skipped, as RFC 9309 asks. Public pages only: no logins, no CAPTCHA bypass.
  * Raw HTML is cached on disk for CACHE_TTL seconds, so repeated runs do not
    re-download the same pages, while regeneration cycles still see fresh news.
  * trafilatura's text is used as ``main_text`` as-is — no second cleaning pass,
    no splitting. Title, author, date and site name come from its metadata when
    it finds them; anything missing stays None rather than being guessed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from contracts import ScrapedDocument

log = logging.getLogger(__name__)

USER_AGENT = "ai-livestream-scraper/0.1 (research project; respects robots.txt)"
TIMEOUT = 15  # seconds per request
MAX_PAGE_BYTES = 5_000_000  # skip anything bigger; it is not an article
MIN_BODY_CHARS = 200  # shorter "bodies" are leftovers like a nav word on a JavaScript-only page
CACHE_TTL = 3600  # seconds a cached page stays fresh
CACHE_DIR = Path(os.environ.get("SCRAPER_CACHE_DIR", Path(__file__).resolve().parents[2] / ".cache" / "scraper"))


class RobotsPolicy:
    """robots.txt answers for each host, read once per run and shared by all threads."""

    def __init__(self, client):
        self.client = client
        self.parsers = {}
        self.lock = threading.Lock()

    def allowed(self, url):
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        with self.lock:  # one thread reads a host's robots.txt; the others wait for its answer
            if host not in self.parsers:
                self.parsers[host] = self._read(host)
            return self.parsers[host].can_fetch(USER_AGENT, url)

    def _read(self, host):
        parser = RobotFileParser()
        try:
            response = self.client.get(f"{host}/robots.txt")
        except Exception as error:
            log.info("robots.txt unreachable for %s (%s); skipping host", host, type(error).__name__)
            parser.disallow_all = True
            return parser
        if response.status_code in (401, 403) or response.status_code >= 500:
            parser.disallow_all = True
        elif response.status_code >= 400:
            parser.allow_all = True  # no robots.txt means no rules
        else:
            parser.parse(response.text.splitlines())
        return parser


class PageCache:
    """Raw HTML on disk, one JSON file per URL."""

    def __init__(self, directory=CACHE_DIR, ttl=CACHE_TTL):
        self.directory = Path(directory)
        self.ttl = ttl

    def _path(self, url):
        return self.directory / (hashlib.sha256(url.encode()).hexdigest() + ".json")

    def get(self, url):
        try:
            entry = json.loads(self._path(url).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if time.time() - entry["saved"] > self.ttl:
            return None
        return entry

    def put(self, url, html, fetched_at):
        self.directory.mkdir(parents=True, exist_ok=True)
        entry = {"url": url, "html": html, "fetched_at": fetched_at.isoformat(), "saved": time.time()}
        tmp = self._path(url).with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(entry), encoding="utf-8")
        os.replace(tmp, self._path(url))  # atomic, so a reader never sees half a file


# Main body and metadata of one page, or None if trafilatura finds no real body.
def extract(html, url, fetched_at=None):
    import trafilatura

    page = trafilatura.bare_extraction(
        html,
        url=url,
        with_metadata=True,
        include_comments=False,
        date_extraction_params={"extensive_search": False},  # only real date markup, no guessing from the URL
    )
    if page is None or len((page.text or "").strip()) < MIN_BODY_CHARS:
        return None
    host = urlsplit(url).netloc.removeprefix("www.")
    metadata = {k: v for k, v in {"hostname": page.hostname, "language": page.language}.items() if v}
    return ScrapedDocument(
        url=url,
        title=page.title or url,
        main_text=page.text,
        source_name=page.sitename or host,
        published_at=_parse_date(page.date),
        author=page.author or None,
        fetched_at=fetched_at,
        metadata=metadata,
    )


def _parse_date(value):
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


class Fetcher:
    """Fetches and extracts pages on up to ``max_threads`` threads."""

    def __init__(self, max_threads=8, client=None, cache=None):
        import httpx

        self.max_threads = max_threads
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True
        )
        self.cache = cache if cache is not None else PageCache()
        self.robots = RobotsPolicy(self.client)

    # Documents for the URLs that worked, in the same order as ``urls``.
    def fetch_all(self, urls):
        urls = list(dict.fromkeys(urls))  # drop repeats, keep order
        if not urls:
            return []
        with ThreadPoolExecutor(max_workers=min(self.max_threads, len(urls)), thread_name_prefix="fetch") as pool:
            documents = list(pool.map(self.fetch_one, urls))
        return [d for d in documents if d is not None]

    # One page as a ScrapedDocument, or None if it cannot be fetched or has no main body.
    def fetch_one(self, url):
        try:
            entry = self.cache.get(url)
            if entry is not None:
                html, fetched_at = entry["html"], datetime.fromisoformat(entry["fetched_at"])
            else:
                html, fetched_at = self._download(url)
                if html is None:
                    return None
                self.cache.put(url, html, fetched_at)
            document = extract(html, url, fetched_at)
            if document is None:
                log.info("dropped %s: no main body found", url)
            return document
        except Exception as error:  # one bad page must never sink the scene
            log.info("dropped %s: %s", url, error)
            return None

    def _download(self, url):
        if urlsplit(url).scheme not in ("http", "https"):
            log.info("dropped %s: not an http(s) URL", url)
            return None, None
        if not self.robots.allowed(url):
            log.info("dropped %s: disallowed by robots.txt", url)
            return None, None
        response = self.client.get(url)
        response.raise_for_status()
        kind = response.headers.get("content-type", "")
        if kind and "html" not in kind:
            log.info("dropped %s: not an HTML page (%s)", url, kind)
            return None, None
        if len(response.content) > MAX_PAGE_BYTES:
            log.info("dropped %s: page too large", url)
            return None, None
        return response.text, datetime.now(timezone.utc)
