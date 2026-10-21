"""Local preview of the broadcast website with live data.

Serves html/ straight from disk (no caching, so a browser refresh shows your last save) and
forwards /live/* and /healthz to the EC2 server through the ssh tunnel, so the page plays the
real published package. Nothing here changes what viewers of the EC2 site see.

Streams: /s/<id>/ serves the same page for stream <id> (its relative live/ urls become /s/<id>/live/...,
proxied to EC2 as they are); / is the default stream, as on EC2.
"""

import http.client
import os
import re
import ssl
import sys
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
            if rest.startswith("/live/"):
                return self.proxy("GET")
            if rest != "/" and (WEB_DIR / rest.lstrip("/")).resolve().is_relative_to(WEB_DIR.resolve()) and (WEB_DIR / rest.lstrip("/")).is_file():
                self.path = rest + query            # another file of the site (thumb-hero.html, thumb/...) for this stream
                return super().do_GET()
            self.path = "/champi-desk.html" + query
            return super().do_GET()
        if self.path.startswith(PROXIED):
            return self.proxy("GET")
        if self.path.split("?")[0] in ("/", "/index.html"):
            self.path = "/champi-desk.html" + (self.path[self.path.find("?"):] if "?" in self.path else "")
        super().do_GET()

    def do_POST(self):
        if self.path.startswith(PROXIED) or re.match(r"^/s/[a-z0-9-]+/live/", self.path):
            return self.proxy("POST")
        self.send_error(405)

    def proxy(self, method):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method == "POST" else None
        headers = {h: self.headers[h] for h in FORWARD_HEADERS if self.headers.get(h)}
        try:
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
        if not self.path.endswith("/live/current.json"):  # the page polls this every 5 s
            sys.stderr.write("%s  %s\n" % (self.log_date_time_string(), fmt % args))


if __name__ == "__main__":
    print(f"preview: http://127.0.0.1:{PORT}/  (serving {WEB_DIR}, /live/* -> EC2 via 127.0.0.1:{UPSTREAM_PORT})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
