"""Prepare the scheduled YouTube broadcasts for the election streams (es / ja / zh). Default: a dry run.

    PY=/home/andyshi2/.conda/envs/ai-livestream/bin/python
    $PY scripts/election_youtube.py                     # dry run: lint + print the plan for es, ja, zh (no API call)
    $PY scripts/election_youtube.py --create --lang ja  # create ONE scheduled broadcast (writes to YouTube)
    $PY scripts/election_youtube.py --create            # create all three

Per language, from saved_configs/election_<lang>.json ("youtube" section), with src/broadcast/youtube.py:
  1. ensure_stream("encoder-election_<lang>"): a reusable 1080p30 RTMPS ingest stream, i.e. that stream's own key. It is
     the stream scripts/youtube_live.py --config saved_configs/election_<lang>.json uses, so going live binds the same key.
  2. create_broadcast(): scheduled start, privacy (unlisted until go-live), selfDeclaredMadeForKids=false, auto-start,
     DVR, bound to that stream.
  3. update_video(): categoryId 25 (News & Politics), tags, defaultLanguage / defaultAudioLanguage, then
     status.containsSyntheticMedia=true with videos.update (the liveBroadcasts resource has no such field).
  4. Reads the video back and checks containsSyntheticMedia, selfDeclaredMadeForKids=false and categoryId 25.
  5. Uploads the thumbnail when the file exists (output/youtube/thumb_election_<lang>.jpg).
  6. Writes .run/youtube/election_<lang>.json, so youtube_live.py reuses this broadcast and never renders the typhoon
     desk's thumbnail or metadata.
The stream key is never printed or written by this script (only the ingest stream's id and title).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
STATE_DIR = REPO / ".run" / "youtube"
LANGS = ("es", "ja", "zh")
# research/election/legal.md s6b: the disclosure each description must carry verbatim
DISCLOSURE = {
    "es": "Guion escrito con IA y leído por una voz sintética. Resultados no oficiales de las oficinas electorales estatales. "
          "Sin afiliación con ningún medio, campaña ni gobierno.",
    "ja": "原稿はAIが作成し、合成音声で読み上げています。数字は各州選挙当局の非公式開票結果です。報道機関・陣営・政府とは無関係です。",
    "zh": "本节目由AI撰稿、合成语音播报。数据为各州选举机构公布的非正式计票结果。与任何新闻机构、竞选阵营或政府无关。",
}
# rules 16, 18, 43: no "official", no network or wire names, no winner / projection words in the title
TITLE_BANNED = re.compile(r"official|oficial|公式|官方|project|proyecci|predic|ganador|gana\b|winner|wins|当選|当確|胜选|胜出|"
                          r"\bCNN\b|\bFox\b|\bNBC\b|\bABC\b|\bCBS\b|MSNBC|Univision|Telemundo|NHK|\bAP\b|Associated Press|"
                          r"Decision Desk|DDHQ|Reuters|ロイター|路透|美联社", re.I)


def load(lang: str) -> dict:
    cfg = json.loads((REPO / "saved_configs" / f"election_{lang}.json").read_text(encoding="utf-8"))
    return cfg["youtube"]


def lint(lang: str, y: dict) -> list[str]:
    bad = []
    if len(y["title"]) > 100:
        bad.append(f"title is {len(y['title'])} characters (YouTube max 100)")
    if TITLE_BANNED.search(y["title"]):
        bad.append(f"title contains {TITLE_BANNED.search(y['title']).group(0)!r} (rules 16, 18, 43)")
    if len(y["description"]) > 4900:
        bad.append("description over 4,900 characters")
    if DISCLOSURE[lang] not in y["description"]:
        bad.append("description lacks the legal.md s6b disclosure string")
    if sum(len(t) + 2 for t in y["tags"]) > 480:
        bad.append("tags over YouTube's 500-character budget")
    if y.get("category_id") != "25":
        bad.append("category is not 25 (News & Politics)")
    if datetime.fromisoformat(y["scheduled_start"]) <= datetime.now(timezone.utc):
        bad.append(f"scheduled_start {y['scheduled_start']} is in the past")
    return bad


def create(lang: str, y: dict) -> dict:
    from broadcast import youtube
    yt = youtube.service()
    state_path = STATE_DIR / f"election_{lang}.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else None
    if state and youtube.broadcast_status(state["broadcast_id"], yt) in ("created", "ready", "testing", "testStarting", "live"):
        print(f"{lang}: reusing prepared broadcast https://youtube.com/watch?v={state['broadcast_id']}; re-applying metadata")
    else:                       # a new broadcast; the state is saved at once so a failure below never orphans it
        stream = youtube.ensure_stream(f"encoder-election_{lang}", yt)      # its own stream key; never printed
        bc = youtube.create_broadcast(y["title"], y["description"], stream["id"], y.get("privacy_at_create", "unlisted"), yt,
                                      start=datetime.fromisoformat(y["scheduled_start"]))
        state = {"broadcast_id": bc["id"], "stream_id": stream["id"], "stream_title": stream["snippet"]["title"],
                 "privacy": y.get("privacy_at_create", "unlisted"), "lang": lang, "title": y["title"], "headline": None,
                 "created": datetime.now(timezone.utc).isoformat()}
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    bc_id = state["broadcast_id"]
    youtube.update_video(bc_id, y["title"], y["description"], y["tags"], category=y["category_id"],
                         language=y["default_language"], audio_language=y["default_audio_language"], synthetic=True, yt=yt)
    v = yt.videos().list(part="status,snippet", id=bc_id).execute()["items"][0]
    checks = {"containsSyntheticMedia": v["status"].get("containsSyntheticMedia") is True,
              "selfDeclaredMadeForKids=false": v["status"].get("selfDeclaredMadeForKids") is False,
              "categoryId=25": v["snippet"].get("categoryId") == "25"}
    thumb = REPO / y["thumbnail"]
    if thumb.is_file():
        try:
            youtube.set_thumbnail(bc_id, thumb, yt)
            checks["thumbnail"] = True
        except Exception as e:  # noqa: BLE001 - report, do not lose the broadcast
            print(f"{lang}: thumbnail upload failed: {e}")
            checks["thumbnail"] = False
    else:
        checks["thumbnail"] = False
    state.update(title=y["title"], checks=checks, metadata_applied=datetime.now(timezone.utc).isoformat())
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{lang}: https://youtube.com/watch?v={bc_id}  stream {state.get('stream_title', state['stream_id'])}  checks {checks}")
    if not all(checks.values()):
        print(f"{lang}: CHECK FAILED: {[k for k, ok in checks.items() if not ok]}; fix before going live")
    return state


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=LANGS + ("all",), default="all")
    ap.add_argument("--create", action="store_true", help="really create the broadcast(s) on YouTube")
    a = ap.parse_args()
    langs = LANGS if a.lang == "all" else (a.lang,)
    problems = 0
    for lang in langs:
        y = load(lang)
        bad = lint(lang, y)
        problems += len(bad)
        print(f"== {lang}: stream encoder-election_{lang}, start {y['scheduled_start']}, privacy {y.get('privacy_at_create')}, "
              f"category {y['category_id']}, language {y['default_language']}/{y['default_audio_language']}, "
              f"thumbnail {'ok' if (REPO / y['thumbnail']).is_file() else 'MISSING ' + y['thumbnail']}")
        print(f"   title ({len(y['title'])}): {y['title']}")
        print(f"   tags: {', '.join(y['tags'])}")
        for b in bad:
            print(f"   PROBLEM: {b}")
        if a.create and not bad:
            create(lang, y)
    if not a.create:
        print("dry run: nothing was sent to YouTube (add --create)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
