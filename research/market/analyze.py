"""Rank measured markets by how much live-stream attention reached small channels (< 100k subscribers).

    python analyze.py [--md]      # table to stdout; --md writes results.md and results.json too

small_views = total views x small-channel share: attention a newcomer can realistically compete for.
best_small  = the best single stream by a small channel: proof that a newcomer can win it.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHES = [HERE / c for c in (sys.argv[sys.argv.index("--caches") + 1].split(",") if "--caches" in sys.argv else ["cache"])]
GENERIC = set("""live en vivo ao vivo em direto directo diretta in direct results result resultados resultado risultati résultats update
updates tonight today hoy now ngayon news latest 2025 2026 2027 the of in de del la el do da a e y na ng and on at for to com con per pour
streaming stream hindi english tracking tracker ライブ 直播 생중계 速報 開票速報 लाइव สด 在线 實況 現場 中継 生配信 resultat election elections
eleição eleições elecciones elezioni élections segunda vuelta turno""".split())

def anchors(query):
    import re
    toks = [t for t in re.split(r"[\s/|,]+", query.lower()) if t]
    return [t for t in toks if t not in GENERIC and (len(t) >= 3 or re.search(r"[^\x00-\x7f]", t))]

import re as _re
SCRIPT = {"ja": r"[\u3040-\u30ff]", "zh": r"[\u4e00-\u9fff]", "hi": r"[\u0900-\u097f]", "te": r"[\u0c00-\u0c7f]",
          "bn": r"[\u0980-\u09ff]", "th": r"[\u0e00-\u0e7f]", "ko": r"[\uac00-\ud7af]"}


def in_script(rows, lang):
    """For languages with their own script, keep streams whose titles are written in it (search's language hint leaks)."""
    pat = SCRIPT.get(lang.split("-")[0])
    return [r for r in rows if _re.search(pat, r["title"])] if pat else rows


def relevant(rows, query, must=None, lang=""):
    """Streams whose title names the event: any of the market's `must` terms, else every anchor of the query."""
    rows = in_script(rows, lang) if lang else rows
    if must:
        return [r for r in rows if any(t.lower() in r["title"].lower() for t in must)]
    a = anchors(query)
    return [r for r in rows if all(t in r["title"].lower() for t in a)] if a else rows

rows = []
seen = {}
for c in CACHES:
    for f in sorted(c.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        k = (r["event"], r["lang"], r["query"])
        old = seen.get(k)
        if old and (old.get("wiki") or {}).get("spike") is not None and (r.get("wiki") or {}).get("spike") is None:
            r["wiki"] = old["wiki"]                            # keep the earlier good Wikipedia figures
        seen[k] = r                                            # later caches (re-measured) win
for r in seen.values():
    y = dict(r.get("yt") or {})
    filtered = "rows" in y
    if filtered:                                               # keep only streams whose titles name the event
        rs = relevant(y["rows"], r["query"], r.get("must"), r["lang"])
        tot = sum(x["views"] for x in rs)
        sm = [x for x in rs if x["subs"] < 100_000]
        y.update(n_streams=len(rs), total_views=tot, small_share=(sum(x["views"] for x in sm) / tot) if tot else 0,
                 big_share=(sum(x["views"] for x in rs if x["subs"] >= 1_000_000) / tot) if tot else 0,
                 best_small=max(sm, key=lambda x: x["views"]) if sm else None, top=rs[:6])
    tot = y.get("total_views") or 0
    small = round(tot * (y.get("small_share") or 0))
    b = y.get("best_small") or {}
    w = r.get("wiki") or {}
    rows.append({"filtered": filtered, "event": r["event"], "domain": r.get("domain"), "lang": r["lang"], "country": r.get("country"), "query": r["query"],
                 "streams": y.get("n_streams"), "channels": y.get("n_channels"), "total_views": tot, "small_views": small,
                 "small_share": y.get("small_share"), "big_share": y.get("big_share"), "top3": y.get("top3_channel_share"),
                 "best_small_views": b.get("views"), "best_small_subs": b.get("subs"), "best_small_channel": b.get("channel"),
                 "best_small_title": b.get("title"), "wiki_peak": w.get("peak"), "wiki_spike": w.get("spike"),
                 "top": [(t["channel"], t["views"], t["subs"]) for t in y.get("top", [])[:3]]})
rows.sort(key=lambda r: -r["small_views"])
fmt = "{:<38} {:<7} {:>3} {:>12} {:>11} {:>6} {:>6} {:>10} {:>9}  {}"
print(fmt.format("event", "lang", "n", "total", "to-small", "small%", "big%", "best-small", "subs", "best small channel"))
for r in rows:
    print(fmt.format(("" if r["filtered"] else "~") + r["event"][:37], r["lang"], r["streams"] or 0, f'{r["total_views"]:,}', f'{r["small_views"]:,}',
                     f'{(r["small_share"] or 0) * 100:.0f}', f'{(r["big_share"] or 0) * 100:.0f}',
                     f'{(r["best_small_views"] or 0):,}', f'{(r["best_small_subs"] or 0):,}', (r["best_small_channel"] or "")[:28]))
if "--md" in sys.argv:
    (HERE / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(rows)} cells -> results.json")
