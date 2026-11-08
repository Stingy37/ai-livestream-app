"""Render the election thumbnails (html/thumb-election.html) to output/youtube/thumb_election_<lang>.jpg (1280x720).

    python scripts/render_election_thumbs.py [es ja zh]      # params from saved_configs/thumb_election_<lang>.json
The page is served by scripts/web_preview.py (port 8095); headless Chromium runs in the yt-encoder container.
"""
import asyncio, json, os, signal, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import youtube_thumbnail as yt  # noqa: E402

def render(lang):
    cfg = json.loads((REPO / "saved_configs" / f"thumb_election_{lang}.json").read_text(encoding="utf-8"))
    q = {k: str(v) for k, v in cfg.items() if v not in (None, "") and k != "tpl" and not k.startswith("_")}
    url = f"http://127.0.0.1:{os.environ.get('PREVIEW_PORT', '8095')}/thumb-election.html?" + urllib.parse.urlencode(q)
    out = REPO / "output" / "youtube" / f"thumb_election_{lang}.jpg"
    log = open(REPO / ".run" / "encoder" / "thumbnail_chromium.log", "a")
    proc = subprocess.Popen([yt.UDOCKER, "run", "--nobanner", "-v", "/tmp:/tmp", "yt-encoder", "chromium", "--headless=new", "--no-sandbox",
                             "--disable-gpu", "--hide-scrollbars", "--window-size=1920,1080", f"--user-data-dir=/tmp/thumb-profile-{yt.CDP_PORT}",
                             f"--remote-debugging-port={yt.CDP_PORT}", "--remote-debugging-address=127.0.0.1", "about:blank"],
                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        ws, t0 = None, time.time()
        while ws is None and time.time() - t0 < 60:
            try:
                ws = next((t["webSocketDebuggerUrl"] for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{yt.CDP_PORT}/json/list", timeout=3)) if t.get("type") == "page"), None)
            except OSError:
                pass
            if ws is None:
                time.sleep(1)
        info = asyncio.run(yt._capture(ws, url, out, 90))
        from PIL import Image
        im = Image.open(out).convert("RGB")
        if im.size != (1280, 720):
            im.crop((0, 0, 1280, 720)).save(out, quality=90)      # the page is 1280x720 inside a 1920x1080 viewport
    finally:
        try: os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError: pass
    print(lang, out, info if isinstance(info, dict) and len(str(info)) < 300 else "")

for lang in sys.argv[1:] or ["es", "ja", "zh"]:
    render(lang)
