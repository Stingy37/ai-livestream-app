"""ec2/server.py itself, with streams: the real server (plain http) behind the real Publisher, S3 replaced by an
in-memory fake whose presigned urls point at a local PUT endpoint. No network, no TLS, no boto3 calls."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests

from broadcast.package import PackageBuilder, SceneEntry
from broadcast.publisher import Publisher, PublishError

from test_publisher import write_sine

TOKEN = "test-token"
SERVER_PY = Path(__file__).resolve().parents[2] / "ec2" / "server.py"


class FakeS3:
    """The calls server.py makes: presign PUT, download_file, list_objects_v2, delete_objects (denied, like the dev role)."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_PUT(self):
                n = int(self.headers.get("Content-Length") or 0)
                fake.objects[self.path.lstrip("/")] = self.rfile.read(n)
                self.send_response(200)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def generate_presigned_url(self, op, Params, ExpiresIn, HttpMethod):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/{Params['Key']}"

    def download_file(self, bucket, key, dst):
        from botocore.exceptions import ClientError
        if key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "GetObject")
        Path(dst).write_bytes(self.objects[key])

    def list_objects_v2(self, Bucket, Prefix, **kw):
        return {"Contents": [{"Key": k} for k in self.objects if k.startswith(Prefix)]}

    def delete_objects(self, Bucket, Delete):
        from botocore.exceptions import ClientError
        raise ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObjects")


@pytest.fixture
def server(tmp_path, monkeypatch):
    web = tmp_path / "web"
    web.mkdir()
    (web / "champi-desk.html").write_text("<!doctype html><title>desk</title>", encoding="utf-8")
    for k, v in {"API_TOKEN": TOKEN, "NO_TLS": "1", "DATA_DIR": str(tmp_path / "data"), "WEB_DIR": str(web),
                 "KEEP_PACKAGES": "1", "MAX_STREAMS": "3"}.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("ec2_server_under_test", SERVER_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # dataclasses look their module up while the class is created
    spec.loader.exec_module(mod)
    s3 = FakeS3()
    mod._s3 = s3
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    srv = types.SimpleNamespace(mod=mod, s3=s3, url=f"http://127.0.0.1:{httpd.server_address[1]}", data=tmp_path / "data")
    yield srv
    httpd.shutdown()
    s3.httpd.shutdown()


def make_package(root: Path, stream: str, text: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    wav = root / f"{stream}-{len(text)}.wav"
    write_sine(wav)
    b = PackageBuilder(root / stream, config_name=stream, run_id="r", storm={"name": "CHAMPI"}, is_test=True,
                       key_prefix=None if stream == "default" else f"streams/{stream}/packages")
    return b.build([SceneEntry(scene_id="s1", node_key="open", title="Open", version=1, script_text=text, audio_src=wav)],
                   playlist=["s1"], reason="test")


DESK = {"schema_version": 1, "generated_at": "2026-10-20T00:00:00Z", "storm": {"name": "CHAMPI"},
        "center": {"lat": 16.2, "lon": 134.9}, "forecast": {"points": []}, "agencies": [{"agency": "JMA"}]}


def test_streams_are_independent(server, tmp_path):
    pubs = {s: Publisher(api_url=server.url, token=TOKEN, tunnel_port=1, stream=s) for s in ("default", "japan", "philippines")}
    pkgs = {s: make_package(tmp_path / "pk", s, f"script for {s}") for s in pubs}
    for s, pub in pubs.items():
        reply = pub.upload_package(pkgs[s])
        assert reply["ok"] and reply["activated"], reply

    # each stream's files went to its own S3 prefix; the default stream keeps the legacy one
    keys = set(server.s3.objects)
    assert f"packages/{pkgs['default'].name}/s1.wav" in keys
    assert f"streams/japan/packages/{pkgs['japan'].name}/s1.wav" in keys
    assert f"streams/philippines/packages/{pkgs['philippines'].name}/manifest.json" in keys

    # each stream serves its own package; unprefixed /live is the default stream
    for s, base in (("default", "/live"), ("japan", "/s/japan/live"), ("philippines", "/s/philippines/live")):
        m = requests.get(server.url + f"{base}/current.json").json()
        assert m["package_id"] == pkgs[s].name and m["scenes"][0]["script"]["llm_output"] == f"script for {s}"
        audio = requests.get(server.url + f"{base}/{pkgs[s].name}/s1.wav", headers={"Range": "bytes=0-3"})
        assert audio.status_code == 206 and audio.content == b"RIFF"
    # a package of one stream is not reachable through another
    assert requests.get(server.url + f"/s/japan/live/{pkgs['philippines'].name}/s1.wav").status_code == 404

    # status per stream, listing of all
    assert pubs["japan"].status()["stream"] == "japan"
    listing = requests.get(server.url + "/streams.json").json()["streams"]
    assert {r["stream"] for r in listing} == {"default", "japan", "philippines"}
    assert next(r for r in listing if r["stream"] == "japan")["page"] == "/s/japan/"


def test_retention_is_per_stream(server, tmp_path):
    jp = Publisher(api_url=server.url, token=TOKEN, tunnel_port=1, stream="japan")
    ph = Publisher(api_url=server.url, token=TOKEN, tunnel_port=1, stream="philippines")
    ph_pkg = make_package(tmp_path / "a", "philippines", "ph one")
    ph.upload_package(ph_pkg)
    first = make_package(tmp_path / "b", "japan", "jp one")
    jp.upload_package(first)
    second = make_package(tmp_path / "c", "japan", "jp two")
    reply = jp.upload_package(second)
    # KEEP_PACKAGES=1: japan retires its own older package; the philippines package is untouched
    assert reply["retired"] == [first.name]
    assert (server.data / "streams" / "philippines" / "packages" / ph_pkg.name).is_dir()
    assert not (server.data / "streams" / "japan" / "packages" / first.name).exists()


def test_page_desk_and_guards(server, tmp_path):
    # page under /s/<id>/ (redirect without the slash), relative live urls resolve inside the stream
    r = requests.get(server.url + "/s/japan?lang=ja", allow_redirects=False)
    assert r.status_code == 301 and r.headers["Location"] == "/s/japan/?lang=ja"
    assert "<title>desk</title>" in requests.get(server.url + "/s/japan/").text

    # desk: a stream without its own desk gets the default stream's; its own desk wins once published
    Publisher(api_url=server.url, token=TOKEN, tunnel_port=1).push_desk(DESK)
    assert requests.get(server.url + "/s/japan/live/desk.json").json()["generated_at"] == DESK["generated_at"]
    Publisher(api_url=server.url, token=TOKEN, tunnel_port=1, stream="japan").push_desk(dict(DESK, generated_at="2026-10-21T00:00:00Z"))
    assert requests.get(server.url + "/s/japan/live/desk.json").json()["generated_at"] == "2026-10-21T00:00:00Z"
    assert requests.get(server.url + "/live/desk.json").json()["generated_at"] == DESK["generated_at"]

    # bad ids, unauthenticated stream creation, public playback for an unknown stream, the stream limit
    assert requests.get(server.url + "/s/Bad_ID/live/current.json").status_code == 404
    assert requests.post(server.url + "/api/v1/streams/x/desk", json=DESK).status_code == 401
    assert requests.post(server.url + "/s/ghost/live/playback", json={"package_id": "pkg-20260101T000000Z-aaaaaa"}).status_code == 404
    assert not (server.data / "streams" / "ghost").exists()
    for sid in ("s2", "s3"):
        Publisher(api_url=server.url, token=TOKEN, tunnel_port=1, stream=sid).push_desk(DESK)
    with pytest.raises(PublishError, match="stream limit"):
        Publisher(api_url=server.url, token=TOKEN, tunnel_port=1, stream="s4").push_desk(DESK)
    with pytest.raises(PublishError, match="bad stream id"):
        Publisher(api_url=server.url, token=TOKEN, tunnel_port=1, stream="Not OK")
