"""YouTube Live control through the YouTube Data API v3 (OAuth, one channel).

    python scripts/youtube_auth.py      one-time consent; saves secrets/youtube_token.json (refresh token)

Then, from code: ``service()`` gives an authorised client, ``ensure_stream()`` creates (or reuses) a
persistent RTMPS ingest stream and returns its URL + key, ``create_broadcast()`` makes a broadcast bound
to that stream, ``go_live()`` / ``end()`` transition it, and ``health()`` reports what YouTube receives.
Nothing here sends video: the encoder (scripts/encoder.sh) pushes to the ingest URL.
"""

from __future__ import annotations

import glob
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRETS = REPO_ROOT / "secrets"
# youtube: manage broadcasts; yt-analytics.readonly: watch time, retention, traffic (Analytics API) and the bulk
# reach reports with impressions and CTR (Reporting API)
SCOPES = ["https://www.googleapis.com/auth/youtube", "https://www.googleapis.com/auth/yt-analytics.readonly"]
TOKEN_PATH = Path(os.environ.get("YOUTUBE_TOKEN", SECRETS / "youtube_token.json"))


def client_secret_path() -> Path:
    env = os.environ.get("YOUTUBE_CLIENT_SECRET")
    if env:
        return Path(env)
    found = sorted(glob.glob(str(SECRETS / "client_secret_*.json")))
    if not found:
        raise FileNotFoundError("no secrets/client_secret_*.json (OAuth desktop client from Google Cloud)")
    return Path(found[0])


def credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not TOKEN_PATH.is_file():
        raise RuntimeError(f"not authorised yet: run  python scripts/youtube_auth.py  (creates {TOKEN_PATH})")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))     # the scopes the token was granted
    if not creds.valid:
        creds.refresh(Request())
        save_token(creds)
    return creds


def save_token(creds) -> None:
    TOKEN_PATH.write_text(creds.to_json())
    os.chmod(TOKEN_PATH, 0o600)


def service():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=credentials(), cache_discovery=False)


def has_scope(scope: str) -> bool:
    return scope in (credentials().scopes or [])


def analytics():
    """YouTube Analytics API v2 client (needs yt-analytics.readonly)."""
    from googleapiclient.discovery import build

    return build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)


def reporting():
    """YouTube Reporting API v1 client (bulk daily reports; needs yt-analytics.readonly)."""
    from googleapiclient.discovery import build

    return build("youtubereporting", "v1", credentials=credentials(), cache_discovery=False)


def channel(yt=None) -> dict:
    yt = yt or service()
    items = yt.channels().list(part="snippet,status", mine=True).execute().get("items", [])
    return items[0] if items else {}


def ensure_stream(title: str, yt=None) -> dict:
    """A reusable 1080p RTMPS ingest stream named ``title`` (created once, then reused across broadcasts)."""
    yt = yt or service()
    for s in yt.liveStreams().list(part="id,snippet,cdn,status", mine=True, maxResults=50).execute().get("items", []):
        if s["snippet"]["title"] == title:
            return s
    return yt.liveStreams().insert(part="snippet,cdn,contentDetails,status", body={
        "snippet": {"title": title},
        "cdn": {"frameRate": "30fps", "ingestionType": "rtmp", "resolution": "1080p"},
        "contentDetails": {"isReusable": True}}).execute()


def ingest(stream: dict) -> tuple[str, str]:
    """(RTMPS ingest URL, stream key) of a live stream resource."""
    info = stream["cdn"]["ingestionInfo"]
    return info.get("rtmpsIngestionAddress") or info["ingestionAddress"], info["streamName"]


def create_broadcast(title: str, description: str, stream_id: str, privacy: str = "unlisted", yt=None,
                     start: datetime | None = None) -> dict:
    """A broadcast bound to ``stream_id``; YouTube starts it automatically when video arrives (enableAutoStart).
    ``start`` is only the time shown to viewers before it goes live (default: in one minute)."""
    yt = yt or service()
    start = (start or datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
    b = yt.liveBroadcasts().insert(part="snippet,status,contentDetails", body={
        "snippet": {"title": title[:100], "description": description[:4900], "scheduledStartTime": start},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        "contentDetails": {"enableAutoStart": True, "enableAutoStop": False, "latencyPreference": "normal",
                           "enableDvr": True, "recordFromStart": True}}).execute()
    yt.liveBroadcasts().bind(id=b["id"], part="id,contentDetails", streamId=stream_id).execute()
    return b


def bind(broadcast_id: str, stream_id: str, yt=None) -> None:
    (yt or service()).liveBroadcasts().bind(id=broadcast_id, part="id,contentDetails", streamId=stream_id).execute()


def update_video(video_id: str, title: str, description: str, tags: list[str] | None = None, category: str = "25",
                 language: str | None = None, audio_language: str | None = None, synthetic: bool | None = None, yt=None) -> None:
    """Video-level metadata a broadcast insert cannot set: category (25 = News & Politics), tags, metadata and audio
    language, and the altered-or-synthetic-content disclosure (status.containsSyntheticMedia)."""
    yt = yt or service()
    snippet = {"title": title[:100], "description": description[:4900], "categoryId": category}
    if tags:
        snippet["tags"] = tags
    if language:
        snippet["defaultLanguage"] = language
    if audio_language:
        snippet["defaultAudioLanguage"] = audio_language
    yt.videos().update(part="snippet", body={"id": video_id, "snippet": snippet}).execute()
    if synthetic is not None:
        cur = yt.videos().list(part="status", id=video_id).execute()["items"][0]["status"]
        writable = {k: cur[k] for k in ("privacyStatus", "embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids") if k in cur}
        yt.videos().update(part="status", body={"id": video_id, "status": dict(writable, containsSyntheticMedia=synthetic)}).execute()


def set_privacy(video_id: str, privacy: str, yt=None) -> None:
    """public / unlisted / private, keeping the other writable status fields as they are."""
    yt = yt or service()
    cur = yt.videos().list(part="status", id=video_id).execute()["items"][0]["status"]
    keep = {k: cur[k] for k in ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids") if k in cur}
    yt.videos().update(part="status", body={"id": video_id, "status": dict(keep, privacyStatus=privacy, containsSyntheticMedia=True)}).execute()


def set_thumbnail(video_id: str, path: str | Path, yt=None) -> None:
    """Custom thumbnail (JPEG/PNG, at most 2 MB; the channel needs custom thumbnails enabled, i.e. phone verification)."""
    from googleapiclient.http import MediaFileUpload

    (yt or service()).thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(path), mimetype="image/jpeg")).execute()


def broadcast_status(broadcast_id: str, yt=None) -> str:
    yt = yt or service()
    items = yt.liveBroadcasts().list(part="status", id=broadcast_id).execute().get("items", [])
    return items[0]["status"]["lifeCycleStatus"] if items else "missing"


def go_live(broadcast_id: str, wait_s: float = 120, yt=None) -> str:
    """Transition to live once YouTube sees the stream (auto-start usually does this already)."""
    yt = yt or service()
    deadline = time.time() + wait_s
    while time.time() < deadline:
        st = broadcast_status(broadcast_id, yt)
        if st == "live":
            return st
        if st in ("ready", "testing"):
            try:
                yt.liveBroadcasts().transition(broadcastStatus="live", id=broadcast_id, part="status").execute()
            except Exception:  # noqa: BLE001 - not ready yet; keep polling
                pass
        time.sleep(10)
    return broadcast_status(broadcast_id, yt)


def end(broadcast_id: str, yt=None) -> None:
    (yt or service()).liveBroadcasts().transition(broadcastStatus="complete", id=broadcast_id, part="status").execute()


def health(stream_id: str, yt=None) -> dict:
    yt = yt or service()
    items = yt.liveStreams().list(part="status", id=stream_id).execute().get("items", [])
    return items[0]["status"] if items else {}
