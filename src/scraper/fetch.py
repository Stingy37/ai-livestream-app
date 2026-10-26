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
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from contracts import ScrapedDocument

log = logging.getLogger(__name__)

# Sites such as Wikipedia refuse bots whose User-Agent has no way to contact the operator.
USER_AGENT = "ai-livestream-scraper/0.1 (+https://github.com/Stingy37/ai-livestream-app; respects robots.txt)"
CONTACT_NAME = "SCRAPER_CONTACT"  # optional extra contact (e.g. a team email), read from the environment
TIMEOUT = 15  # seconds per request
MAX_PAGE_BYTES = 5_000_000  # skip anything bigger; it is not an article
MIN_BODY_CHARS = 200  # shorter "bodies" are leftovers like a nav word on a JavaScript-only page
MAX_REDIRECTS = 5
CACHE_TTL = 3600  # seconds a cached page stays fresh
CACHE_KEEP = 24 * 3600  # seconds before an old cache file is deleted
CACHE_DIR = Path(os.environ.get("SCRAPER_CACHE_DIR", Path(__file__).resolve().parents[2] / ".cache" / "scraper"))


def user_agent():
    contact = os.environ.get(CONTACT_NAME, "").strip()
    return f"{USER_AGENT[:-1]}; {contact})" if contact else USER_AGENT


class RobotsPolicy:
    """robots.txt answers for each host, read once per run and shared by all threads."""

    def __init__(self, client):
        self.client = client
        self.parsers = {}
        self.host_locks = {}
        self.lock = threading.Lock()  # guards host_locks only

    def allowed(self, url):
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        with self.lock:
            host_lock = self.host_locks.setdefault(host, threading.Lock())
        with host_lock:  # one thread reads a host's robots.txt; others for that host wait, other hosts do not
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

    def __init__(self, directory=CACHE_DIR, ttl=CACHE_TTL, keep=CACHE_KEEP):
        self.directory = Path(directory)
        self.ttl = ttl
        self.keep = keep

    # Delete cache files older than ``keep`` so the folder does not grow forever.
    def prune(self):
        cutoff = time.time() - self.keep
        for path in self.directory.rglob("*"):  # pages, the search/ subfolder, and temp files left by a crash
            try:
                if path.is_file() and path.suffix in (".json", ".tmp") and path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass  # another scene process got there first

    def _path(self, url):
        return self.directory / (hashlib.sha256(url.encode()).hexdigest() + ".json")

    def get(self, url):
        try:
            entry = json.loads(self._path(url).read_text(encoding="utf-8"))
            fresh = time.time() - entry["saved"] <= self.ttl and isinstance(entry["html"], str)
        except (OSError, ValueError, KeyError, TypeError):  # missing or damaged: fetch again
            return None
        return entry if fresh else None

    def put(self, url, html, fetched_at):
        self.directory.mkdir(parents=True, exist_ok=True)
        entry = {"url": url, "html": html, "fetched_at": fetched_at.isoformat(), "saved": time.time()}
        tmp = self._path(url).with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")  # unique across scene processes
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
    published_at, date_only = _parse_date(page.date)
    if date_only:
        metadata["published_date_only"] = True  # the page gave a day, not a time; 00:00 UTC is a stand-in
    return ScrapedDocument(
        url=url,
        title=page.title or url,
        main_text=page.text,
        source_name=page.sitename or host,
        published_at=published_at,
        author=page.author or None,
        fetched_at=fetched_at,
        metadata=metadata,
    )


# (datetime, date_only) from trafilatura's date string. Always timezone-aware, so it can be
# compared with fetched_at (UTC): a date without a time or zone becomes midnight UTC.
def _parse_date(value):
    try:
        parsed = datetime.fromisoformat(value) if value else None
    except ValueError:
        parsed = None
    if parsed is None:
        return None, False
    date_only = "T" not in value and " " not in value.strip()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed, date_only


class Fetcher:
    """Fetches and extracts pages on up to ``max_threads`` threads."""

    def __init__(self, max_threads=8, client=None, cache=None):
        import httpx

        self.max_threads = max(1, max_threads)
        self.client = client or httpx.Client(
            headers={"User-Agent": user_agent()}, timeout=TIMEOUT, follow_redirects=True
        )
        self.cache = cache if cache is not None else PageCache()
        self.cache.prune()
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
        # Redirects are followed by hand so that robots.txt is checked for every hop, not just the first URL.
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            if urlsplit(current).scheme not in ("http", "https"):
                log.info("dropped %s: not an http(s) URL (%s)", url, current)
                return None, None
            if not self.robots.allowed(current):
                log.info("dropped %s: disallowed by robots.txt (%s)", url, current)
                return None, None
            with self.client.stream("GET", current, follow_redirects=False) as response:
                if response.is_redirect:
                    current = urljoin(current, response.headers["location"])
                    continue
                response.raise_for_status()
                kind = response.headers.get("content-type", "")
                if kind and "html" not in kind:
                    log.info("dropped %s: not an HTML page (%s)", url, kind)
                    return None, None
                body = bytearray()
                for chunk in response.iter_bytes():  # streamed, so a huge file is abandoned early
                    body += chunk
                    if len(body) > MAX_PAGE_BYTES:
                        log.info("dropped %s: page too large", url)
                        return None, None
                return _decode(bytes(body), response.charset_encoding), datetime.now(timezone.utc)
        log.info("dropped %s: too many redirects", url)
        return None, None


# Bytes to text. The HTTP header's charset wins; otherwise trafilatura reads the page's own <meta charset>
# (httpx would assume UTF-8 and garble e.g. a windows-1252 page).
def _decode(body, charset):
    if charset:
        try:
            return body.decode(charset, errors="replace")
        except LookupError:  # a charset name Python does not know
            pass
    from trafilatura.utils import decode_file

    return decode_file(body)
