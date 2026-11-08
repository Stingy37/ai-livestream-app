"""ICRN-side client of the EC2 broadcast server (ec2/server.py).

    publisher = Publisher()                 # settings from the environment / secrets/
    result = publisher.upload_package(package_dir)   # presign -> PUT to S3 -> complete
    publisher.status()                       # what is on air, what was retired
    publisher.retire([package_id, ...])      # explicit retire (normally the server prunes itself)

Transport: the direct url (EC2_API_URL, https://54.221.147.143:8443) is tried first; when it is
unreachable (the security group only opens port 22 today) an SSH local port forward is started
(or reused) and https://127.0.0.1:<EC2_TUNNEL_PORT> is used instead. TLS is verified against the
pinned self-signed certificate deploy.sh copied to secrets/ec2_server.crt; the certificate carries
both the public IP and 127.0.0.1, so verification holds on either transport.

Streams: EC2_STREAM_ID (e.g. "japan") publishes packages and desk.json into that stream's namespace
(/api/v1/streams/<id>/..., S3 streams/<id>/packages/, page at /s/<id>/). Empty or "default" is the
unprefixed single-stream layout, so existing setups are unchanged.

Settings (environment, defaults match src/config_env.Settings):
    EC2_API_URL, EC2_API_TOKEN_FILE, EC2_CA_CERT, EC2_SSH_HOST, EC2_SSH_KEY, EC2_TUNNEL_PORT,
    EC2_UPLOAD_TIMEOUT, EC2_PORT (remote port, 8443), EC2_STREAM_ID, EC2_TLS_INSECURE=1 (escape hatch, warns)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTENT_TYPES = {".wav": "audio/wav", ".json": "application/json", ".txt": "text/plain"}
STREAM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")     # same rule as ec2/server.py


class PublishError(RuntimeError):
    """The package could not be published; the message says why."""


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Publisher:
    def __init__(self, api_url: str | None = None, token: str | None = None, token_file: str | Path | None = None,
                 ca_cert: str | Path | None = None, ssh_host: str | None = None, ssh_key: str | Path | None = None,
                 tunnel_port: int | None = None, remote_port: int | None = None, upload_timeout: float | None = None,
                 insecure: bool | None = None, stream: str | None = None) -> None:
        env = os.environ.get
        self.stream = (env("EC2_STREAM_ID", "") if stream is None else stream).strip() or "default"
        if not STREAM_ID_RE.match(self.stream):
            raise PublishError(f"bad stream id {self.stream!r}: use lowercase letters, digits and '-' (max 32)")
        self.api_url = (api_url or env("EC2_API_URL", "https://54.221.147.143:8443")).rstrip("/")
        self.token_file = Path(token_file or env("EC2_API_TOKEN_FILE", REPO_ROOT / "secrets" / "ec2_api_token")).expanduser()
        self._token = token
        self.ca_cert = Path(ca_cert or env("EC2_CA_CERT", REPO_ROOT / "secrets" / "ec2_server.crt")).expanduser()
        self.ssh_host = ssh_host or env("EC2_SSH_HOST", "ubuntu@54.221.147.143")
        self.ssh_key = Path(ssh_key or env("EC2_SSH_KEY", "~/.ssh/weather-dev")).expanduser()
        self.tunnel_port = int(tunnel_port or env("EC2_TUNNEL_PORT", "18443"))
        self.remote_port = int(remote_port or env("EC2_PORT", "8443"))
        self.upload_timeout = float(upload_timeout or env("EC2_UPLOAD_TIMEOUT", "600"))
        self.insecure = (env("EC2_TLS_INSECURE", "0") == "1") if insecure is None else insecure
        self.base_url: str | None = None      # chosen by connect()
        self.transport: str = ""              # "direct" | "tunnel"
        self._session = requests.Session()

    # ---- connection ----------------------------------------------------------------------
    @property
    def token(self) -> str:
        if self._token is None:
            try:
                self._token = self.token_file.read_text(encoding="utf-8").strip()
            except OSError as e:
                raise PublishError(f"api token not found at {self.token_file} (run ec2/deploy.sh): {e}") from e
        return self._token

    @property
    def verify(self):
        if self.insecure:
            log.warning("EC2_TLS_INSECURE=1: TLS certificate verification is OFF")
            return False
        if self.ca_cert.is_file():
            return str(self.ca_cert)
        return True   # system CA bundle (will fail for the self-signed cert; deploy.sh writes the pin)

    def _healthy(self, base: str, timeout: float = 6.0) -> bool:
        try:
            r = self._session.get(f"{base}/healthz", timeout=timeout, verify=self.verify)
            return r.ok and r.json().get("ok") is True
        except (requests.RequestException, ValueError):
            return False

    def connect(self, force: bool = False) -> str:
        """Pick the direct url or the ssh tunnel; returns the base url in use."""
        if self.base_url and not force and self._healthy(self.base_url):
            return self.base_url
        if self._healthy(self.api_url):
            self.base_url, self.transport = self.api_url, "direct"
            log.info("EC2 reachable directly at %s", self.api_url)
            return self.base_url
        tunnel = f"https://127.0.0.1:{self.tunnel_port}"
        if self.api_url.startswith("http://"):
            tunnel = f"http://127.0.0.1:{self.tunnel_port}"
        if not self._healthy(tunnel):
            self._start_tunnel()
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline and not self._healthy(tunnel):
                time.sleep(1.0)
        if not self._healthy(tunnel):
            raise PublishError(f"EC2 server unreachable: neither {self.api_url} nor the ssh tunnel on {tunnel} answers")
        self.base_url, self.transport = tunnel, "tunnel"
        log.info("EC2 reachable through the ssh tunnel at %s", tunnel)
        return self.base_url

    def _start_tunnel(self) -> None:
        if _port_open("127.0.0.1", self.tunnel_port):
            return   # something is listening already (a tunnel from scripts/ec2_tunnel.sh, probably)
        cmd = ["ssh", "-N", "-f", "-o", "IdentitiesOnly=yes", "-o", "PasswordAuthentication=no",
               "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
               "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=20", "-i", str(self.ssh_key),
               "-L", f"{self.tunnel_port}:127.0.0.1:{self.remote_port}", self.ssh_host]
        log.info("starting ssh tunnel: %s", " ".join(cmd))
        try:
            subprocess.run(cmd, check=True, timeout=60, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise PublishError(f"ssh tunnel failed: {e.stderr.strip()[:300]}") from e
        except (subprocess.TimeoutExpired, OSError) as e:
            raise PublishError(f"ssh tunnel failed: {e}") from e

    # ---- api calls -----------------------------------------------------------------------
    def _stream_path(self, path: str) -> str:
        """/api/v1/x -> /api/v1/streams/<id>/x for a named stream; the default stream keeps the plain path."""
        if self.stream == "default":
            return path
        return f"/api/v1/streams/{self.stream}{path[len('/api/v1'):]}"

    def _api(self, method: str, path: str, payload: dict | None = None, timeout: float = 120.0) -> dict:
        path = self._stream_path(path)
        base = self.connect()
        headers = {"Authorization": f"Bearer {self.token}"}
        last: Exception | None = None
        for attempt in range(3):
            try:
                r = self._session.request(method, f"{base}{path}", json=payload, headers=headers,
                                          timeout=timeout, verify=self.verify)
                try:
                    data = r.json()
                except ValueError:
                    data = {"ok": False, "error": f"non-json response ({r.status_code})"}
                if r.status_code == 401:
                    raise PublishError("EC2 rejected the api token (secrets/ec2_api_token out of date?)")
                if r.status_code >= 500 and attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                data.setdefault("_status", r.status_code)
                return data
            except requests.RequestException as e:
                last = e
                log.warning("EC2 api %s %s failed (attempt %d/3): %s", method, path, attempt + 1, e)
                time.sleep(2.0 * (attempt + 1))
                base = self.connect(force=True)
        raise PublishError(f"EC2 api {method} {path} unreachable: {last}")

    def status(self) -> dict:
        return self._api("GET", "/api/v1/status", timeout=30)

    def push_desk(self, doc: dict) -> dict:
        """Publish desk.json (the page's live numbers). Returns the server's reply; raises PublishError if rejected."""
        reply = self._api("POST", "/api/v1/desk", doc, timeout=60)
        if not reply.get("ok"):
            raise PublishError(f"EC2 rejected desk.json: {reply.get('error')} {reply.get('problems') or ''}".strip())
        return reply

    def retire(self, package_ids: list[str]) -> dict:
        return self._api("POST", "/api/v1/retire", {"package_ids": list(package_ids)}, timeout=120)

    # ---- the upload ----------------------------------------------------------------------
    def upload_package(self, package_dir: str | Path) -> dict:
        """Publish one package folder (manifest.json + wavs). Returns the server's `complete` reply."""
        pdir = Path(package_dir)
        mpath = pdir / "manifest.json"
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise PublishError(f"cannot read {mpath}: {e}") from e
        package_id = manifest.get("package_id", "")
        if not package_id or package_id != pdir.name:
            raise PublishError(f"package_id {package_id!r} does not match folder {pdir.name!r}")

        # every file the manifest lists, plus the manifest itself
        names = ["manifest.json"] + [f["path"] for f in manifest.get("files", [])]
        for s in manifest.get("scenes", []):
            p = (s.get("audio") or {}).get("path")
            if p and p not in names:
                names.append(p)
        files = []
        for name in names:
            path = pdir / name
            if not path.is_file():
                raise PublishError(f"{name} listed in the manifest is missing from {pdir}")
            files.append({"path": name, "content_type": CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"),
                          "size": path.stat().st_size, "sha256": _sha256(path)})

        t0 = time.monotonic()
        reply = self._api("POST", "/api/v1/uploads", {"package_id": package_id, "files": files})
        if not reply.get("ok"):
            raise PublishError(f"presign refused: {reply.get('error', reply)}")
        urls = {u["path"]: u for u in reply["urls"]}
        for f in files:
            u = urls.get(f["path"])
            if u is None:
                raise PublishError(f"no upload url for {f['path']}")
            self._put_file(pdir / f["path"], u)
        log.info("uploaded %d file(s) of %s to S3 in %.1fs", len(files), package_id, time.monotonic() - t0)

        manifest_key = urls["manifest.json"]["key"]
        reply = self._api("POST", f"/api/v1/packages/{package_id}/complete", {"manifest_key": manifest_key},
                          timeout=self.upload_timeout)
        if not reply.get("ok"):
            problems = reply.get("problems") or []
            raise PublishError(f"EC2 rejected package {package_id}: {reply.get('error')} {'; '.join(problems)[:600]}")
        log.info("package %s activated on EC2 (retired: %s)", package_id, reply.get("retired"))
        return reply

    def _put_file(self, path: Path, u: dict) -> None:
        headers = dict(u.get("headers") or {})
        last: Exception | None = None
        for attempt in range(3):
            try:
                with open(path, "rb") as fh:
                    r = requests.put(u["url"], data=fh, headers=headers, timeout=self.upload_timeout)
                if r.status_code in (200, 201, 204):
                    return
                last = PublishError(f"S3 answered {r.status_code}: {r.text[:200]}")
                if 400 <= r.status_code < 500 and r.status_code != 429:
                    break   # a signature/permission problem will not fix itself
            except requests.RequestException as e:
                last = e
            time.sleep(2.0 * (attempt + 1))
        raise PublishError(f"upload of {path.name} failed: {last}")


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False
