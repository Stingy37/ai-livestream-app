"""Measure demand and competition for live-stream markets: (event, language) cells.

    python measure.py candidates.json [--max-searches N]

candidates.json: [{"event", "domain", "start_utc", "end_utc", "markets": [{"lang", "country", "youtube_query",
"wikipedia_title"}], ...}]. Per cell:
  wiki    daily pageviews (all-access, user) from start-14d to end+7d: baseline (median of the 14 days before start),
          peak, spike ratio, window total
  youtube completed live streams matching the query, published start-2d .. end+3d (search.list, 100 quota units),
          their views and channels' subscriber counts: n, total views, top-3 share, HHI, share of views by big channels
          (>= 1M subs) and small ones (< 100k), the best small-channel stream
Results are cached per cell in cache/<key>.json, so a run stopped by quota resumes where it stopped.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, "/home/andyshi2/ai-livestream-app/src")
from broadcast import youtube  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)
UA = {"User-Agent": "livestream-market-research/0.1 (student project)"}
BIG, SMALL = 1_000_000, 100_000


def wiki(lang: str, title: str | None, start: date, end: date) -> dict | None:
    if not title:
        return None
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    a, b = (start - timedelta(days=14)).strftime("%Y%m%d"), (end + timedelta(days=7)).strftime("%Y%m%d")
    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/user/{t}/daily/{a}/{b}"
    try:
        items = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30)).get("items", [])
    except Exception as error:  # noqa: BLE001
        return {"error": str(error)[:120]}
    days = {datetime.strptime(i["timestamp"][:8], "%Y%m%d").date(): i["views"] for i in items}
    before = [v for d, v in days.items() if d < start]
    inside = [v for d, v in days.items() if start <= d <= end + timedelta(days=7)]
    base = statistics.median(before) if before else 0
    peak = max(inside or [0])
    return {"baseline": base, "peak": peak, "spike": round(peak / max(base, 10), 1), "window_total": sum(inside)}


def yt_cell(yt, query: str, lang: str, start: date, end: date) -> dict:
    after = datetime.combine(start - timedelta(days=2), datetime.min.time()).isoformat() + "Z"
    before = datetime.combine(end + timedelta(days=3), datetime.min.time()).isoformat() + "Z"
    kw = dict(part="id", q=query, type="video", eventType="completed", publishedAfter=after, publishedBefore=before,
              maxResults=50, order="viewCount")
    if lang:
        kw["relevanceLanguage"] = lang.split("-")[0]
    ids = [i["id"]["videoId"] for i in yt.search().list(**kw).execute().get("items", [])]
    vids = yt.videos().list(part="snippet,statistics,liveStreamingDetails", id=",".join(ids)).execute()["items"] if ids else []
    chans = {v["snippet"]["channelId"] for v in vids}
    subs = {}
    for i in range(0, len(chans), 50):
        for c in yt.channels().list(part="statistics,snippet", id=",".join(list(chans)[i:i + 50])).execute().get("items", []):
            subs[c["id"]] = (int(c["statistics"].get("subscriberCount", 0) or 0), c["snippet"]["title"])
    rows = []
    for v in vids:
        cid = v["snippet"]["channelId"]
        rows.append({"id": v["id"], "views": int(v["statistics"].get("viewCount", 0) or 0), "channel": subs.get(cid, (0, "?"))[1],
                     "subs": subs.get(cid, (0, ""))[0], "title": v["snippet"]["title"][:90],
                     "start": (v.get("liveStreamingDetails") or {}).get("actualStartTime")})
    rows.sort(key=lambda r: -r["views"])
    tot = sum(r["views"] for r in rows)
    by_ch: dict[str, int] = {}
    for r in rows:
        by_ch[r["channel"]] = by_ch.get(r["channel"], 0) + r["views"]
    shares = sorted((v / tot for v in by_ch.values()), reverse=True) if tot else []
    small = [r for r in rows if r["subs"] < SMALL]
    return {"n_streams": len(rows), "n_channels": len(by_ch), "total_views": tot,
            "top3_channel_share": round(sum(shares[:3]), 3) if shares else None,
            "hhi": round(sum(s * s for s in shares), 3) if shares else None,
            "big_share": round(sum(r["views"] for r in rows if r["subs"] >= BIG) / tot, 3) if tot else None,
            "small_share": round(sum(r["views"] for r in small) / tot, 3) if tot else None,
            "best_small": max(small, key=lambda r: r["views"]) if small else None,
            "top": rows[:6], "rows": rows}


def refill_wiki() -> int:
    """Re-fetch Wikipedia stats for cached cells whose lookup failed (429s), slowly, with backoff."""
    import time
    fixed = 0
    for f in sorted(CACHE.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        w = rec.get("wiki")
        if not rec.get("wiki_title") or (w and "error" not in w) or (w and "404" in w.get("error", "")):
            continue
        for wait in (2, 5, 15, 30):
            time.sleep(wait)
            w = wiki(rec["lang"].split("-")[0], rec["wiki_title"], date.fromisoformat(rec["start"]), date.fromisoformat(rec["end"]))
            if not (w and "429" in w.get("error", "")):
                break
        rec["wiki"] = w
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        fixed += 1
        print(f'{rec["event"][:40]:40} {rec["lang"]:7} {w}')
    print(f"refilled {fixed}")
    return 0


def main() -> int:
    global CACHE
    if "--cache" in sys.argv:
        CACHE = HERE / sys.argv[sys.argv.index("--cache") + 1]
        CACHE.mkdir(exist_ok=True)
    only = sys.argv[sys.argv.index("--only") + 1].split(";") if "--only" in sys.argv else None
    if sys.argv[1] == "--refill-wiki":
        return refill_wiki()
    path = Path(sys.argv[1])
    max_searches = int(sys.argv[sys.argv.index("--max-searches") + 1]) if "--max-searches" in sys.argv else 10**6
    events = json.loads(path.read_text(encoding="utf-8"))
    yt = youtube.service()
    done = searches = 0
    for ev in events:
        start, end = date.fromisoformat(ev["start_utc"][:10]), date.fromisoformat(ev["end_utc"][:10])
        if start > date.today():
            continue                                       # upcoming: nothing to measure yet
        for m in ev.get("markets", []):
            if not m.get("youtube_query"):
                continue
            if only and not any(o.split("|")[0].lower() in ev["event"].lower() and (len(o.split("|")) < 2 or o.split("|")[1] == m["lang"])
                                for o in only):
                continue
            key = hashlib.sha1(f'{ev["event"]}|{m["lang"]}|{m["youtube_query"]}|{start}|{end}'.encode()).hexdigest()[:16]
            out = CACHE / f"{key}.json"
            if out.is_file():
                done += 1
                continue
            if searches >= max_searches:
                print("search budget reached; rerun to continue")
                return 0
            rec = {"event": ev["event"], "domain": ev.get("domain"), "lang": m["lang"], "country": m.get("country"),
                   "query": m["youtube_query"], "start": str(start), "end": str(end),
                   "must": m.get("must"), "wiki_title": m.get("wikipedia_title"), "wiki": wiki(m["lang"].split("-")[0], m.get("wikipedia_title"), start, end)}
            try:
                for wait in (60, 120, 240, 0):            # HTTP 429 is a short-term rate limit: back off and retry
                    try:
                        rec["yt"] = yt_cell(yt, m["youtube_query"], m["lang"], start, end)
                        break
                    except Exception as error:  # noqa: BLE001
                        if " 429 " not in f" {error} " and "429" not in str(error)[:40] or not wait:
                            raise
                        print(f"rate limited; retrying in {wait}s")
                        import time
                        time.sleep(wait)
                searches += 1
            except Exception as error:  # noqa: BLE001
                msg = str(error)
                print(f"YouTube error for {ev['event']} [{m['lang']}]: {msg[:600]}")
                if "quotaexceeded" in msg.lower().replace(" ", ""):   # the real daily limit (HTTP 403)
                    return 2
                continue
            out.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            done += 1
            y = rec["yt"]
            print(f"{ev['event'][:40]:40} {m['lang']:5} streams {y['n_streams']:3} views {y['total_views']:>10,} "
                  f"top3 {y['top3_channel_share']} big {y['big_share']} small {y['small_share']} "
                  f"wiki-spike {(rec['wiki'] or {}).get('spike')}")
    print(f"done: {done} cells ({searches} new searches)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
