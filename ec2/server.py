#!/usr/bin/env python3
"""EC2 side of the broadcast: one HTTPS server for the ICRN uploader and the public website.

Runs on the t3.micro with Python 3.14's standard library plus boto3 (the only non-stdlib
import). Everything is configured through the environment (see ec2/env.example):

    API_TOKEN      bearer token ICRN must send on /api/v1/* (constant-time compared)
    BUCKET, REGION S3 bucket the instance role may ListBucket / GetObject / PutObject on
    DATA_DIR       where packages are kept locally (default /home/ubuntu/weather-livestream-data)
    WEB_DIR        the deployed html folder (champi-desk.html lives here)
    BIND, PORT     0.0.0.0:8443
    CERT, KEY      PEM files for TLS
    KEEP_PACKAGES  newest packages kept locally besides the one on air (default 3)
    PRESIGN_TTL    lifetime of presigned PUT urls in seconds (default 900)

Flow for one package (see src/broadcast/package.py for the manifest):

    ICRN  POST /api/v1/uploads                 -> presigned PUT urls under packages/<id>/
    ICRN  PUT  <presigned urls>                -> files land in S3
    ICRN  POST /api/v1/packages/<id>/complete  -> this server downloads + verifies the package,
                                                  then atomically points current.json at it
    site  GET  /live/current.json              -> the manifest on air
    site  GET  /live/<id>/<scene>.wav          -> audio (with Range support)
    site  POST /live/playback                  -> heartbeat: which package/scene is playing

A failed `complete` never touches the package currently on air: the partial folder is removed
and the previous current.json stays. After an activation, packages older than the newest
KEEP_PACKAGES (never the one on air, never the one the site reports playing) are retired:
removed locally and, if the role allows it, deleted from S3 (the dev role has no DeleteObject,
so that part is tolerated and reported as s3_delete_denied).

Streams. Several broadcasts can run side by side; each is a stream with its own id ([a-z0-9-], up to 32
characters), its own packages, on-air package, retention and desk.json:

    stream "default"   DATA_DIR/{state.json,current.json,packages/,desk.json}   S3 packages/<id>/
    stream "<sid>"     DATA_DIR/streams/<sid>/...  (same layout)                 S3 streams/<sid>/packages/<id>/

    page      GET  /s/<sid>/                         the website for that stream (its relative live/ urls
                                                      resolve under /s/<sid>/live/)
    live      GET  /s/<sid>/live/current.json, /s/<sid>/live/desk.json, /s/<sid>/live/<id>/<file>
              POST /s/<sid>/live/playback
    api       /api/v1/streams/<sid>/uploads, .../packages/<id>/complete, .../retire, .../desk, .../status
    listing   GET  /streams.json (public summary), GET /api/v1/streams (authed, full status)

The unprefixed routes (/, /live/*, /api/v1/*) are stream "default", so a single-stream setup works as
before. A stream without a desk.json of its own is served the default stream's (one desk updater can feed
every stream about the same storm). A stream exists once a package or desk has been published to it.

State is one json file per stream, guarded by one lock; the server is single-process.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import ssl
import sys
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

API_TOKEN = os.environ.get("API_TOKEN", "")
BUCKET = os.environ.get("BUCKET", "weather-livestream-716747745410-dev")
REGION = os.environ.get("REGION", "us-east-1")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/home/ubuntu/weather-livestream-data"))
WEB_DIR = Path(os.environ.get("WEB_DIR", "/home/ubuntu/weather-livestream/html"))
BIND = os.environ.get("BIND", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8443"))
CERT = os.environ.get("CERT", "/etc/weather-livestream/tls/server.crt")
KEY = os.environ.get("KEY", "/etc/weather-livestream/tls/server.key")
KEEP_PACKAGES = int(os.environ.get("KEEP_PACKAGES", "3"))
PRESIGN_TTL = int(os.environ.get("PRESIGN_TTL", "900"))
NO_TLS = os.environ.get("NO_TLS", "0") == "1"          # plain http, for local tests only

DEFAULT_STREAM = "default"
STREAM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
MAX_STREAMS = int(os.environ.get("MAX_STREAMS", "16"))
PACKAGE_ID_RE = re.compile(r"^pkg-[0-9TZ]+-[0-9a-f]{6}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_JSON_BYTES = 1 << 20              # request bodies on the api
MAX_DESK_BYTES = 2 << 20              # desk.json (live numbers for the page) may be bigger
DESK_KEEP = int(os.environ.get("DESK_KEEP", "20"))
DESK_REQUIRED = ("generated_at", "storm", "center", "forecast", "agencies")
MAX_PACKAGE_BYTES = 200 * (1 << 20)   # whole package
ALLOWED_UPLOAD_TYPES = {"application/json", "audio/wav", "audio/x-wav", "audio/wave", "text/plain"}
CONTENT_TYPES = {".wav": "audio/wav", ".json": "application/json", ".html": "text/html; charset=utf-8",
                 ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml",
                 ".txt": "text/plain; charset=utf-8", ".ico": "image/x-icon"}

_state_lock = threading.Lock()
_log_lock = threading.Lock()
_s3 = None


def log(msg: str) -> None:
    with _log_lock:
        sys.stdout.write(f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}\n")
        sys.stdout.flush()


def s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=REGION, config=BotoConfig(signature_version="s3v4",
                                                                       retries={"max_attempts": 4}))
    return _s3


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Streams (one namespace per broadcast)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Stream:
    sid: str
    root: Path        # local folder: state.json, current.json, packages/, desk.json, desk-history/
    prefix: str       # S3 key prefix of its packages

    @property
    def packages_dir(self) -> Path:
        return self.root / "packages"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @property
    def current_path(self) -> Path:
        return self.root / "current.json"

    @property
    def desk_path(self) -> Path:
        return self.root / "desk.json"

    @property
    def desk_history_dir(self) -> Path:
        return self.root / "desk-history"

    def exists(self) -> bool:
        return self.sid == DEFAULT_STREAM or self.root.is_dir()


def get_stream(sid: str | None) -> Stream | None:
    """The stream for an id (None or "default": the legacy single-stream layout); None if the id is invalid."""
    if not sid or sid == DEFAULT_STREAM:
        return Stream(DEFAULT_STREAM, DATA_DIR, "packages")
    if not STREAM_ID_RE.match(sid):
        return None
    return Stream(sid, DATA_DIR / "streams" / sid, f"streams/{sid}/packages")


def all_streams() -> list[Stream]:
    out = [get_stream(DEFAULT_STREAM)]
    sdir = DATA_DIR / "streams"
    if sdir.is_dir():
        out += [get_stream(d.name) for d in sorted(sdir.iterdir()) if d.is_dir() and STREAM_ID_RE.match(d.name)]
    return out


def can_create(stm: Stream) -> bool:
    return stm.exists() or len(all_streams()) - 1 < MAX_STREAMS


# ─────────────────────────────────────────────────────────────────────────────
# State (one json file per stream)
# ─────────────────────────────────────────────────────────────────────────────

def _default_state() -> dict:
    return {"current": None, "playing": None, "retired": [], "s3_delete_denied": False, "activations": []}


def load_state(stm: Stream) -> dict:
    try:
        st = json.loads(stm.state_path.read_text(encoding="utf-8"))
        base = _default_state()
        base.update(st)
        return base
    except (OSError, ValueError):
        return _default_state()


def save_state(stm: Stream, st: dict) -> None:
    write_json_atomic(stm.state_path, st)


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def set_current(stm: Stream, st: dict, package_id: str | None) -> None:
    st["current"] = None if package_id is None else {"package_id": package_id, "activated_at": now_iso()}
    st["activations"] = (st.get("activations") or [])[-50:] + ([package_id] if package_id else [])
    # current.json is the small file other tools may read directly
    write_json_atomic(stm.current_path, st["current"] or {})


# ─────────────────────────────────────────────────────────────────────────────
# Packages on disk
# ─────────────────────────────────────────────────────────────────────────────

def package_dir(stm: Stream, package_id: str) -> Path:
    return stm.packages_dir / package_id


def read_manifest(stm: Stream, package_id: str) -> dict | None:
    try:
        return json.loads((package_dir(stm, package_id) / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def local_packages(stm: Stream) -> list[dict]:
    """Packages on disk, newest first (by manifest created_at, then folder mtime)."""
    out = []
    if not stm.packages_dir.is_dir():
        return out
    for d in stm.packages_dir.iterdir():
        if not d.is_dir() or not PACKAGE_ID_RE.match(d.name):
            continue
        m = read_manifest(stm, d.name)
        out.append({"package_id": d.name, "created_at": (m or {}).get("created_at", ""),
                    "mtime": d.stat().st_mtime, "complete": m is not None,
                    "scenes": len((m or {}).get("scenes", [])), "is_test": bool((m or {}).get("is_test"))})
    out.sort(key=lambda p: (p["created_at"], p["mtime"]), reverse=True)
    return out


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_manifest(manifest: dict, pdir: Path) -> list[str]:
    """The rules from src/broadcast/package.validate_manifest, kept in step by hand."""
    problems: list[str] = []
    if manifest.get("schema_version") not in (1, 2):
        problems.append("unsupported schema_version")
    pid = manifest.get("package_id")
    if not isinstance(pid, str) or not pid:
        problems.append("missing package_id")
    elif pid != pdir.name:
        problems.append("package_id does not match the upload prefix")
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        problems.append("no scenes")
        return problems
    ids = set()
    for s in scenes:
        if not isinstance(s, dict):
            problems.append("scene entry is not an object")
            continue
        sid = s.get("scene_id")
        if not sid or sid in ids:
            problems.append(f"bad or duplicate scene_id {sid!r}")
        ids.add(sid)
        a = s.get("audio") or {}
        for k in ("key", "duration_seconds", "sample_rate", "channels", "format"):
            if k not in a:
                problems.append(f"scene {sid}: audio.{k} missing")
        if not (s.get("script") or {}).get("llm_output"):
            problems.append(f"scene {sid}: script.llm_output missing")
        # the file the site will play: audio.path (v2) or the basename of audio.key (v1)
        name = a.get("path") or os.path.basename(a.get("key", ""))
        if not name or not SAFE_NAME_RE.match(name):
            problems.append(f"scene {sid}: audio file name {name!r} not allowed")
            continue
        p = pdir / name
        if not p.is_file():
            problems.append(f"scene {sid}: audio file {name} missing")
            continue
        if a.get("sha256") and sha256_of(p) != a["sha256"]:
            problems.append(f"scene {sid}: audio sha256 mismatch")
        try:
            with wave.open(str(p), "rb") as w:
                frames, rate, ch = w.getnframes(), w.getframerate(), w.getnchannels()
            if rate != int(a.get("sample_rate", rate)) or ch != int(a.get("channels", ch)):
                problems.append(f"scene {sid}: wav header disagrees with the manifest")
            if abs(frames / rate - float(a.get("duration_seconds", frames / rate))) > 0.05:
                problems.append(f"scene {sid}: wav duration disagrees with the manifest")
        except (wave.Error, EOFError, OSError, ValueError) as e:
            problems.append(f"scene {sid}: wav not readable ({e})")
    for sid in manifest.get("playlist", []) or []:
        if sid not in ids:
            problems.append(f"playlist references unknown scene {sid!r}")
    return problems


def download_package(stm: Stream, package_id: str, manifest_key: str) -> tuple[dict, list[str]]:
    """Fetch manifest + files into a fresh folder; return (manifest, problems). Folder is left for the caller."""
    pdir = package_dir(stm, package_id)
    if pdir.exists():
        shutil.rmtree(pdir)
    pdir.mkdir(parents=True)
    expected_key = f"{stm.prefix}/{package_id}/manifest.json"
    if manifest_key != expected_key:
        return {}, [f"manifest_key must be {expected_key}"]
    try:
        s3().download_file(BUCKET, manifest_key, str(pdir / "manifest.json"))
        manifest = json.loads((pdir / "manifest.json").read_text(encoding="utf-8"))
    except (ClientError, OSError, ValueError) as e:
        return {}, [f"manifest download failed: {e}"]
    files = manifest.get("files")
    if not isinstance(files, list):
        # v1 manifests list no files: derive them from the scenes' audio keys
        files = [{"key": s["audio"]["key"], "path": os.path.basename(s["audio"]["key"])}
                 for s in manifest.get("scenes", []) if isinstance(s, dict) and (s.get("audio") or {}).get("key")]
    problems: list[str] = []
    total = 0
    for f in files:
        # the key is derived from the file name inside this stream's prefix; a key in the manifest is never trusted
        name = f.get("path") or os.path.basename(f.get("key", ""))
        if not SAFE_NAME_RE.match(name or ""):
            problems.append(f"file {name!r} has a bad name")
            continue
        key = f"{stm.prefix}/{package_id}/{name}"
        if name == "manifest.json":
            continue
        dst = pdir / name
        try:
            s3().download_file(BUCKET, key, str(dst))
        except (ClientError, OSError) as e:
            problems.append(f"download failed for {key}: {e}")
            continue
        size = dst.stat().st_size
        total += size
        if total > MAX_PACKAGE_BYTES:
            problems.append("package exceeds the size limit")
            break
        if "size" in f and int(f["size"]) != size:
            problems.append(f"{name}: size {size} != manifest {f['size']}")
        if f.get("sha256") and sha256_of(dst) != f["sha256"]:
            problems.append(f"{name}: sha256 mismatch")
    return manifest, problems


def s3_delete_prefix(prefix: str) -> tuple[bool, str]:
    """Delete every object under prefix. Returns (deleted?, note)."""
    try:
        keys = []
        token = None
        while True:
            kw = {"Bucket": BUCKET, "Prefix": prefix}
            if token:
                kw["ContinuationToken"] = token
            r = s3().list_objects_v2(**kw)
            keys += [{"Key": o["Key"]} for o in r.get("Contents", [])]
            token = r.get("NextContinuationToken")
            if not token:
                break
        for i in range(0, len(keys), 1000):
            s3().delete_objects(Bucket=BUCKET, Delete={"Objects": keys[i:i + 1000], "Quiet": True})
        return True, f"deleted {len(keys)} object(s)"
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        return False, code or str(e)


def prune_packages(stm: Stream, st: dict) -> list[str]:
    """Retire everything but the KEEP_PACKAGES newest (and never the current / playing package)."""
    protected = set()
    if st.get("current"):
        protected.add(st["current"]["package_id"])
    if st.get("playing"):
        protected.add(st["playing"].get("package_id"))
    keep = [p["package_id"] for p in local_packages(stm)][:max(1, KEEP_PACKAGES)]
    protected.update(keep)
    retired = []
    for p in local_packages(stm):
        pid = p["package_id"]
        if pid in protected:
            continue
        shutil.rmtree(package_dir(stm, pid), ignore_errors=True)
        ok, note = s3_delete_prefix(f"{stm.prefix}/{pid}/")
        if not ok:
            if not st.get("s3_delete_denied"):
                log(f"S3 delete of {pid} denied ({note}); the instance role lacks s3:DeleteObject")
            st["s3_delete_denied"] = True
        retired.append(pid)
        log(f"[{stm.sid}] retired package {pid} (s3: {note})")
    st["retired"] = (st.get("retired") or [])[-200:] + retired
    return retired


# ─────────────────────────────────────────────────────────────────────────────
# HTTP handler
# ─────────────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    server_version = "weather-livestream/1.0"
    protocol_version = "HTTP/1.1"

    # ---- plumbing ----------------------------------------------------------------------
    def log_message(self, fmt, *args):  # one line per request, written in finish_request
        pass

    def _send_json(self, status: int, data, extra: dict | None = None) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_JSON_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(n) if n else b""
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("json object expected")
        return data

    def _authed(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if not API_TOKEN or not auth.startswith("Bearer "):
            return False
        return hmac.compare_digest(auth[7:].strip(), API_TOKEN)

    def _drain(self) -> None:
        n = int(self.headers.get("Content-Length") or 0)
        if 0 < n <= MAX_JSON_BYTES:
            self.rfile.read(n)

    def handle_one_request(self):
        t0 = time.perf_counter()
        self._status = "-"
        try:
            super().handle_one_request()
        finally:
            if getattr(self, "raw_requestline", b""):
                log(f"{self.client_address[0]} {self.command} {self.path} {self._status} {1000 * (time.perf_counter() - t0):.0f}ms")

    def send_response(self, code, message=None):
        self._status = code
        super().send_response(code, message)

    # ---- routing -----------------------------------------------------------------------
    def _route(self, path: str) -> tuple[Stream | None, str]:
        """(stream, path within it): /s/<sid>/... and /api/v1/streams/<sid>/... name a stream; anything else is
        the default stream. An invalid stream id gives (None, path)."""
        m = re.match(r"^/s/([^/]+)(/.*)?$", path)
        if m:
            return get_stream(m.group(1)), m.group(2) or ""
        m = re.match(r"^/api/v1/streams/([^/]+)(/.*)$", path)
        if m:
            return get_stream(m.group(1)), "/api/v1" + m.group(2)
        return get_stream(DEFAULT_STREAM), path

    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path
        try:
            if path == "/healthz":
                return self._send_json(200, {"ok": True, "time": now_iso()})
            if path == "/streams.json":
                return self._send_json(200, {"ok": True, "streams": self._streams_summary(full=False)})
            if path == "/api/v1/streams":
                if not self._authed():
                    return self._send_json(401, {"ok": False, "error": "unauthorized"})
                return self._send_json(200, {"ok": True, "streams": self._streams_summary(full=True)})
            stm, path = self._route(path)
            if stm is None:
                return self._send_json(404, {"ok": False, "error": "bad stream id"})
            if path == "" and url.path.startswith("/s/"):        # /s/<sid> -> /s/<sid>/ (relative urls need the slash)
                self.send_response(301)
                self.send_header("Location", url.path + "/" + (f"?{url.query}" if url.query else ""))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path in ("/", "/index.html", "/champi-desk.html"):
                return self._send_file(WEB_DIR / "champi-desk.html", cache="no-cache")
            if path == "/live/current.json":
                return self._live_current(stm)
            if path == "/live/desk.json":
                return self._live_desk(stm)
            if path.startswith("/live/"):
                return self._live_file(stm, path[len("/live/"):])
            if path == "/api/v1/status":
                if not self._authed():
                    return self._send_json(401, {"ok": False, "error": "unauthorized"})
                return self._send_json(200, self._status_payload(stm))
            # other static assets next to the html (fonts are loaded from Google, so this is rarely used)
            if path.startswith("/static/"):
                return self._send_file(WEB_DIR / path[len("/static/"):].lstrip("/"), root=WEB_DIR)
            self._send_json(404, {"ok": False, "error": "not found"})
        except Exception as e:  # noqa: BLE001 - never let a handler take the server down
            log(f"ERROR GET {path}: {type(e).__name__}: {e}")
            try:
                self._send_json(500, {"ok": False, "error": "internal error"})
            except Exception:  # noqa: BLE001
                pass

    do_HEAD = do_GET

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            stm, path = self._route(path)
            if stm is None:
                self._drain()
                return self._send_json(404, {"ok": False, "error": "bad stream id"})
            if path == "/live/playback":
                return self._live_playback(stm)
            if not path.startswith("/api/v1/"):
                self._drain()
                return self._send_json(404, {"ok": False, "error": "not found"})
            if not self._authed():
                self._drain()
                return self._send_json(401, {"ok": False, "error": "unauthorized"})
            if not can_create(stm):
                self._drain()
                return self._send_json(409, {"ok": False, "error": f"stream limit reached ({MAX_STREAMS})"})
            if path == "/api/v1/desk":
                return self._api_desk(stm)
            if path == "/api/v1/uploads":
                return self._api_uploads(stm, self._read_json())
            m = re.match(r"^/api/v1/packages/([^/]+)/complete$", path)
            if m:
                return self._api_complete(stm, m.group(1), self._read_json())
            if path == "/api/v1/retire":
                return self._api_retire(stm, self._read_json())
            self._drain()
            self._send_json(404, {"ok": False, "error": "not found"})
        except ValueError as e:
            self._send_json(400, {"ok": False, "error": str(e)})
        except Exception as e:  # noqa: BLE001
            log(f"ERROR POST {path}: {type(e).__name__}: {e}")
            try:
                self._send_json(500, {"ok": False, "error": "internal error"})
            except Exception:  # noqa: BLE001
                pass

    # ---- api ---------------------------------------------------------------------------
    def _api_uploads(self, stm: Stream, req: dict) -> None:
        pid = req.get("package_id", "")
        files = req.get("files")
        if not isinstance(pid, str) or not PACKAGE_ID_RE.match(pid):
            return self._send_json(400, {"ok": False, "error": "bad package_id"})
        if not isinstance(files, list) or not files or len(files) > 200:
            return self._send_json(400, {"ok": False, "error": "files must be a non-empty list"})
        total, urls = 0, []
        for f in files:
            name = f.get("path", "")
            ct = f.get("content_type", "application/octet-stream")
            size = int(f.get("size", 0))
            if not SAFE_NAME_RE.match(name or "") or "/" in name:
                return self._send_json(400, {"ok": False, "error": f"bad file name {name!r}"})
            if ct not in ALLOWED_UPLOAD_TYPES:
                return self._send_json(400, {"ok": False, "error": f"content type {ct!r} not allowed"})
            total += size
            if size < 0 or total > MAX_PACKAGE_BYTES:
                return self._send_json(400, {"ok": False, "error": "package too large"})
            key = f"{stm.prefix}/{pid}/{name}"
            url = s3().generate_presigned_url("put_object", Params={"Bucket": BUCKET, "Key": key, "ContentType": ct},
                                              ExpiresIn=PRESIGN_TTL, HttpMethod="PUT")
            urls.append({"path": name, "key": key, "url": url, "method": "PUT", "headers": {"Content-Type": ct}})
        log(f"[{stm.sid}] presigned {len(urls)} upload url(s) for {pid} ({total} bytes)")
        self._send_json(200, {"ok": True, "stream": stm.sid, "package_id": pid, "prefix": f"{stm.prefix}/{pid}/",
                              "urls": urls, "expires_in": PRESIGN_TTL})

    def _api_complete(self, stm: Stream, pid: str, req: dict) -> None:
        if not PACKAGE_ID_RE.match(pid):
            return self._send_json(400, {"ok": False, "error": "bad package_id"})
        manifest_key = req.get("manifest_key") or f"{stm.prefix}/{pid}/manifest.json"
        with _state_lock:
            st = load_state(stm)
            if st.get("current") and st["current"]["package_id"] == pid:
                return self._send_json(200, {"ok": True, "package_id": pid, "activated": False,
                                             "note": "already current", "retired": []})
            manifest, problems = download_package(stm, pid, manifest_key)
            if not problems:
                problems = validate_manifest(manifest, package_dir(stm, pid))
            if problems:
                shutil.rmtree(package_dir(stm, pid), ignore_errors=True)
                log(f"[{stm.sid}] package {pid} REJECTED: {'; '.join(problems)[:500]}")
                return self._send_json(422, {"ok": False, "stream": stm.sid, "package_id": pid, "activated": False,
                                             "error": "package rejected", "problems": problems})
            set_current(stm, st, pid)
            retired = prune_packages(stm, st)
            save_state(stm, st)
        log(f"[{stm.sid}] package {pid} activated ({len(manifest.get('scenes', []))} scenes); retired {retired}")
        self._send_json(200, {"ok": True, "stream": stm.sid, "package_id": pid, "activated": True, "retired": retired,
                              "s3_delete_denied": bool(st.get("s3_delete_denied"))})

    def _api_retire(self, stm: Stream, req: dict) -> None:
        ids = req.get("package_ids")
        if not isinstance(ids, list):
            return self._send_json(400, {"ok": False, "error": "package_ids must be a list"})
        with _state_lock:
            st = load_state(stm)
            protected = {(st.get("current") or {}).get("package_id"), (st.get("playing") or {}).get("package_id")}
            retired, skipped = [], []
            for pid in ids:
                if not isinstance(pid, str) or not PACKAGE_ID_RE.match(pid) or pid in protected:
                    skipped.append(pid)
                    continue
                shutil.rmtree(package_dir(stm, pid), ignore_errors=True)
                ok, note = s3_delete_prefix(f"{stm.prefix}/{pid}/")
                if not ok:
                    st["s3_delete_denied"] = True
                retired.append(pid)
            st["retired"] = (st.get("retired") or [])[-200:] + retired
            save_state(stm, st)
        self._send_json(200, {"ok": True, "retired": retired, "skipped": skipped,
                              "s3_delete_denied": bool(st.get("s3_delete_denied"))})

    def _status_payload(self, stm: Stream) -> dict:
        with _state_lock:
            st = load_state(stm)
        usage = shutil.disk_usage(str(DATA_DIR if DATA_DIR.exists() else Path("/")))
        return {"ok": True, "time": now_iso(), "stream": stm.sid, "s3_prefix": f"{stm.prefix}/",
                "current": st.get("current"), "playing": st.get("playing"),
                "packages": local_packages(stm), "retired": st.get("retired", [])[-50:],
                "s3_delete_denied": bool(st.get("s3_delete_denied")), "disk_free_mb": usage.free // (1 << 20),
                "keep_packages": KEEP_PACKAGES}

    def _streams_summary(self, full: bool) -> list[dict]:
        """Every stream with something published. Public view: on-air package and desk time only."""
        out = []
        for stm in all_streams():
            with _state_lock:
                st = load_state(stm)
            cur = st.get("current") or {}
            desk = None
            if stm.desk_path.is_file():
                try:
                    desk = json.loads(stm.desk_path.read_text(encoding="utf-8")).get("generated_at")
                except (OSError, ValueError):
                    pass
            if stm.sid == DEFAULT_STREAM and not cur and not desk:
                continue
            row = {"stream": stm.sid, "page": "/" if stm.sid == DEFAULT_STREAM else f"/s/{stm.sid}/",
                   "package_id": cur.get("package_id"), "activated_at": cur.get("activated_at"), "desk_generated_at": desk}
            if full:
                row.update({"playing": st.get("playing"), "packages": len(local_packages(stm)), "s3_prefix": f"{stm.prefix}/"})
            out.append(row)
        return out

    # ---- live (public) -----------------------------------------------------------------
    # ---- desk data (the page's live numbers) ---------------------------------------------
    def _api_desk(self, stm: Stream) -> None:
        """POST /api/v1/desk: replace the stream's desk.json. The previous file stays if the new one is invalid."""
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_DESK_BYTES:
            self._drain()
            return self._send_json(413 if n > 0 else 400, {"ok": False, "error": f"body must be 1..{MAX_DESK_BYTES} bytes"})
        try:
            doc = json.loads(self.rfile.read(n).decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            return self._send_json(400, {"ok": False, "error": f"invalid json: {e}"})
        problems = []
        if not isinstance(doc, dict):
            problems.append("json object expected")
        else:
            if doc.get("schema_version") != 1:
                problems.append("schema_version must be 1")
            problems += [f"missing {k}" for k in DESK_REQUIRED if not doc.get(k)]
            c = doc.get("center") or {}
            if not (isinstance(c.get("lat"), (int, float)) and -60 <= c["lat"] <= 60
                    and isinstance(c.get("lon"), (int, float)) and 80 <= c["lon"] <= 200):
                problems.append("center lat/lon out of range")
        if problems:
            log(f"[{stm.sid}] desk rejected: {problems}")
            return self._send_json(422, {"ok": False, "error": "invalid desk document", "problems": problems})
        stm.desk_history_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(stm.desk_path, doc)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        write_json_atomic(stm.desk_history_dir / f"desk-{stamp}.json", doc)
        old = sorted(stm.desk_history_dir.glob("desk-*.json"))
        for f in old[:-DESK_KEEP]:
            f.unlink(missing_ok=True)
        self._send_json(200, {"ok": True, "stream": stm.sid, "generated_at": doc.get("generated_at"), "stale": doc.get("stale", []),
                              "bytes": n, "history": min(len(old), DESK_KEEP)})

    def _live_desk(self, stm: Stream) -> None:
        """The most recent good desk.json of the stream, whatever its age (the page never shows an empty state);
        a stream that has never had one gets the default stream's."""
        path = None
        for s in ([stm] if stm.sid == DEFAULT_STREAM else [stm, get_stream(DEFAULT_STREAM)]):
            if s.desk_path.is_file():
                path = s.desk_path
            elif s.desk_history_dir.is_dir():
                hist = sorted(s.desk_history_dir.glob("desk-*.json"))
                path = hist[-1] if hist else None
            if path:
                break
        if path is None:
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _live_current(self, stm: Stream) -> None:
        with _state_lock:
            st = load_state(stm)
        cur = st.get("current")
        if not cur:
            return self._send_json(204, {})
        m = read_manifest(stm, cur["package_id"])
        if m is None:
            return self._send_json(404, {"ok": False, "error": "current package missing on disk"})
        m = dict(m)
        m["_activated_at"] = cur.get("activated_at")
        self._send_json(200, m, {"ETag": f'"{cur["package_id"]}"'})

    def _live_file(self, stm: Stream, rest: str) -> None:
        parts = rest.split("/")
        if len(parts) != 2 or not PACKAGE_ID_RE.match(parts[0]) or not SAFE_NAME_RE.match(parts[1]):
            return self._send_json(404, {"ok": False, "error": "not found"})
        self._send_file(package_dir(stm, parts[0]) / parts[1], root=stm.packages_dir, cache="public, max-age=86400, immutable")

    def _live_playback(self, stm: Stream) -> None:
        try:
            req = self._read_json()
        except ValueError:
            return self._send_json(400, {"ok": False, "error": "bad json"})
        pid = req.get("package_id")
        if not isinstance(pid, str) or not PACKAGE_ID_RE.match(pid):
            return self._send_json(400, {"ok": False, "error": "bad package_id"})
        if not stm.exists():                     # public endpoint: never creates a stream
            return self._send_json(404, {"ok": False, "error": "unknown stream"})
        with _state_lock:
            st = load_state(stm)
            st["playing"] = {"package_id": pid, "scene_id": str(req.get("scene_id", ""))[:128],
                             "playlist_index": int(req.get("playlist_index", 0) or 0), "at": now_iso(),
                             "client": self.client_address[0]}
            save_state(stm, st)
        self._send_json(200, {"ok": True})

    # ---- static files with Range support -----------------------------------------------
    def _send_file(self, path: Path, root: Path | None = None, cache: str = "no-cache") -> None:
        root = (root or WEB_DIR).resolve()
        try:
            real = path.resolve()
        except OSError:
            return self._send_json(404, {"ok": False, "error": "not found"})
        if root not in real.parents or not real.is_file():
            return self._send_json(404, {"ok": False, "error": "not found"})
        size = real.stat().st_size
        ctype = CONTENT_TYPES.get(real.suffix.lower(), "application/octet-stream")
        start, end = 0, size - 1
        status = 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            m = re.match(r"^bytes=(\d*)-(\d*)$", rng.strip())
            if not m:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            a, b = m.group(1), m.group(2)
            if a:
                start = int(a)
                end = int(b) if b else size - 1
            else:
                start = max(0, size - int(b or 0))
            end = min(end, size - 1)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", cache)
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(real, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1 << 16, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    if not API_TOKEN and not NO_TLS:
        log("API_TOKEN is not set; refusing to start")
        return 2
    get_stream(DEFAULT_STREAM).packages_dir.mkdir(parents=True, exist_ok=True)
    with _state_lock:
        for stm in all_streams():
            st = load_state(stm)
            # a current package that vanished from disk must not be advertised
            if st.get("current") and read_manifest(stm, st["current"]["package_id"]) is None:
                log(f"[{stm.sid}] current package {st['current']['package_id']} missing on disk; clearing")
                set_current(stm, st, None)
            save_state(stm, st)
    httpd = ThreadingHTTPServer((BIND, PORT), Handler)
    httpd.daemon_threads = True
    if not NO_TLS:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(CERT, KEY)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    log(f"serving {'http' if NO_TLS else 'https'}://{BIND}:{PORT} web={WEB_DIR} data={DATA_DIR} bucket={BUCKET} "
        f"keep={KEEP_PACKAGES} streams={[s.sid for s in all_streams()]}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
