"""Build the market-gaps report page from results.json (filtered measurements)."""
import html
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "report" / "market-gaps.html"
rows = [r for r in json.load(open(HERE / "results.json", encoding="utf-8")) if r["total_views"] >= 10000]
DOM = {"hazard": ("Weather and natural hazards", "c1", "circle"), "politics": ("Politics", "c2", "square"),
       "conflict": ("War, violence and unrest", "c3", "triangle"), "other": ("Space, markets, outages, health", "c4", "diamond")}
LANG = {"en": "English", "es": "Spanish", "pt": "Portuguese", "it": "Italian", "fr": "French", "ja": "Japanese", "zh-Hant": "Chinese (Taiwan)",
        "tl": "Tagalog", "hi": "Hindi", "te": "Telugu", "bn": "Bengali", "th": "Thai", "ko": "Korean", "hu": "Hungarian"}
X0, X1, Y0, Y1 = 70, 740, 24, 384
LX0, LX1 = 4.0, 8.3
sx = lambda v: X0 + (math.log10(max(v, 10 ** LX0)) - LX0) / (LX1 - LX0) * (X1 - X0)
sy = lambda p: Y1 - (p or 0) * (Y1 - Y0)
esc = lambda s: html.escape(str(s or ""), quote=True)


def mark(shape, x, y, cls):
    if shape == "circle":
        return f'<circle class="pt {cls}" cx="{x:.1f}" cy="{y:.1f}" r="5"'
    if shape == "square":
        return f'<rect class="pt {cls}" x="{x - 4.5:.1f}" y="{y - 4.5:.1f}" width="9" height="9" rx="1.5"'
    if shape == "triangle":
        return f'<polygon class="pt {cls}" points="{x:.1f},{y - 6:.1f} {x + 5.6:.1f},{y + 4:.1f} {x - 5.6:.1f},{y + 4:.1f}"'
    return f'<polygon class="pt {cls}" points="{x:.1f},{y - 6:.1f} {x + 6:.1f},{y:.1f} {x:.1f},{y + 6:.1f} {x - 6:.1f},{y:.1f}"'


pts = []
for r in sorted(rows, key=lambda r: -r["total_views"]):
    name, cls, shape = DOM[r["domain"]]
    x, y = sx(r["total_views"]), sy(r["small_share"])
    best = (f'{r["best_small_views"]:,} views · {r["best_small_channel"]} ({r["best_small_subs"]:,} subs)' if r["best_small_views"] else "none")
    tip = (f'{r["event"]} · {LANG.get(r["lang"], r["lang"])}|{r["total_views"]:,} live-stream views in {r["streams"]} streams|'
           f'{(r["small_share"] or 0) * 100:.0f}% to channels under 100k subs · {(r["big_share"] or 0) * 100:.0f}% to channels over 1M|'
           f'Best small-channel stream: {best}')
    pts.append(f'{mark(shape, x, y, cls)} tabindex="0" data-tip="{esc(tip)}"><title>{esc(tip.replace("|", ". "))}</title></{"circle" if shape == "circle" else "rect" if shape == "square" else "polygon"}>')

LABELS = [  # (text, x, y, anchor)
    ("Honduras vote count (es)", 430, 135, "start"), ("Italy referendum (it)", 324, 182, "end"), ("Aurora storm (en)", 292, 212, "start"),
    ("Lunar eclipse (ja)", 441, 257, "start"), ("Champi (tl)", 433, 292, "start"), ("Champi (ja), our 10%", 296, 323, "end"),
    ("Iran war (en)", 623, 364, "middle"), ("Brazil vote (pt)", 738, 350, "end"), ("Cloudflare outage (en)", 101, 58, "start")]
labels = "".join(f'<text class="dl" x="{x}" y="{y}" text-anchor="{a}">{esc(t)}</text>' for t, x, y, a in LABELS)
gx = "".join(f'<line class="grid" x1="{sx(v):.1f}" y1="{Y0}" x2="{sx(v):.1f}" y2="{Y1}"/><text class="tick" x="{sx(v):.1f}" y="{Y1 + 18}" text-anchor="middle">{t}</text>'
             for v, t in ((1e4, "10k"), (1e5, "100k"), (1e6, "1M"), (1e7, "10M"), (1e8, "100M")))
gy = "".join(f'<line class="grid" x1="{X0}" y1="{sy(p):.1f}" x2="{X1}" y2="{sy(p):.1f}"/><text class="tick" x="{X0 - 8}" y="{sy(p) + 4:.1f}" text-anchor="end">{int(p * 100)}%</text>'
             for p in (0, .25, .5, .75, 1))
qx, qy = sx(3e5), sy(.25)
svg = f'''<svg class="chart" viewBox="0 0 760 430" role="img" aria-label="Scatter of {len(rows)} event-and-language markets: live-stream views against the share that went to small channels. Most war and politics markets sit at the bottom right, where big channels take nearly everything; vote counts in Honduras and Italy, eclipses, aurora storms and typhoons in Japanese and Tagalog sit in the open upper area.">
<rect class="open" x="{qx:.1f}" y="{Y0}" width="{X1 - qx:.1f}" height="{qy - Y0:.1f}"/>
<text class="openlbl" x="{X1 - 8}" y="{Y0 + 16}" text-anchor="end">big audience, small channels win</text>
{gx}{gy}
<line class="axis" x1="{X0}" y1="{Y1}" x2="{X1}" y2="{Y1}"/>
<text class="axt" x="{(X0 + X1) / 2}" y="{Y1 + 40}" text-anchor="middle">Live-stream views on the event (log scale)</text>
<text class="axt" x="16" y="{(Y0 + Y1) / 2}" text-anchor="middle" transform="rotate(-90 16 {(Y0 + Y1) / 2})">Share of views won by channels under 100k subscribers</text>
{''.join(pts)}
{labels}
</svg>'''

legend = "".join(f'<span class="lg"><svg width="14" height="14" viewBox="-7 -7 14 14" aria-hidden="true">'
                 f'{mark(shape, 0, 0, cls)}/></svg>{esc(name)}</span>' for name, cls, shape in DOM.values())

def best_cell(r):
    if not r["best_small_views"]:
        return "none"
    return f'{r["best_small_views"]:,} · {r["best_small_channel"]} ({r["best_small_subs"]:,} subs)'


table_rows = "".join(
    f'<tr><td>{esc(r["event"])}</td><td>{esc(LANG.get(r["lang"], r["lang"]))}</td><td>{esc(DOM[r["domain"]][0])}</td>'
    f'<td class="n">{r["streams"]}</td><td class="n">{r["total_views"]:,}</td><td class="n">{(r["small_share"] or 0) * 100:.0f}%</td>'
    f'<td class="n">{(r["big_share"] or 0) * 100:.0f}%</td><td>{esc(best_cell(r))}</td></tr>'
    for r in sorted(rows, key=lambda r: -(r["total_views"] * (r["small_share"] or 0))))

page = (HERE / "report_template.html").read_text(encoding="utf-8")
page = page.replace("{{SVG}}", svg).replace("{{LEGEND}}", legend).replace("{{TABLE}}", table_rows).replace("{{N}}", str(len(rows)))
OUT.write_text(page, encoding="utf-8")
print(OUT, len(page) // 1024, "KB,", len(rows), "points")
