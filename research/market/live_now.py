"""Snapshot of evergreen (always-on) live streams: what is live right now for a search, who runs it, how many watch.

    python live_now.py evergreen.json [--out live_now/<UTC stamp>.json]

evergreen.json: [{"topic", "lang", "query", "must": [...]}]. Per query: search.list eventType=live (100 quota units), then
videos.list for concurrent viewers and channels.list for subscriber counts. Event-specific searches (measure.py) miss
these streams, because a 24/7 monitor's title never names the event that spikes it.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/andyshi2/ai-livestream-app/src")
from broadcast import youtube  # noqa: E402

HERE = Path(__file__).resolve().parent


def snapshot(yt, q: dict) -> dict:
    kw = dict(part="id", q=q["query"], type="video", eventType="live", maxResults=50, order="viewCount")
    if q.get("lang"):
        kw["relevanceLanguage"] = q["lang"].split("-")[0]
    ids = [i["id"]["videoId"] for i in yt.search().list(**kw).execute().get("items", [])]
    vids = yt.videos().list(part="snippet,liveStreamingDetails", id=",".join(ids)).execute()["items"] if ids else []
    chans = list({v["snippet"]["channelId"] for v in vids})
    subs = {}
    for i in range(0, len(chans), 50):
        for c in yt.channels().list(part="statistics,snippet", id=",".join(chans[i:i + 50])).execute().get("items", []):
            subs[c["id"]] = (int(c["statistics"].get("subscriberCount", 0) or 0), c["snippet"]["title"])
    rows = []
    for v in vids:
        ld = v.get("liveStreamingDetails") or {}
        cid = v["snippet"]["channelId"]
        rows.append({"id": v["id"], "title": v["snippet"]["title"][:90], "channel": subs.get(cid, (0, "?"))[1], "subs": subs.get(cid, (0, ""))[0],
                     "viewers": int(ld.get("concurrentViewers", 0) or 0), "started": ld.get("actualStartTime")})
    must = [m.lower() for m in q.get("must") or []]
    if must:
        rows = [r for r in rows if any(m in r["title"].lower() for m in must)]
    rows.sort(key=lambda r: -r["viewers"])
    tot = sum(r["viewers"] for r in rows)
    small = sum(r["viewers"] for r in rows if r["subs"] < 100_000)
    big = sum(r["viewers"] for r in rows if r["subs"] >= 1_000_000)
    return dict(q, streams=len(rows), viewers=tot, small_share=round(small / tot, 3) if tot else None,
                big_share=round(big / tot, 3) if tot else None, rows=rows)


def main() -> int:
    qs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE / "live_now" / f"{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    yt = youtube.service()
    res = []
    for q in qs:
        try:
            r = snapshot(yt, q)
        except Exception as error:  # noqa: BLE001
            print(f"error for {q['topic']}: {str(error)[:160]}")
            if "quota" in str(error).lower():
                break
            continue
        res.append(r)
        top = r["rows"][0] if r["rows"] else {}
        print(f'{q["topic"][:34]:34} {q["lang"]:7} live {r["streams"]:3} watching {r["viewers"]:>8,} small {r["small_share"]} big {r["big_share"]} '
              f'top: {top.get("viewers", 0):,} {str(top.get("channel", ""))[:24]} ({top.get("subs", 0):,} subs)')
    out.write_text(json.dumps({"taken_at": stamp, "results": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
