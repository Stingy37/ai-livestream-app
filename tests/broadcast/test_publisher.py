"""Offline tests for the broadcast package + publisher: a tiny in-process HTTP stub stands in
for ec2/server.py and for S3's presigned PUT urls. No network, no TLS, no boto3."""

from __future__ import annotations

import json
import math
import struct
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from broadcast.package import PackageBuilder, SceneEntry, load_manifest, validate_manifest
from broadcast.publisher import Publisher, PublishError

TOKEN = "test-token"


def write_sine(path: Path, seconds: float = 1.0, rate: int = 24000) -> None:
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(frames)))


class Stub:
    """Fake EC2 server: records what it saw; `fail_complete` makes /complete reject the package."""

    def __init__(self):
        self.puts: dict[str, bytes] = {}
        self.requests: list[tuple[str, str]] = []
        self.fail_complete = False
        self.retired = ["pkg-20260101T000000Z-aaaaaa"]
        stub = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _json(self, code, data):
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(n) if n else b""

            def do_GET(self):
                stub.requests.append(("GET", self.path))
                if self.path == "/healthz":
                    return self._json(200, {"ok": True})
                if self.path == "/api/v1/status":
                    if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                        return self._json(401, {"ok": False, "error": "unauthorized"})
                    return self._json(200, {"ok": True, "current": None, "retired": stub.retired})
                self._json(404, {"ok": False})

            def do_PUT(self):
                stub.requests.append(("PUT", self.path))
                stub.puts[self.path] = (self.headers.get("Content-Type"), self._body())
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_POST(self):
                stub.requests.append(("POST", self.path))
                body = json.loads(self._body() or b"{}")
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    return self._json(401, {"ok": False, "error": "unauthorized"})
                if self.path == "/api/v1/uploads":
                    host = self.headers.get("Host")
                    urls = [{"path": f["path"], "key": f"packages/{body['package_id']}/{f['path']}",
                             "url": f"http://{host}/put/{body['package_id']}/{f['path']}", "method": "PUT",
                             "headers": {"Content-Type": f["content_type"]}} for f in body["files"]]
                    return self._json(200, {"ok": True, "package_id": body["package_id"], "urls": urls, "expires_in": 900})
                if self.path.endswith("/complete"):
                    if stub.fail_complete:
                        return self._json(422, {"ok": False, "error": "package rejected", "problems": ["audio sha256 mismatch"]})
                    pid = self.path.split("/")[4]
                    return self._json(200, {"ok": True, "package_id": pid, "activated": True, "retired": stub.retired})
                self._json(404, {"ok": False})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def stub():
    s = Stub()
    yield s
    s.close()


@pytest.fixture
def package(tmp_path):
    wav = tmp_path / "scene.wav"
    write_sine(wav)
    builder = PackageBuilder(tmp_path / "packages", config_name="test", run_id="run-test", storm={"name": "CHAMPI"}, is_test=True)
    entry = SceneEntry(scene_id="s1", node_key="open", title="Show Open", version=1, script_text="Hello. This is a test.",
                       audio_src=wav, headline={"main": "Test", "sub": "sub", "tag": "TEST"})
    return builder.build([entry], playlist=["s1"], reason="initial")


def test_package_builder_writes_a_valid_manifest(package):
    m = load_manifest(package)
    assert m["schema_version"] == 2 and m["package_id"] == package.name and m["is_test"] is True
    assert validate_manifest(m, package) == []
    assert m["scenes"][0]["audio"]["duration_seconds"] == pytest.approx(1.0, abs=0.01)
    assert m["files"][0]["key"] == f"packages/{package.name}/s1.wav"


def test_validate_manifest_reports_problems(package):
    m = load_manifest(package)
    m["scenes"][0]["audio"]["sha256"] = "0" * 64
    m["playlist"] = ["s1", "ghost"]
    problems = validate_manifest(m, package)
    assert any("sha256" in p for p in problems) and any("ghost" in p for p in problems)
    assert "no scenes" in validate_manifest({"schema_version": 2, "package_id": "x", "scenes": []})


def test_publisher_happy_path(stub, package):
    pub = Publisher(api_url=f"http://127.0.0.1:{stub.port}", token=TOKEN, tunnel_port=1)
    reply = pub.upload_package(package)
    assert reply["ok"] and reply["activated"] and reply["retired"] == stub.retired
    assert pub.transport == "direct"
    pid = package.name
    # every file was PUT with the content type that was signed, and complete came after the uploads
    assert set(stub.puts) == {f"/put/{pid}/manifest.json", f"/put/{pid}/s1.wav"}
    assert stub.puts[f"/put/{pid}/s1.wav"][0] == "audio/wav"
    assert stub.puts[f"/put/{pid}/manifest.json"][0] == "application/json"
    assert stub.puts[f"/put/{pid}/s1.wav"][1] == (package / "s1.wav").read_bytes()
    order = [p for _, p in stub.requests]
    assert order.index("/api/v1/uploads") < order.index(f"/put/{pid}/s1.wav") < order.index(f"/api/v1/packages/{pid}/complete")
    assert pub.status()["retired"] == stub.retired


def test_publisher_failed_complete_raises(stub, package):
    stub.fail_complete = True
    pub = Publisher(api_url=f"http://127.0.0.1:{stub.port}", token=TOKEN, tunnel_port=1)
    with pytest.raises(PublishError, match="sha256 mismatch"):
        pub.upload_package(package)


def test_publisher_bad_token_is_a_clear_error(stub, package):
    pub = Publisher(api_url=f"http://127.0.0.1:{stub.port}", token="wrong", tunnel_port=1)
    with pytest.raises(PublishError, match="token"):
        pub.upload_package(package)


def test_publisher_refuses_folder_without_manifest(tmp_path, stub):
    pub = Publisher(api_url=f"http://127.0.0.1:{stub.port}", token=TOKEN, tunnel_port=1)
    with pytest.raises(PublishError):
        pub.upload_package(tmp_path)
