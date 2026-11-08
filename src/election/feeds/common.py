"""Shared plumbing for the election-night results adapters.

HTTP: a polite, identifiable User-Agent, (connect, read) timeouts, bounded retries with backoff, per-host request
spacing, and conditional GETs (ETag / If-Modified-Since) backed by a small disk cache so an unchanged file costs the
server a 304. Bot challenges and WAF blocks are detected and raised as ``SourceBlocked``; they are never retried or
worked around. TLS verification is always on (``extra_ca`` only *adds* a verified intermediate a server forgot to
send).

Normalisation: party codes (DEM/REP/IND/LIB/GRN/OTH), candidate keys (lowercase surname, collision-safe), county
names to 5-digit FIPS, and the final assembly of the "Live results" dict documented in docs/ELECTION.md.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests

from .fips import COUNTIES

log = logging.getLogger("election.feeds")

REPO = Path(__file__).resolve().parents[3]
USER_AGENT = "election-results-desk/0.1 (independent livestream)"
TIMEOUT = (float(os.environ.get("ELECTION_CONNECT_TIMEOUT_S", "10")),
           float(os.environ.get("ELECTION_READ_TIMEOUT_S", "60")))
RETRIES = int(os.environ.get("ELECTION_HTTP_RETRIES", "2"))
MIN_HOST_INTERVAL_S = float(os.environ.get("ELECTION_MIN_HOST_INTERVAL_S", "2.0"))
CACHE_DIR = Path(os.environ.get("ELECTION_CACHE_DIR", REPO / "output" / "election" / "cache" / "http"))
RAW_DIR = os.environ.get("ELECTION_RAW_DIR")          # when set, every downloaded body is also saved here
CERT_DIR = Path(__file__).resolve().parent / "certs"


# ---------------------------------------------------------------- errors

class FeedError(RuntimeError):
    """Base class: the adapter could not produce a result."""


class SourceBlocked(FeedError):
    """The official server answered with a bot challenge / WAF block, or is unreachable from here."""


class NotPublished(FeedError):
    """The 2026 general-election file is not (yet) at the expected place, or the file there is another election."""


class TestData(FeedError):
    """The source marks its file as test data (pre-election test / zero file)."""


class ParseError(FeedError):
    """The file was fetched but its structure is not what the adapter expects."""


# ---------------------------------------------------------------- HTTP

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8"})
    return s


@dataclass
class Fetched:
    url: str
    status: int
    content: bytes
    headers: dict[str, str] = field(default_factory=dict)
    not_modified: bool = False           # True when the server answered 304 and ``content`` came from the cache

    @property
    def text(self) -> str:
        enc = "utf-8"
        ctype = self.headers.get("content-type", "")
        m = re.search(r"charset=([\w-]+)", ctype, re.I)
        if m:
            enc = m.group(1)
        try:
            return self.content.decode(enc, errors="replace").lstrip("﻿")
        except LookupError:
            return self.content.decode("utf-8", errors="replace").lstrip("﻿")

    def json(self) -> Any:
        try:
            return json.loads(self.text)
        except ValueError as e:
            raise ParseError(f"{self.url}: not JSON ({e})") from e

    @property
    def last_modified(self) -> str | None:
        """Last-Modified header as ISO-8601 UTC, if the server sent one."""
        lm = self.headers.get("last-modified")
        if not lm:
            return None
        try:
            return iso(email.utils.parsedate_to_datetime(lm))
        except (TypeError, ValueError):
            return None


_host_lock = threading.Lock()
_host_last: dict[str, float] = {}
_bundle_cache: dict[str, str] = {}


def _space_host(host: str) -> None:
    """Keep at least MIN_HOST_INTERVAL_S between two requests to the same host (shared by all adapters)."""
    with _host_lock:
        wait = _host_last.get(host, 0.0) + MIN_HOST_INTERVAL_S - time.monotonic()
        _host_last[host] = time.monotonic() + max(wait, 0.0)
    if wait > 0:
        time.sleep(wait)


def _ca_bundle(extra_ca: str) -> str:
    """certifi's bundle plus one extra (already verified) intermediate certificate from ``certs/``."""
    if extra_ca in _bundle_cache:
        return _bundle_cache[extra_ca]
    import certifi
    pem = (CERT_DIR / extra_ca).read_text(encoding="ascii")
    out = CACHE_DIR.parent / "ca" / f"bundle-{hashlib.sha1(pem.encode()).hexdigest()[:12]}.pem"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.is_file():
        write_atomic_bytes(out, Path(certifi.where()).read_bytes() + b"\n" + pem.encode("ascii"))
    _bundle_cache[extra_ca] = str(out)
    return str(out)


_CHALLENGE_MARKERS = (b"Just a moment...", b"cf_chl_opt", b"challenge-platform", b"IM_UNDER_ATTACK",
                      b"Request blocked.", b"Attention Required! | Cloudflare", b"Access Denied")


def looks_blocked(status: int, headers: dict[str, str], body: bytes) -> bool:
    """A bot challenge / WAF page rather than the file we asked for."""
    if status not in (401, 403, 429, 503):
        return False
    head = body[:20000]
    server = headers.get("server", "").lower()
    return any(m in head for m in _CHALLENGE_MARKERS) or "cloudflare" in server or "cloudfront" in server


def _cache_paths(url: str) -> tuple[Path, Path]:
    h = hashlib.sha1(url.encode()).hexdigest()
    return CACHE_DIR / f"{h}.meta.json", CACHE_DIR / f"{h}.body"


def _save_raw(url: str, body: bytes) -> None:
    if not RAW_DIR:
        return
    try:
        p = urlsplit(url)
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", (p.netloc + p.path + ("_" + p.query if p.query else "")))[-150:]
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        d = Path(RAW_DIR)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{stamp}_{name}").write_bytes(body)
    except OSError as e:          # never fail a fetch because the raw copy could not be written
        log.warning("raw copy of %s not saved: %s", url, e)


def get(session: requests.Session, url: str, *, conditional: bool = True, extra_ca: str | None = None,
        timeout: tuple[float, float] | None = None, retries: int | None = None, params: dict | None = None,
        allow_404: bool = False) -> Fetched:
    """GET ``url`` politely. Raises SourceBlocked (challenge/WAF/unreachable), NotPublished (404) or FeedError.

    With ``conditional`` the previous ETag / Last-Modified for this URL is sent; a 304 returns the cached body with
    ``not_modified=True``.
    """
    if params:
        url = requests.Request("GET", url, params=params).prepare().url
    host = urlsplit(url).netloc
    meta_p, body_p = _cache_paths(url)
    headers: dict[str, str] = {}
    cached_meta: dict[str, Any] | None = None
    if conditional and meta_p.is_file() and body_p.is_file():
        try:
            cached_meta = json.loads(meta_p.read_text(encoding="utf-8"))
            if cached_meta.get("etag"):
                headers["If-None-Match"] = cached_meta["etag"]
            if cached_meta.get("last_modified"):
                headers["If-Modified-Since"] = cached_meta["last_modified"]
        except (OSError, ValueError):
            cached_meta = None
    verify: bool | str = _ca_bundle(extra_ca) if extra_ca else True
    retries = RETRIES if retries is None else retries
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        _space_host(host)
        try:
            r = session.get(url, headers=headers, timeout=timeout or TIMEOUT, verify=verify)
        except requests.exceptions.SSLError as e:
            raise SourceBlocked(f"{url}: TLS verification failed ({e})") from e
        except (requests.ConnectionError, requests.Timeout) as e:
            last_err = e
            time.sleep(min(2.0 * (attempt + 1), 10.0))
            continue
        hdrs = {k.lower(): v for k, v in r.headers.items()}
        if r.status_code == 304 and cached_meta is not None:
            return Fetched(url, 304, body_p.read_bytes(), cached_meta.get("headers", {}), not_modified=True)
        if looks_blocked(r.status_code, hdrs, r.content):
            raise SourceBlocked(f"{url}: HTTP {r.status_code} bot challenge / WAF block "
                                f"(server={hdrs.get('server', '?')}); not retried, not bypassed")
        if r.status_code == 404:
            if allow_404:
                return Fetched(url, 404, r.content, hdrs)
            raise NotPublished(f"{url}: 404")
        if r.status_code == 429 or r.status_code >= 500:
            last_err = FeedError(f"{url}: HTTP {r.status_code}")
            ra = hdrs.get("retry-after", "")
            time.sleep(min(float(ra) if ra.isdigit() else 3.0 * (attempt + 1), 30.0))
            continue
        if r.status_code >= 400:
            raise FeedError(f"{url}: HTTP {r.status_code}")
        body = r.content
        _save_raw(url, body)
        if conditional and (hdrs.get("etag") or hdrs.get("last-modified")):
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                keep = {k: hdrs[k] for k in ("content-type", "last-modified", "etag", "date") if k in hdrs}
                write_atomic_bytes(body_p, body)
                write_atomic_bytes(meta_p, json.dumps({"url": url, "etag": hdrs.get("etag"),
                                                       "last_modified": hdrs.get("last-modified"),
                                                       "headers": keep}).encode())
            except OSError as e:
                log.warning("cache write failed for %s: %s", url, e)
        return Fetched(url, r.status_code, body, hdrs)
    if isinstance(last_err, (requests.ConnectionError, requests.Timeout)):
        raise SourceBlocked(f"{url}: unreachable after {retries + 1} attempts ({last_err})")
    raise FeedError(f"{url}: {last_err}")


# ---------------------------------------------------------------- time

def iso(t: dt.datetime) -> str:
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utcnow() -> str:
    return iso(dt.datetime.now(dt.timezone.utc))


def local_to_iso(text: str, fmts: Iterable[str], tz: str) -> str | None:
    """Parse a local wall-clock timestamp in one of ``fmts`` (zone ``tz``) to ISO UTC; None if nothing matches."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    for f in fmts:
        try:
            return iso(dt.datetime.strptime(text, f).replace(tzinfo=ZoneInfo(tz)))
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- parties, names, keys

_PARTY_WORDS = [
    (r"^(DEM|D|DEMOCRAT|DEMOCRATIC|DEMOCRATIC PARTY|DFL)$", "DEM"),
    (r"^(REP|R|GOP|REPUBLICAN|REPUBLICAN PARTY)$", "REP"),
    (r"^(LIB|L|LBT|LPF|LIBERTARIAN|LIBERTARIAN PARTY)$", "LIB"),
    (r"^(GRN|G|GRE|GREEN|GREEN PARTY|GREEN INDEPENDENT)$", "GRN"),
    (r"^(IND|I|INDEP|INDEPENDENT|NPA|NON|NONPARTISAN|NONPARTY|NONPRTYCAN|NONPARTY CANDIDATE|UND|UNDECLARED|"
     r"UNENROLLED|U|NP|NO PARTY|INDEPENDENT - NO BALLOT DESIGNATION|NO PARTY AFFILIATION)$", "IND"),
]


def norm_party(raw: str | None) -> str:
    """Map a source party label to DEM/REP/IND/LIB/GRN/OTH (OTH for anything else, including blanks)."""
    p = re.sub(r"\s+", " ", (raw or "").strip().upper().replace(".", ""))
    for pat, code in _PARTY_WORDS:
        if re.match(pat, p):
            return code
    return "OTH"


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def ascii_slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def split_name(name: str) -> tuple[str, str, str]:
    """(first, last, suffix) from 'First M. Last Jr.' or 'Last, First M. Jr.' (nicknames in quotes dropped)."""
    n = re.sub(r"\([^)]*\)", " ", name)                        # "(I)" incumbent marks
    n = re.sub(r"[\"“”][^\"“”]*[\"“”]", " ", n)   # "Kitty"
    n = re.sub(r"\s+", " ", n).strip(" ,")
    suffix = ""
    if "," in n:
        last, rest = [x.strip() for x in n.split(",", 1)]
        toks = rest.split()
        if toks and ascii_slug(toks[-1]) in _SUFFIXES:
            suffix = ascii_slug(toks.pop())
        if ascii_slug(last) in _SUFFIXES:           # "Smith Jr., John" is rare; keep it simple
            suffix, last = ascii_slug(last), ""
        return " ".join(toks), last, suffix
    toks = n.split()
    while toks and ascii_slug(toks[-1]) in _SUFFIXES:
        suffix = ascii_slug(toks.pop())
    if not toks:
        return "", n, suffix
    return " ".join(toks[:-1]), toks[-1], suffix


def assign_keys(cands: list[dict], overrides: dict[str, str] | None = None) -> None:
    """Set ``c["key"]`` = lowercase ASCII surname, made unique in ballot order.

    Each dict needs ``name`` and may carry ``last`` (surname from a structured source) and ``order``. A clash gets the
    generational suffix (``sullivan_jr``) or else the first given name (``smith_john``); ``overrides`` maps a source
    name exactly to a key. Write-in aggregates keep their preset key.
    """
    overrides = overrides or {}
    used: set[str] = set()
    for c in sorted(cands, key=lambda c: c.get("order", 0)):
        if c.get("key"):
            used.add(c["key"])
            continue
        if c["name"] in overrides:
            c["key"] = overrides[c["name"]]
            used.add(c["key"])
            continue
        first, last, suffix = split_name(c["name"])
        last = c.get("last") or last
        base = ascii_slug(last) or ascii_slug(c["name"]) or "cand"
        key = base
        if key in used:
            alt = [f"{base}_{suffix}"] if suffix else []
            alt += [f"{base}_{ascii_slug(first.split()[0])}"] if first.split() else []
            alt += [f"{base}_{i}" for i in range(2, 50)]
            key = next(k for k in alt if k not in used)
        c["key"] = key
        used.add(key)


def display_name(name: str) -> str:
    """'SULLIVAN, DAN S.' / 'JOHN CORNYN (I)' -> 'Dan S. Sullivan' / 'John Cornyn' (title-cased only if all caps)."""
    n = re.sub(r"\s*\((I|i)\)\s*$", "", name).strip()
    if "," in n:
        last, rest = [x.strip() for x in n.split(",", 1)]
        toks = rest.split()
        suffix = toks.pop() if toks and ascii_slug(toks[-1]) in _SUFFIXES else ""
        n = " ".join(toks + [last] + ([suffix] if suffix else []))
    if n.isupper():
        n = " ".join(_title_word(w) for w in n.split())
    return re.sub(r"\s+", " ", n).strip()


def _title_word(w: str) -> str:
    if ascii_slug(w) in {"ii", "iii", "iv"}:
        return w.upper()
    t = w.capitalize()
    t = re.sub(r"^(Mc)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    t = re.sub(r"^(O')([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    t = re.sub(r"([\"“])([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    return re.sub(r"-([a-z])", lambda m: "-" + m.group(1).upper(), t)


# ---------------------------------------------------------------- counties

def _county_norm(name: str) -> str:
    n = name.upper().replace("SAINT ", "ST ").replace("STE. ", "STE ")
    n = re.sub(r"\b(COUNTY|PARISH)\b", "", n)
    return re.sub(r"[^A-Z]", "", n)


_county_index: dict[str, dict[str, str]] = {}


def county_fips(state: str, name: str) -> str:
    """5-digit FIPS for a county name in ``state`` (case, spacing, 'County' and 'St./Saint' insensitive)."""
    idx = _county_index.get(state)
    if idx is None:
        idx = {_county_norm(n): f for f, n in COUNTIES[state].items()}
        _county_index[state] = idx
    try:
        return idx[_county_norm(name)]
    except KeyError:
        raise ParseError(f"{state}: unknown county name {name!r}") from None


def county_name(fips: str, state: str) -> str:
    return COUNTIES[state][fips]


# ---------------------------------------------------------------- result assembly

WRITEIN_KEY = "writein"


def to_int(x: Any) -> int:
    if x is None:
        return 0
    if isinstance(x, (int, float)):
        return int(x)
    s = re.sub(r"[,\s]", "", str(x))
    if s in ("", "-", "--"):
        return 0
    try:
        return int(float(s))
    except ValueError:
        raise ParseError(f"not a number: {x!r}") from None


def precincts(reporting: Any, total: Any) -> dict[str, int] | None:
    if reporting is None or total is None:
        return None
    return {"reporting": to_int(reporting), "total": to_int(total)}


def build_result(*, state: str, unit_type: str, source: str, source_url: str, source_updated_at: str | None,
                 candidates: list[dict], units: list[dict], statewide_votes: dict[str, int] | None = None,
                 statewide_precincts: dict[str, int] | None = None, extra: dict[str, Any] | None = None) -> dict:
    """Assemble the docs/ELECTION.md "Live results" dict.

    ``candidates``: dicts with key, name, party (already normalised) and optional ``order`` (ballot order).
    ``units``: dicts with id, name, votes {key: n}, precincts (dict or None). Totals are recomputed from the votes.
    ``statewide_votes``: official statewide totals when the source publishes them separately (else summed from units).
    ``extra``: additional top-level keys explicitly allowed by the spec (Maine ``towns``).
    """
    keys = [c["key"] for c in candidates]
    if len(set(keys)) != len(keys):
        raise ParseError(f"{state}: duplicate candidate keys {keys}")
    out_units = []
    sums = {k: 0 for k in keys}
    for u in units:
        votes = {k: to_int(u["votes"].get(k, 0)) for k in keys}
        for k in votes:
            sums[k] += votes[k]
        out_units.append({"id": u["id"], "name": u["name"], "votes": votes, "total": sum(votes.values()),
                          "precincts": u.get("precincts")})
    out_units.sort(key=lambda u: u["id"])
    sw = {k: to_int((statewide_votes or sums).get(k, 0)) for k in keys}
    order = {c["key"]: c.get("order", i) for i, c in enumerate(candidates)}
    cand_out = [{"key": c["key"], "name": c["name"], "party": c["party"], "votes": sw[c["key"]]} for c in candidates]
    cand_out.sort(key=lambda c: (-c["votes"], order[c["key"]]))
    if statewide_precincts is None:
        ps = [u["precincts"] for u in out_units if u.get("precincts")]
        statewide_precincts = ({"reporting": sum(p["reporting"] for p in ps), "total": sum(p["total"] for p in ps)}
                               if ps and len(ps) == len(out_units) else None)
    res = {
        "state": state, "race": "senate", "unit_type": unit_type,
        "source": source, "source_url": source_url,
        "fetched_at": utcnow(), "source_updated_at": source_updated_at,
        "candidates": cand_out,
        "total_votes": sum(sw.values()),
        "precincts": statewide_precincts,
        "units": out_units,
    }
    if extra:
        res.update(extra)
    validate(res)
    return res


SCHEMA_KEYS = ["state", "race", "unit_type", "source", "source_url", "fetched_at", "source_updated_at",
               "candidates", "total_votes", "precincts", "units"]
PARTIES = {"DEM", "REP", "IND", "LIB", "GRN", "OTH"}


def validate(d: dict) -> None:
    """Raise ParseError if ``d`` does not match the Live results schema (extra keys allowed: towns)."""
    missing = [k for k in SCHEMA_KEYS if k not in d]
    if missing:
        raise ParseError(f"missing keys {missing}")
    unknown = set(d) - set(SCHEMA_KEYS) - {"towns"}
    if unknown:
        raise ParseError(f"unexpected keys {sorted(unknown)}")
    if d["race"] != "senate" or d["unit_type"] not in ("county", "house_district"):
        raise ParseError("race/unit_type")
    keys = set()
    for c in d["candidates"]:
        if set(c) != {"key", "name", "party", "votes"} or c["party"] not in PARTIES:
            raise ParseError(f"bad candidate {c}")
        if not re.fullmatch(r"[a-z0-9_]+", c["key"]):
            raise ParseError(f"bad key {c['key']!r}")
        keys.add(c["key"])
    if d["total_votes"] != sum(c["votes"] for c in d["candidates"]):
        raise ParseError("total_votes != sum of candidate votes")
    p = d["precincts"]
    if p is not None and (set(p) != {"reporting", "total"} or min(p["reporting"], p["total"]) < 0):
        raise ParseError("precincts")
    for u in d["units"]:
        if set(u) != {"id", "name", "votes", "total", "precincts"} or set(u["votes"]) != keys:
            raise ParseError(f"bad unit {u.get('id')}")
        if u["total"] != sum(u["votes"].values()):
            raise ParseError(f"unit total {u['id']}")
    ids = [u["id"] for u in d["units"]]
    if len(set(ids)) != len(ids):
        raise ParseError("duplicate unit ids")
    pat = r"AK-HD\d\d" if d["unit_type"] == "house_district" else r"\d{5}"
    bad = [i for i in ids if not re.fullmatch(pat, i)]
    if bad:
        raise ParseError(f"bad unit ids {bad[:5]}")


# ---------------------------------------------------------------- files

def write_atomic_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)          # mkstemp creates 0600; the web server must be able to read it
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_json_atomic(path: Path, obj: Any) -> None:
    write_atomic_bytes(Path(path), (json.dumps(obj, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default
