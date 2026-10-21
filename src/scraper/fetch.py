"""Fetching and main-text extraction for the agentic scraper (internal to the Web Scraper team).

One ``Fetcher`` per scene process: a thread pool fetches URLs concurrently and every page goes
through an on-disk cache (``SCRAPE_CACHE_DIR``, TTL ``SCRAPE_CACHE_TTL_S``) so the five scene
processes of one run do not hit the same agency page five times.

Content handling, by content type:

    text/html ........... trafilatura main-text extraction (+ metadata: title, author, date)
    text/plain .......... the raw text (JTWC warnings are plain text)
    application/json .... rendered to readable English sentences: a dedicated renderer for the
                          JMA typhoon JSON (specifications.json / forecast.json / targetTc.json)
                          and a generic ``key: value`` flattener for anything else

``main_text`` is never summarised or truncated: it is the complete extracted text, because the
RAG team chunks it later. ``published_at`` is only ever set from the page itself (metadata /
JSON issue time), never invented.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests

from contracts import ScrapedDocument

log = logging.getLogger(__name__)

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/128.0.0.0 Safari/537.36 typhoon-desk/0.1 (+student weather broadcast)")
DEFAULT_CACHE_DIR = Path(os.environ.get("SCRAPE_CACHE_DIR", "/home/andyshi2/ai-livestream-app/output/cache/pages"))
CACHE_TTL_S = float(os.environ.get("SCRAPE_CACHE_TTL_S", "900"))
MAX_BYTES = int(os.environ.get("SCRAPE_MAX_BYTES", str(6 * 1024 * 1024)))   # bigger downloads are cut off
MIN_TEXT_CHARS = int(os.environ.get("SCRAPE_MIN_TEXT_CHARS", "120"))        # shorter pages have no main body
MIN_PROSE_CHARS = int(os.environ.get("SCRAPE_MIN_PROSE_CHARS", "300"))      # html pages: chars in sentence-like lines

# hostname (suffix) -> issuing agency. Anything else uses og:site_name or the registered domain.
AGENCY_BY_HOST = [
    ("jma.go.jp", "JMA"),
    ("data.jma.go.jp", "JMA"),
    ("metoc.navy.mil", "JTWC"),
    ("pagasa.dost.gov.ph", "PAGASA"),
    ("cwa.gov.tw", "CWA"),
    ("cwb.gov.tw", "CWA"),
    ("nhc.noaa.gov", "NHC"),
    ("weather.gov", "NWS"),
    ("noaa.gov", "NOAA"),
    ("hko.gov.hk", "HKO"),
    ("kma.go.kr", "KMA"),
    ("nchmf.gov.vn", "NCHMF"),
    ("ndrrmc.gov.ph", "NDRRMC"),
    ("phivolcs.dost.gov.ph", "PHIVOLCS"),
    ("reliefweb.int", "ReliefWeb"),
]


def agency_for(url: str, site_name: str | None = None) -> str:
    host = (urlparse(url).hostname or "").lower()
    for suffix, name in AGENCY_BY_HOST:
        if host == suffix or host.endswith("." + suffix):
            return name
    if site_name:
        return site_name.strip()
    parts = host.split(".")
    if len(parts) >= 2:
        # registered domain, e.g. "philstar" from "www.philstar.com"
        core = parts[-2] if parts[-2] not in ("co", "com", "gov", "org", "net", "ac", "edu") or len(parts) < 3 else parts[-3]
        return core.capitalize()
    return host or "unknown"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------------------------
# fetch result
# ---------------------------------------------------------------------------------------------
@dataclass
class FetchResult:
    url: str
    ok: bool
    status: int | None = None
    content_type: str = ""
    text: str = ""                 # extracted main text (complete)
    title: str = ""
    author: str | None = None
    published_at: datetime | None = None
    extraction: str = ""           # trafilatura | text | json
    links: list[str] = field(default_factory=list)   # same-domain links found on html pages
    error: str = ""
    cache_hit: bool = False
    fetched_at: datetime = field(default_factory=_now)
    site_name: str | None = None

    def to_cache(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items()}
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        d["fetched_at"] = self.fetched_at.isoformat()
        return d

    @classmethod
    def from_cache(cls, d: dict[str, Any]) -> "FetchResult":
        d = dict(d)
        d["published_at"] = datetime.fromisoformat(d["published_at"]) if d.get("published_at") else None
        d["fetched_at"] = datetime.fromisoformat(d["fetched_at"])
        return cls(**d)


# ---------------------------------------------------------------------------------------------
# JSON renderers (JMA typhoon products -> English sentences)
# ---------------------------------------------------------------------------------------------
# JMA writes some fields in Japanese only; these are the terms its typhoon products use.
JMA_TERMS = {
    "北": "N", "北北東": "NNE", "北東": "NE", "東北東": "ENE", "東": "E", "東南東": "ESE", "南東": "SE", "南南東": "SSE",
    "南": "S", "南南西": "SSW", "南西": "SW", "西南西": "WSW", "西": "W", "西北西": "WNW", "北西": "NW", "北北西": "NNW",
    "ほとんど停滞": "almost stationary", "停滞": "stationary", "ゆっくり": "slowly",
    "強い": "strong", "非常に強い": "very strong", "猛烈な": "violent", "大型": "large", "超大型": "very large",
    "正確": "accurate", "ほぼ正確": "fairly accurate", "不確か": "uncertain", "全域": "All",
    "台風": "typhoon", "熱帯低気圧": "tropical depression", "温帯低気圧": "extratropical cyclone",
}
JMA_PLACES = {
    "フィリピン": "the Philippines", "ルソン島": "Luzon", "沖縄": "Okinawa", "沖縄本島": "Okinawa Island", "先島諸島": "the Sakishima Islands",
    "石垣島": "Ishigaki Island", "宮古島": "Miyakojima", "与那国島": "Yonaguni Island", "那覇市": "Naha", "那覇": "Naha",
    "台湾": "Taiwan", "東シナ海": "the East China Sea", "南シナ海": "the South China Sea", "日本": "Japan", "九州": "Kyushu",
    "奄美大島": "Amami Oshima", "大東島": "Daito Islands", "南大東島": "Minamidaito", "父島": "Chichijima", "硫黄島": "Iwo To",
    "マリアナ諸島": "the Mariana Islands", "グアム島": "Guam", "グアム": "Guam", "小笠原": "Ogasawara", "本州": "Honshu", "四国": "Shikoku",
    "トラック諸島": "the Chuuk Islands", "カロリン諸島": "the Caroline Islands", "ハイナン島": "Hainan", "華南": "South China",
    "バシー海峡": "the Bashi Channel", "太平洋": "the Pacific", "日本の南": "south of Japan", "近海": "waters near",
}
_DIR_EN = {"北": "north", "北北東": "north-northeast", "北東": "northeast", "東北東": "east-northeast", "東": "east",
           "東南東": "east-southeast", "南東": "southeast", "南南東": "south-southeast", "南": "south", "南南西": "south-southwest",
           "南西": "southwest", "西南西": "west-southwest", "西": "west", "西北西": "west-northwest", "北西": "northwest", "北北西": "north-northwest"}
_JMA_REL = {("の" + jp): (en + " of ") for jp, en in _DIR_EN.items()}
_JMA_REL.update({"付近": "near ", "の近海": "waters near ", "沖": "off "})


def jma_english(s: str) -> str:
    """Translate the Japanese-only JMA terms (directions, classes, places) to English; unknown text is kept."""
    if not s:
        return s
    if s in JMA_TERMS:
        return JMA_TERMS[s]
    if s in JMA_PLACES:
        return JMA_PLACES[s]
    for rel, en in sorted(_JMA_REL.items(), key=lambda kv: -len(kv[0])):
        if s.endswith(rel):
            base = s[: -len(rel)]
            return en + JMA_PLACES.get(base, base)
    for jp, en in sorted(JMA_PLACES.items(), key=lambda kv: -len(kv[0])):
        s = s.replace(jp, en)
    return s


def _en(x: Any) -> str:
    """Pick the English form of a JMA {jp, en} label, or translate/stringify."""
    if isinstance(x, dict):
        return str(x.get("en") or jma_english(str(x.get("jp") or "")))
    return "" if x is None else jma_english(str(x))


def _utc(x: Any) -> str:
    if isinstance(x, dict):
        return str(x.get("UTC") or x.get("utc") or x.get("JST") or "")
    return "" if x is None else str(x)


def render_jma_part(part: dict[str, Any], storm_name: str) -> str:
    """One English sentence block for one JMA analysis / forecast element."""
    label = _en(part.get("part"))
    valid = _utc(part.get("validtime"))
    bits = [f"JMA {label or 'information'} for {storm_name} valid {valid} UTC" if valid else f"JMA {label or 'information'} for {storm_name}"]
    cat = _en(part.get("category"))
    if cat:
        bits.append(f"category {cat}")
    pos = part.get("position") or {}
    deg = pos.get("deg") if isinstance(pos, dict) else None
    if isinstance(deg, list) and len(deg) == 2:
        bits.append(f"center near {deg[0]}N {deg[1]}E")
    loc = part.get("location")
    if loc:
        bits.append(f"location {_en(loc)}")
    if part.get("pressure"):
        bits.append(f"central pressure {part['pressure']} hPa")
    mw = part.get("maximumWind") or {}
    sus, gust = mw.get("sustained") or {}, mw.get("gust") or {}
    if sus:
        bits.append(f"maximum sustained winds {sus.get('m/s', '?')} m/s ({sus.get('kt', '?')} kt, 10-minute average)")
    if gust:
        bits.append(f"gusts {gust.get('m/s', '?')} m/s ({gust.get('kt', '?')} kt)")
    course, speed = part.get("course"), part.get("speed") or {}
    if course or speed:
        bits.append(f"moving {_en(course) or 'direction not reported'} at {speed.get('km/h', '?')} km/h ({speed.get('kt', '?')} kt)")
    for key, name in (("stormWarning", "storm-force winds (>= 25 m/s)"), ("galeWarning", "gale-force winds (>= 15 m/s)")):
        for w in part.get(key) or []:
            area, rng = _en(w.get("area")), w.get("range") or {}
            bits.append(f"{name} within {rng.get('km', '?')} km ({rng.get('nm', '?')} nm) to the {area}" if area and area != "All"
                        else f"{name} within {rng.get('km', '?')} km ({rng.get('nm', '?')} nm) of the center")
    pc = part.get("probabilityCircleRadius")
    if pc:
        bits.append(f"70% probability circle radius {pc.get('km', '?')} km")
    for key, name in (("intensity", "intensity class"), ("scale", "size class")):
        if part.get(key):
            bits.append(f"{name} {_en(part[key])}")
    return "; ".join(bits) + "."


def render_jma_typhoon_json(data: Any) -> tuple[str, str, datetime | None]:
    """(text, title, issue time) for specifications.json / forecast.json / targetTc.json shapes."""
    issued: datetime | None = None
    if isinstance(data, list) and data and isinstance(data[0], dict) and "tropicalCyclone" in data[0]:
        lines = []
        for tc in data:
            issue = tc.get("issue")
            lines.append(f"JMA lists active tropical cyclone {tc.get('tropicalCyclone')} (typhoon number {tc.get('typhoonNumber')}, "
                         f"category {tc.get('category')}), information issued {issue}.")
            issued = issued or _parse_iso(issue)
        return "\n".join(lines), "JMA active tropical cyclones", issued
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("part") == "title":
        head = data[0]
        name = _en(head.get("name")) or "the typhoon"
        number = head.get("typhoonNumber", "")
        issue = _utc(head.get("issue"))
        issued = _parse_iso(issue)
        storm = f"Typhoon {name} (typhoon number {number})" if number else f"Typhoon {name}"
        lines = [f"JMA tropical cyclone information for {storm}, issued {issue} UTC."]
        for part in data[1:]:
            if isinstance(part, dict):
                lines.append(render_jma_part(part, storm))
        return "\n".join(lines), f"JMA tropical cyclone information: {storm}", issued
    return render_generic_json(data), "JSON document", None


def render_generic_json(data: Any, prefix: str = "", out: list[str] | None = None) -> str:
    """Flatten any JSON into 'a.b[0].c: value' lines (readable, complete)."""
    first = out is None
    out = [] if out is None else out
    if isinstance(data, dict):
        for k, v in data.items():
            render_generic_json(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            render_generic_json(v, f"{prefix}[{i}]", out)
    else:
        out.append(f"{prefix}: {data}")
    return "\n".join(out) if first else ""


def _parse_iso(s: Any) -> datetime | None:
    if not isinstance(s, str) or not s:
        return None
    try:
        return _to_utc(datetime.fromisoformat(s.replace("Z", "+00:00")))
    except ValueError:
        return None


# ---------------------------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------------------------
def extract_html(html: str, url: str) -> tuple[str, dict[str, Any], list[str]]:
    """(main text, metadata dict, same-domain links) from an html page with trafilatura."""
    import trafilatura
    from trafilatura.metadata import extract_metadata

    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True,
                               favor_recall=True, output_format="txt") or ""
    if len(text) < FALLBACK_MIN_CHARS:
        # Agency pages are often tables trafilatura discards; fall back to the page's visible text when it
        # holds clearly more *prose* (long lines / sentences, not menu entries). Still the page's own
        # words, never a summary.
        visible = visible_text(html)
        prose = "\n".join(ln for ln in visible.splitlines() if len(ln) >= 60 or ln.endswith((".", "。")))
        if len(prose) >= 3 * max(len(text), 1) and len(prose) > FALLBACK_MIN_CHARS:
            text = visible
    meta: dict[str, Any] = {}
    try:
        md = extract_metadata(html, default_url=url)
        if md is not None:
            d = md.as_dict() if hasattr(md, "as_dict") else dict(md.__dict__)
            meta = {k: d.get(k) for k in ("title", "author", "date", "sitename", "description")}
    except Exception as exc:  # noqa: BLE001 - metadata is best effort
        log.debug("metadata extraction failed for %s: %s", url, exc)
    if not meta.get("date"):
        try:
            from htmldate import find_date

            meta["date"] = find_date(html, url=url, outputformat="%Y-%m-%dT%H:%M:%S", extensive_search=False)
        except Exception:  # noqa: BLE001
            pass
    return text, meta, same_domain_links(html, url)


FALLBACK_MIN_CHARS = int(os.environ.get("SCRAPE_FALLBACK_MIN_CHARS", "600"))

# Parsing runs in helper processes: lxml/libxml2 can abort the whole process on a malformed page ("double free or
# corruption"), which would take the scene's worker down with it. A crash or hang now costs only that page.
_PARSE_LOCK = threading.Lock()
_PARSE_POOL = None
PARSE_TIMEOUT_S = float(os.environ.get("SCRAPE_PARSE_TIMEOUT_S", "60"))


def _parse_pool():
    global _PARSE_POOL
    with _PARSE_LOCK:
        if _PARSE_POOL is None:
            import multiprocessing as mp
            from concurrent.futures import ProcessPoolExecutor

            _PARSE_POOL = ProcessPoolExecutor(max_workers=int(os.environ.get("SCRAPE_PARSE_WORKERS", "3")),
                                              mp_context=mp.get_context("spawn"))
        return _PARSE_POOL


def _reset_parse_pool(broken) -> None:
    global _PARSE_POOL
    with _PARSE_LOCK:
        if _PARSE_POOL is broken:
            _PARSE_POOL = None
    try:
        broken.shutdown(wait=False, cancel_futures=True)
    except Exception:  # noqa: BLE001
        pass


def extract_html_isolated(html: str, url: str) -> tuple[str, dict[str, Any], list[str]]:
    """extract_html in a helper process; ("", {}, []) when the parser crashes or hangs on this page."""
    from concurrent.futures import TimeoutError as FutureTimeout
    from concurrent.futures.process import BrokenProcessPool

    pool = _parse_pool()
    try:
        return pool.submit(extract_html, html, url).result(timeout=PARSE_TIMEOUT_S)
    except (BrokenProcessPool, FutureTimeout) as error:
        log.warning("html parser %s on %s; page skipped", "crashed" if isinstance(error, BrokenProcessPool) else "timed out", url)
        _reset_parse_pool(pool)
        return "", {}, []


def prose_chars(text: str) -> int:
    """Characters in lines that look like sentences (long, or ending in a full stop): menus do not count."""
    return sum(len(ln) for ln in text.splitlines() if len(ln.strip()) >= 60 or ln.strip().endswith((".", "。", "!", "?")))


def visible_text(html: str) -> str:
    """Whitespace-normalised visible text of a page (scripts, styles, nav chrome removed)."""
    try:
        import lxml.html

        doc = lxml.html.fromstring(html)
        for bad in doc.xpath("//script|//style|//noscript|//svg|//template"):
            parent = bad.getparent()
            if parent is not None:
                parent.remove(bad)
        for block in doc.xpath("//p|//div|//li|//tr|//h1|//h2|//h3|//h4|//br|//td"):
            block.tail = ("\n" + block.tail) if block.tail else "\n"
        raw = doc.text_content()
    except Exception:  # noqa: BLE001
        raw = re.sub(r"<[^>]+>", " ", html)
    lines = [re.sub(r"[ \t\u00a0]+", " ", ln).strip() for ln in raw.splitlines()]
    return "\n".join(ln for ln in lines if ln)


_HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#?]+)(?:[?#][^"']*)?["']""", re.IGNORECASE)


def same_domain_links(html: str, base_url: str, limit: int = 200) -> list[str]:
    host = (urlparse(base_url).hostname or "").lower()
    out, seen = [], set()
    for m in _HREF_RE.finditer(html):
        href = urljoin(base_url, m.group(1).strip())
        p = urlparse(href)
        if p.scheme not in ("http", "https") or (p.hostname or "").lower() != host:
            continue
        if p.path.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".ico", ".pdf", ".zip", ".xml")):
            continue
        if href in seen or href.rstrip("/") == base_url.rstrip("/"):
            continue
        seen.add(href)
        out.append(href)
        if len(out) >= limit:
            break
    return out


def _published_from_meta(meta: dict[str, Any]) -> datetime | None:
    raw = meta.get("date")
    if not raw:
        return None
    try:
        from dateutil import parser as dparser  # python-dateutil (trafilatura dependency)

        return _to_utc(dparser.parse(str(raw)))
    except Exception:  # noqa: BLE001
        return _parse_iso(str(raw))


# ---------------------------------------------------------------------------------------------
# the fetcher
# ---------------------------------------------------------------------------------------------
class Fetcher:
    def __init__(self, max_threads: int = 8, timeout: float = 25.0, cache_dir: Path | None = None,
                 cache_ttl_s: float = CACHE_TTL_S) -> None:
        self.max_threads = max(1, max_threads)
        self.timeout = timeout
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
        self.cache_ttl_s = cache_ttl_s
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,ja;q=0.5,fil;q=0.5",
                                      "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.5"})
        self._lock = threading.Lock()
        self.stats = {"fetched": 0, "cache_hits": 0, "failed": 0}

    # ---- public ----------------------------------------------------------------------------
    def fetch_many(self, urls: Iterable[str]) -> list[FetchResult]:
        urls = list(dict.fromkeys(u for u in urls if u))
        if not urls:
            return []
        with ThreadPoolExecutor(max_workers=min(self.max_threads, len(urls)), thread_name_prefix="fetch") as pool:
            return list(pool.map(self.fetch, urls))

    def fetch(self, url: str) -> FetchResult:
        cached = self._cache_get(url)
        if cached is not None:
            with self._lock:
                self.stats["cache_hits"] += 1
            cached.cache_hit = True
            return cached
        result = self._fetch_uncached(url)
        with self._lock:
            self.stats["fetched" if result.ok else "failed"] += 1
        if result.ok:
            self._cache_put(result)
        return result

    # ---- internals -------------------------------------------------------------------------
    def _fetch_uncached(self, url: str) -> FetchResult:
        try:
            resp = self._session.get(url, timeout=self.timeout, stream=True, allow_redirects=True)
        except requests.RequestException as exc:
            return FetchResult(url=url, ok=False, error=f"{type(exc).__name__}: {str(exc)[:160]}")
        status = resp.status_code
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        try:
            body = b""
            for chunk in resp.iter_content(chunk_size=65536):
                body += chunk
                if len(body) > MAX_BYTES:
                    break
        except requests.RequestException as exc:
            return FetchResult(url=url, ok=False, status=status, content_type=ctype, error=f"read error: {exc}")
        finally:
            resp.close()
        if status >= 400:
            return FetchResult(url=url, ok=False, status=status, content_type=ctype, error=f"HTTP {status}")
        encoding = resp.encoding or "utf-8"
        try:
            raw = body.decode(encoding, errors="replace")
        except LookupError:
            raw = body.decode("utf-8", errors="replace")
        return self._extract(url, status, ctype, raw)

    def _extract(self, url: str, status: int, ctype: str, raw: str) -> FetchResult:
        path = urlparse(url).path.lower()
        looks_json = ctype in ("application/json", "text/json") or path.endswith(".json")
        looks_text = ctype.startswith("text/plain") or path.endswith(".txt")
        if looks_json:
            try:
                data = json.loads(raw)
            except ValueError:
                return FetchResult(url=url, ok=False, status=status, content_type=ctype, error="invalid json")
            text, title, issued = render_jma_typhoon_json(data) if "jma.go.jp" in url else (render_generic_json(data), "JSON document", None)
            return FetchResult(url=url, ok=bool(text.strip()), status=status, content_type=ctype, text=text, title=title,
                               published_at=issued, extraction="json", error="" if text.strip() else "empty json")
        if looks_text:
            text = raw.strip()
            title = text.splitlines()[0].strip()[:120] if text else url
            # JTWC warnings carry a WMO header "WTPN32 PGTW 192100" = day 19, 21:00Z of the current month; keep it
            # on the page's own words, we do not guess a month, so published_at stays None for plain text.
            return FetchResult(url=url, ok=len(text) >= MIN_TEXT_CHARS, status=status, content_type=ctype, text=text,
                               title=title, extraction="text", error="" if len(text) >= MIN_TEXT_CHARS else "too short")
        # html (or unknown): trafilatura. A page counts as usable only if it holds real prose (sentences /
        # long lines), so a menu-only agency page or a "no bulletin issued" stub is dropped, not scored.
        text, meta, links = extract_html_isolated(raw, url)
        title = (meta.get("title") or "").strip() or _title_from_html(raw) or url
        ok = len(text.strip()) >= MIN_TEXT_CHARS and prose_chars(text) >= MIN_PROSE_CHARS
        return FetchResult(url=url, ok=ok, status=status, content_type=ctype or "text/html", text=text.strip(), title=title,
                           author=(meta.get("author") or None), published_at=_published_from_meta(meta),
                           extraction="trafilatura", links=links, error="" if ok else "no main text (no prose)",
                           site_name=(meta.get("sitename") or None))

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")

    def _cache_get(self, url: str) -> FetchResult | None:
        p = self._cache_path(url)
        try:
            if not p.is_file() or (time.time() - p.stat().st_mtime) > self.cache_ttl_s:
                return None
            return FetchResult.from_cache(json.loads(p.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 - a bad cache entry is just a miss
            log.debug("cache read failed for %s: %s", url, exc)
            return None

    def _cache_put(self, result: FetchResult) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            p = self._cache_path(result.url)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(result.to_cache(), ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, p)
        except Exception as exc:  # noqa: BLE001
            log.debug("cache write failed for %s: %s", result.url, exc)


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _title_from_html(html: str) -> str:
    m = _TITLE_RE.search(html)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


# ---------------------------------------------------------------------------------------------
# FetchResult -> ScrapedDocument
# ---------------------------------------------------------------------------------------------
def to_document(r: FetchResult, discovered_by: str, search_query: str = "", round_no: int = 0) -> ScrapedDocument:
    return ScrapedDocument(
        url=r.url,
        title=r.title or r.url,
        main_text=r.text,
        source_name=agency_for(r.url, r.site_name),
        published_at=r.published_at,
        author=r.author,
        fetched_at=r.fetched_at,
        metadata={
            "content_type": r.content_type,
            "extraction": r.extraction,
            "discovered_by": discovered_by,
            "search_query": search_query,
            "round": round_no,
            "http_status": r.status,
            "text_chars": len(r.text),
            "cache_hit": r.cache_hit,
            "links_found": len(r.links),
        },
    )
