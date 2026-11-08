"""Performance of a broadcast: views, watch time, retention, traffic sources, and (from the Reporting API's reach
reports) thumbnail impressions and click-through rate.

    /home/andyshi2/.conda/envs/ai-livestream/bin/python scripts/youtube_stats.py --video iQiMItPqrYI

Needs the yt-analytics.readonly scope (re-run scripts/youtube_auth.py once). YouTube Analytics data lags by about
1-2 days, and the reach reports (impressions, CTR) only exist from the day a reporting job is created: the first run
creates that job, so impressions/CTR appear on later runs. Results also go to output/youtube/stats_<video>.json.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from broadcast import youtube  # noqa: E402

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


def query(ya, video: str, start: str, end: str, metrics: str, dimensions: str | None = None, sort: str | None = None,
          max_results: int | None = None) -> list[dict]:
    kw = {"ids": "channel==MINE", "startDate": start, "endDate": end, "metrics": metrics, "filters": f"video=={video}"}
    if dimensions:
        kw["dimensions"] = dimensions
    if sort:
        kw["sort"] = sort
    if max_results:
        kw["maxResults"] = max_results
    r = ya.reports().query(**kw).execute()
    cols = [h["name"] for h in r.get("columnHeaders", [])]
    return [dict(zip(cols, row)) for row in r.get("rows", [])]


def reach(video: str) -> dict:
    """Impressions and CTR for the video from the reach report (creates the reporting job on first use)."""
    rp = youtube.reporting()
    types = [t["id"] for t in rp.reportTypes().list().execute().get("reportTypes", [])]
    rtype = next((t for t in types if t.startswith("channel_reach_basic")), None)
    if rtype is None:
        return {"note": f"no reach report type available to this channel ({len(types)} types)"}
    jobs = rp.jobs().list().execute().get("jobs", [])
    job = next((j for j in jobs if j["reportTypeId"] == rtype), None)
    if job is None:
        job = rp.jobs().create(body={"reportTypeId": rtype, "name": "reach (scripts/youtube_stats.py)"}).execute()
        return {"note": f"created reporting job {job['id']} for {rtype}; impressions/CTR appear on a later run (reports take ~1-2 days)"}
    reports = rp.jobs().reports().list(jobId=job["id"]).execute().get("reports", [])
    impressions, clicks = 0.0, 0.0
    days = 0
    from googleapiclient.http import MediaIoBaseDownload

    for rep in reports:
        buf = io.BytesIO()
        req = rp.media().download_media(resourceName="")
        req.uri = rep["downloadUrl"]
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        rows = [r for r in csv.DictReader(io.StringIO(buf.getvalue().decode("utf-8"))) if r.get("video_id") == video]
        if rows:
            days += 1
        for r in rows:
            imp = float(r.get("video_thumbnail_impressions") or 0)
            ctr = float(r.get("video_thumbnail_impressions_ctr") or 0)
            impressions += imp
            clicks += imp * ctr
    if not days:
        return {"note": f"reporting job exists ({len(reports)} report(s)); none covers this video yet"}
    return {"impressions": int(impressions), "ctr": round(clicks / impressions, 4) if impressions else None, "report_days": days}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--start", default=None, help="first day (default: the broadcast's start date)")
    a = ap.parse_args()

    yt = youtube.service()
    v = yt.videos().list(part="snippet,statistics,liveStreamingDetails,contentDetails", id=a.video).execute()["items"][0]
    out: dict = {"video": a.video, "title": v["snippet"]["title"], "statistics": v["statistics"],
                 "live": v.get("liveStreamingDetails", {}), "duration": v["contentDetails"].get("duration")}
    start = a.start or (out["live"].get("actualStartTime") or v["snippet"]["publishedAt"])[:10]
    end = date.today().isoformat()

    if not youtube.has_scope(ANALYTICS_SCOPE):
        out["analytics"] = "missing scope: run scripts/youtube_auth.py again to grant yt-analytics.readonly"
    else:
        ya = youtube.analytics()
        sections = {
            "totals": dict(metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,dislikes,"
                                   "shares,comments,subscribersGained,subscribersLost"),
            "live_vs_on_demand": dict(metrics="views,estimatedMinutesWatched,averageViewDuration", dimensions="liveOrOnDemand"),
            "traffic_sources": dict(metrics="views,estimatedMinutesWatched", dimensions="insightTrafficSourceType", sort="-views"),
            "countries": dict(metrics="views,estimatedMinutesWatched,averageViewDuration", dimensions="country", sort="-views", max_results=10),
            "devices": dict(metrics="views,estimatedMinutesWatched", dimensions="deviceType", sort="-views"),
            "retention": dict(metrics="audienceWatchRatio,relativeRetentionPerformance", dimensions="elapsedVideoTimeRatio"),
        }
        for name, kw in sections.items():
            try:
                out[name] = query(ya, a.video, start, end, **kw)
            except Exception as error:  # noqa: BLE001 - one unsupported query must not hide the others
                out[name] = f"unavailable: {str(error)[:200]}"
        try:
            out["reach"] = reach(a.video)
        except Exception as error:  # noqa: BLE001
            out["reach"] = f"unavailable: {str(error)[:200]}"

    path = REPO / "output" / "youtube" / f"stats_{a.video}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nsaved {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
