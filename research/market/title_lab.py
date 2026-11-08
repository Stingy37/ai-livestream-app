"""Title experiment on live streams: rotate titles on a schedule and measure our share of the live market.

    python title_lab.py plan.json                  # run: rotate titles, sample viewers every few minutes (detach it)
    python title_lab.py plan.json --report         # per-title results from the samples so far

plan.json:
  {"out": "title_lab/<name>", "rotate_min": 60, "sample_s": 300, "panel_every_min": 180, "panel_queries": "arnab_panel.json",
   "streams": {"india-te": {"state": ".run/youtube/india_te.json", "title_file": ".run/youtube/title_india-te.txt",
                            "panel_lang": "te", "variants": {"T1": "title ...", ...}}}}

Titles go through the launcher's YOUTUBE_TITLE_FILE (scripts/youtube_live.py applies a changed file within a minute), so
nothing else writes the video. {RED} in a title is filled from the stream's desk.json (IMD red-alert districts in Andhra
Pradesh on the worst coming day). One stream per language with rotating titles, never parallel copies of a stream:
duplicate live streams from one channel risk YouTube's spam policy and would compete with each other.

The metric is share = our concurrent viewers / the panel's (live competitor streams for the same query), averaged over
each title period after a settling time, so the night-and-morning swing of the whole market cancels out.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))
from broadcast import youtube  # noqa: E402
import live_now  # noqa: E402

SETTLE_MIN = 10          # samples this soon after a title change are left out of the report


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def red_count(desk_path: Path) -> int | None:
    try:
        days = json.loads(desk_path.read_text(encoding="utf-8"))["in"]["districts_days"]["Andhra Pradesh"]
    except (OSError, ValueError, KeyError):
        return None
    today = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")
    per_day: dict[str, int] = {}
    for entries in days.values():
        for e in entries or []:
            if e.get("date", "") >= today and e.get("colour") == "red":
                per_day[e["date"]] = per_day.get(e["date"], 0) + 1
    return max(per_day.values()) if per_day else None


def append(path: Path, row: dict) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def refresh_panel(yt, plan: dict, out: Path) -> dict[str, list[str]]:
    """Live competitor streams per language (search.list: 100 units per query)."""
    queries = json.loads((HERE / plan.get("panel_queries", "arnab_panel.json")).read_text(encoding="utf-8"))
    panel: dict[str, list[str]] = {}
    for q in queries:
        snap = live_now.snapshot(yt, q)
        panel[q["lang"]] = [r["id"] for r in snap["rows"]]
        for r in snap["rows"]:
            append(out / "panel_members.csv", {"utc": now(), "lang": q["lang"], "video_id": r["id"], "channel": r["channel"],
                                               "subs": r["subs"], "title": r["title"]})
    return panel


def run(plan: dict) -> None:
    out = HERE / plan["out"]
    out.mkdir(parents=True, exist_ok=True)
    yt = youtube.service()
    streams = plan["streams"]
    order = {sid: list(s["variants"]) for sid, s in streams.items()}
    rotate_s, sample_s = plan.get("rotate_min", 60) * 60, plan.get("sample_s", 300)
    panel, next_panel, next_rotate, k, ended = {}, 0.0, 0.0, 0, 0
    current: dict[str, str] = {}
    video: dict[str, str] = {}
    while True:
        t = time.time()
        for sid, s in streams.items():           # the broadcast id appears once the launcher has created it
            if sid not in video:
                try:
                    video[sid] = json.loads((REPO / s["state"]).read_text(encoding="utf-8"))["broadcast_id"]
                except (OSError, ValueError, KeyError):
                    pass
        if t >= next_rotate:
            next_rotate = t + rotate_s
            for sid, s in streams.items():
                var = order[sid][k % len(order[sid])]
                title = s["variants"][var]
                if "{RED}" in title:
                    n = red_count(REPO / s.get("desk", "output/desk/india-te/desk.json"))
                    if n is None:                 # no number to show: keep the current title, out of the comparison
                        append(out / "errors.csv", {"utc": now(), "where": "red", "error": f"{sid}: no red-alert count for {var}"})
                        current[sid] = ""
                        continue
                    title = title.replace("{RED}", str(n))
                (REPO / s["title_file"]).write_text(title + "\n", encoding="utf-8")
                current[sid] = var
                append(out / "periods.csv", {"utc": now(), "stream": sid, "variant": var, "title": title})
            k += 1
        if t >= next_panel:
            next_panel = t + plan.get("panel_every_min", 180) * 60
            try:
                panel = refresh_panel(yt, plan, out)
            except Exception as e:  # noqa: BLE001 - keep the last panel (quota, network)
                append(out / "errors.csv", {"utc": now(), "where": "panel", "error": str(e)[:300]})
        ids = list(video.values()) + [i for v in panel.values() for i in v]
        try:
            items = []
            for i in range(0, len(ids), 50):
                items += yt.videos().list(part="snippet,statistics,liveStreamingDetails", id=",".join(ids[i:i + 50])).execute()["items"]
        except Exception as e:  # noqa: BLE001
            append(out / "errors.csv", {"utc": now(), "where": "sample", "error": str(e)[:300]})
            yt = youtube.service()
            items = []
        by_id = {it["id"]: it for it in items}
        stamp = now()
        for sid, vid in video.items():
            it = by_id.get(vid, {})
            ld, st = it.get("liveStreamingDetails", {}), it.get("statistics", {})
            append(out / "samples.csv", {"utc": stamp, "stream": sid, "video_id": vid, "variant": current.get(sid, ""),
                                         "live": (it.get("snippet") or {}).get("liveBroadcastContent", ""),
                                         "concurrent": ld.get("concurrentViewers", ""), "views": st.get("viewCount", ""),
                                         "likes": st.get("likeCount", "")})
        for lang, vids in panel.items():                 # our own stream may show up in the search: never part of the market
            live = [by_id[v] for v in vids if v in by_id and v not in video.values() and by_id[v]["snippet"].get("liveBroadcastContent") == "live"]
            append(out / "panel.csv", {"utc": stamp, "lang": lang, "streams": len(live),
                                       "concurrent": sum(int(v.get("liveStreamingDetails", {}).get("concurrentViewers", 0) or 0) for v in live)})
        states = [(by_id.get(v, {}).get("snippet") or {}).get("liveBroadcastContent") for v in video.values()]
        ended = ended + 1 if video and len(video) == len(streams) and all(x == "none" for x in states) else 0
        if (REPO / ".run" / "STOP_TITLE_LAB").exists() or ended >= 3:     # stopped by hand, or every broadcast is over
            return
        time.sleep(max(5.0, sample_s - (time.time() - t)))


def report(plan: dict) -> None:
    out = HERE / plan["out"]
    rows = list(csv.DictReader((out / "samples.csv").open(encoding="utf-8"))) if (out / "samples.csv").exists() else []
    panel = {(r["utc"], r["lang"]): int(r["concurrent"] or 0) for r in csv.DictReader((out / "panel.csv").open(encoding="utf-8"))} \
        if (out / "panel.csv").exists() else {}
    periods = list(csv.DictReader((out / "periods.csv").open(encoding="utf-8")))
    parse = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    for sid, s in plan["streams"].items():
        print(f"== {sid}")
        starts = [(parse(p["utc"]), p["variant"]) for p in periods if p["stream"] == sid]
        agg: dict[str, dict] = {}
        per: list[tuple[str, int, int]] = []
        for i, (t0, var) in enumerate(starts):
            t1 = starts[i + 1][0] if i + 1 < len(starts) else datetime(9999, 1, 1)
            ss = [r for r in rows if r["stream"] == sid and t0 + timedelta(minutes=SETTLE_MIN) <= parse(r["utc"]) < t1 and r["live"] == "live"]
            ours = [int(r["concurrent"] or 0) for r in ss]
            mkt = [panel.get((r["utc"], s["panel_lang"]), 0) for r in ss]
            views = [int(r["views"] or 0) for r in ss if r["views"]]
            hours = (parse(ss[-1]["utc"]) - parse(ss[0]["utc"])).total_seconds() / 3600 if len(ss) > 1 else 0
            line = (f"  {t0:%H:%M}Z {var:3s} n={len(ss):2d}  ours {sum(ours)/max(1,len(ours)):6.1f}  market {sum(mkt)/max(1,len(mkt)):7.1f}"
                    f"  share {100*sum(ours)/max(1,sum(mkt)):5.2f}%  views/h {((views[-1]-views[0])/hours if hours and views else 0):6.1f}")
            print(line)
            a = agg.setdefault(var, {"ours": 0, "mkt": 0, "n": 0})
            a["ours"] += sum(ours); a["mkt"] += sum(mkt); a["n"] += len(ss)
            per.append((var, sum(ours), sum(mkt)))
        for var, a in sorted(agg.items()):
            print(f"  {var}: share {100*a['ours']/max(1,a['mkt']):5.2f}% over {a['n']} samples  | {s['variants'][var][:90]}")
        if len(agg) == 2:      # alternating arms: each period against its neighbouring periods of the other arm (market drift cancels)
            arm, other = sorted(agg)
            wins = pairs = 0
            for i, (var, o, m) in enumerate(per):
                nb = [per[j] for j in (i - 1, i + 1) if 0 <= j < len(per) and per[j][0] == other and per[j][2]]
                if var == arm and m and nb:
                    pairs += 1
                    wins += o / m > sum(x[1] for x in nb) / sum(x[2] for x in nb)
            print(f"  {arm} beat its neighbouring {other} periods in {wins}/{pairs}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    report(plan) if a.report else run(plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
