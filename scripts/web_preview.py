"""Local preview of the broadcast website with live data.

Serves html/ straight from disk (no caching, so a browser refresh shows your last save) and
forwards /live/* and /healthz to the EC2 server through the ssh tunnel, so the page plays the
real published package. Nothing here changes what viewers of the EC2 site see.

Streams: /s/<id>/ serves the page for stream <id> (its relative live/ urls become /s/<id>/live/...,
proxied to EC2 as they are); / is the default stream, as on EC2. Streams whose id starts with "india" get
html/india-desk.html (North Indian Ocean, ?lang=te|ta), every other stream html/champi-desk.html.

Election streams (id starting with "election": election-es, election-ja, election-zh) get html/election-desk.html, and
their live/* is served from local disk instead of EC2 (docs/ELECTION.md, "Page contract"):
live/current.json and live/desk.json from output/election/air/<stream>/ (204 while missing), live/<package_id>/<file>
from output/election/air/<stream>/<package_id>/ (Range ok), and POST live/playback writes <stream>/playback.json.
"""

import http.client
import json
import os
import re
import ssl
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEB_DIR = Path(os.environ.get("WEB_DIR", REPO / "html"))
PORT = int(os.environ.get("PREVIEW_PORT", "8095"))
UPSTREAM_PORT = int(os.environ.get("EC2_TUNNEL_PORT", "18443"))
CA = os.environ.get("EC2_CA_CERT", str(REPO / "secrets" / "ec2_server.crt"))
TLS = ssl.create_default_context(cafile=CA)
PROXIED = ("/live/", "/healthz")
FORWARD_HEADERS = ("Range", "Content-Type", "If-None-Match", "If-Modified-Since")


ALIAS_FILE = Path(os.environ.get("STREAM_ALIAS_FILE", REPO / ".run" / "stream_alias.json"))

# Election streams (ids starting with "election", e.g. election-ja): the page is html/election-desk.html and its
# live/* comes from local disk, ELECTION_AIR_DIR/<stream>/ (docs/ELECTION.md "Page contract"), not from EC2.
ELECTION_AIR = Path(os.environ.get("ELECTION_AIR_DIR", REPO / "output" / "election" / "air"))
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MEDIA_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".opus": "audio/ogg", ".m4a": "audio/mp4",
               ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp",
               ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8"}


def is_election(sid: str) -> bool:
    return sid.startswith("election")


def alias_path(path: str) -> tuple[str, str]:
    """STREAM_ALIAS_FILE ({"page stream": "data stream"}, re-read on every request): /s/<page>/live/... is served from
    /s/<data>/live/... on EC2, so a running encoder can switch to another publisher's stream at the next scene boundary
    without a reload. Returns (upstream path, the aliased page stream or "")."""
    try:
        aliases = json.loads(ALIAS_FILE.read_text(encoding="utf-8")) if ALIAS_FILE.is_file() else {}
    except (OSError, ValueError):
        aliases = {}
    m = re.match(r"^/s/([a-z0-9][a-z0-9-]{0,31})(/live/.*)$", path)
    if m and aliases.get(m.group(1)) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", aliases[m.group(1)]):
        return f"/s/{aliases[m.group(1)]}{m.group(2)}", m.group(1)
    return path, ""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self):
        if not (self.path.startswith(PROXIED) or "/live/" in self.path):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        m = re.match(r"^/s/([a-z0-9][a-z0-9-]{0,31})(/[^?]*)?(\?.*)?$", self.path)
        if m:                                   # a named stream: /s/<id>/live/* -> EC2, anything else -> the page
            rest, query = m.group(2) or "", m.group(3) or ""
            if not rest:
                self.send_response(301)
                self.send_header("Location", f"/s/{m.group(1)}/{query}")
                self.send_header("Content-Length", "0")
                return self.end_headers()
            if rest.startswith("/live/") and is_election(m.group(1)):
                return self.election_live(m.group(1), rest[len("/live/"):])
            if rest.startswith("/live/"):
                return self.proxy("GET")
            if rest != "/" and (WEB_DIR / rest.lstrip("/")).resolve().is_relative_to(WEB_DIR.resolve()) and (WEB_DIR / rest.lstrip("/")).is_file():
                self.path = rest + query            # another file of the site (thumb-hero.html, thumb/...) for this stream
                return super().do_GET()
            # India streams (india-te, india-ta) get their own page; every other stream the Western Pacific desk
            self.path = ("/india-desk.html" if m.group(1).startswith("india") else "/champi-desk.html") + query
            if is_election(m.group(1)):             # election-es / -ja / -zh: the results desk
                self.path = "/election-desk.html" + query
            return super().do_GET()
        if self.path.startswith(PROXIED):
            return self.proxy("GET")
        if self.path.split("?")[0] in ("/", "/index.html"):
            self.path = "/champi-desk.html" + (self.path[self.path.find("?"):] if "?" in self.path else "")
        super().do_GET()

    def do_POST(self):
        m = re.match(r"^/s/(election[a-z0-9-]{0,23})/live/playback(\?.*)?$", self.path)
        if m:
            return self.election_playback(m.group(1))
        if self.path.startswith(PROXIED) or re.match(r"^/s/[a-z0-9-]+/live/", self.path):
            return self.proxy("POST")
        self.send_error(405)

    # ---- election streams: live/* from ELECTION_AIR/<stream>/ on local disk ------------------------------------
    def send_empty(self, status: int, extra: dict | None = None):
        self.send_response(status)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def election_live(self, sid: str, rest: str):
        """live/current.json and live/desk.json (204 while missing, no-store), live/<package_id>/<file> (Range ok)."""
        base = ELECTION_AIR / sid
        if rest in ("current.json", "desk.json"):
            try:
                body = (base / rest).read_bytes()
            except OSError:                         # not written yet (or mid-rename): the page keeps polling
                return self.send_empty(204)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return self.wfile.write(body)
        parts = rest.split("/")
        if len(parts) != 2 or not all(SAFE_NAME.match(p) for p in parts):
            return self.send_error(404)
        path = (base / parts[0] / parts[1])
        try:
            real = path.resolve(strict=True)
        except OSError:
            return self.send_error(404)
        if not real.is_relative_to(base.resolve()) or not real.is_file():
            return self.send_error(404)
        size = real.stat().st_size
        start, end, status = 0, size - 1, 200
        rng = (self.headers.get("Range") or "").strip()
        if rng:
            r = re.match(r"^bytes=(\d*)-(\d*)$", rng)
            if r and (r.group(1) or r.group(2)):
                if r.group(1):
                    start, end = int(r.group(1)), min(int(r.group(2)) if r.group(2) else size - 1, size - 1)
                else:                                # suffix range: the last N bytes
                    start = max(0, size - int(r.group(2)))
                if start > end or start >= size:
                    return self.send_empty(416, {"Content-Range": f"bytes */{size}"})
                status = 206
        self.send_response(status)
        self.send_header("Content-Type", MEDIA_TYPES.get(real.suffix.lower(), "application/octet-stream"))
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(real, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0 and (chunk := f.read(min(64 * 1024, left))):
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):   # Chromium seeked or dropped the request
                    break
                left -= len(chunk)

    def election_playback(self, sid: str):
        """POST live/playback: the page's heartbeat JSON, written atomically to ELECTION_AIR/<stream>/playback.json."""
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 64 * 1024:
            return self.send_empty(400 if n <= 0 else 413)
        try:
            doc = json.loads(self.rfile.read(n))
            if not isinstance(doc, dict):
                raise ValueError("not an object")
        except ValueError:
            return self.send_empty(400)
        base = ELECTION_AIR / sid
        base.mkdir(parents=True, exist_ok=True)
        tmp = base / f".playback.{os.getpid()}.{threading.get_ident()}.tmp"
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, base / "playback.json")
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def proxy(self, method):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method == "POST" else None
        headers = {h: self.headers[h] for h in FORWARD_HEADERS if self.headers.get(h)}
        path, alias_from = alias_path(self.path)
        try:
            conn = http.client.HTTPSConnection("127.0.0.1", UPSTREAM_PORT, context=TLS, timeout=30)
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            if resp.status == 404 and alias_from and method == "GET":   # a file of the package still playing from the old stream
                resp.read(); conn.close()
                conn = http.client.HTTPSConnection("127.0.0.1", UPSTREAM_PORT, context=TLS, timeout=30)
                conn.request(method, self.path, body=body, headers=headers)
                resp = conn.getresponse()
        except OSError as error:
            return self.send_error(502, f"EC2 not reachable through the tunnel ({error}); run scripts/ec2_tunnel.sh")
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in ("connection", "transfer-encoding", "server", "date"):
                self.send_header(k, v)
        self.end_headers()
        while chunk := resp.read(64 * 1024):
            try:
                self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):  # browser seeked or closed the audio
                break
        conn.close()

    def log_message(self, fmt, *args):
        quiet = self.path.endswith("/live/current.json") or (     # the page polls this every 5 s
            self.path.startswith("/s/election") and self.path.endswith(("/live/desk.json", "/live/playback")))
        if not quiet:
            sys.stderr.write("%s  %s\n" % (self.log_date_time_string(), fmt % args))


if __name__ == "__main__":
    print(f"preview: http://127.0.0.1:{PORT}/  (serving {WEB_DIR}, /live/* -> EC2 via 127.0.0.1:{UPSTREAM_PORT})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
