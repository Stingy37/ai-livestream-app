"""Charts for the results report (matplotlib). Every number is literal and listed in the report's sources section.

    python research/report/make_charts.py <fonts_dir> <election_health.json> <out_dir>

Palette: the validated reference palette (series blue + neutral context; status good/critical only for health states).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, PathPatch, Rectangle
from matplotlib.path import Path as MPath

FONTS, HEALTH, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
for f in FONTS.glob("*.ttf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams.update({"font.family": "Barlow", "font.size": 11.5, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.spines.bottom": False, "svg.fonttype": "none"})

SURFACE, INK, INK2, MUTED, GRID = "#ffffff", "#0b0b0b", "#52514e", "#74736e", "#e6e5e0"
OURS, THEIRS = "#2a78d6", "#bdbcb5"
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
W = 8.0                 # figure width in inches; shown at about 860 px, so 1 pt is roughly 1.5 px on screen
DPI = 220


def fig_for(h: float):
    return plt.figure(figsize=(W, h), facecolor=SURFACE, dpi=DPI)


def heading(fig, title: str, sub: str | None, h: float) -> None:
    fig.text(0.02, 1 - 0.30 / h, title, fontsize=16.5, fontweight=600, color=INK, va="center")
    if sub:
        fig.text(0.02, 1 - 0.60 / h, sub, fontsize=11.5, color=INK2, va="center")


def legend(fig, y: float, items: list[tuple[str, str]], x: float = 0.02) -> None:
    for color, label in items:
        fig.patches.append(Rectangle((x, y - 0.012), 0.016, 0.024, transform=fig.transFigure, facecolor=color, edgecolor="none"))
        t = fig.text(x + 0.023, y, label, fontsize=11, color=INK2, va="center")
        fig.canvas.draw()
        x = fig.transFigure.inverted().transform((t.get_window_extent().x1, 0))[0] + 0.03


def clean(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.tick_params(length=0)
    ax.set_xticks([])
    ax.set_yticks([])


def hbar(ax, y: float, w: float, h: float, color: str, x0: float = 0.0, radius_pt: float = 2.4, round_end: bool = True) -> None:
    """Horizontal bar: square at the baseline, softly rounded data end (radius in points, independent of the data scale)."""
    box = ax.get_window_extent()
    (x_lo, x_hi), (y_lo, y_hi) = ax.get_xlim(), ax.get_ylim()
    px_x, px_y = box.width / abs(x_hi - x_lo), box.height / abs(y_hi - y_lo)
    r_px = radius_pt * ax.figure.dpi / 72
    rx, ry = r_px / px_x, min(r_px / px_y, h / 2)
    y0, y1, x1 = y - h / 2, y + h / 2, x0 + w
    if not round_end or w <= rx * 1.2:
        ax.add_patch(Rectangle((x0, y0), w, h, facecolor=color, edgecolor="none"))
        return
    v = [(x0, y0), (x1 - rx, y0), (x1, y0), (x1, y0 + ry), (x1, y1 - ry), (x1, y1), (x1 - rx, y1), (x0, y1), (x0, y0)]
    c = [MPath.MOVETO, MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO, MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(v, c), facecolor=color, edgecolor="none"))


def save(fig, name: str) -> None:
    fig.savefig(OUT / f"{name}.png", facecolor=SURFACE, dpi=DPI)
    plt.close(fig)


# ---------- 1. head to head ----------
def head_to_head() -> None:
    groups = [("2026, AI-agent era", [
        ("ABP News", "51.4M subscribers · Cyclone Murasu", 49294, 38331, "1.3×"),
        ("Zee Telugu News", "3M subscribers · Cyclone Murasu", 49294, 40359, "1.2×"),
        ("Earth Uncut TV", "253K subscribers · Typhoon Champi, Japan", 17588, 6591, "2.7×"),
        ("CDN 37", "1.1M subscribers · US midterms, Spanish", 5001, 3609, "1.4×")]),
        ("2024 typhoon season", [
        ("Associated Press", "4.7M subscribers · Typhoon Krathon/Julian", 64625, 45617, "1.4×"),
        ("Firstpost", "9.8M subscribers · Typhoon Krathon/Julian", 64625, 28996, "2.2×"),
        ("Hindustan Times", "8.7M subscribers · Typhoon Yagi", 46043, 26718, "1.7×"),
        ("South China Morning Post", "4.4M subscribers · Typhoon Yagi", 46043, 38522, "1.2×"),
        ("TV5 News Philippines", "5.1M subscribers · Typhoon Kristine", 38204, 6917, "5.5×")])]
    row_in, group_in, top_in = 0.56, 0.40, 1.28
    n = sum(len(g[1]) for g in groups)
    h = top_in + n * row_in + group_in * len(groups) + 0.15
    fig = fig_for(h)
    heading(fig, "With under 4,500 subscribers, we outdrew major news brands", "Live-stream views on the same storm or race. Each row compares our stream with that outlet's top stream.", h)
    legend(fig, 1 - 0.92 / h, [(OURS, "Our live stream"), (THEIRS, "Their top live stream")])
    ax = fig.add_axes([0.385, 0.012, 0.545, 1 - top_in / h - 0.012])
    clean(ax)
    total = n * row_in + group_in * len(groups)
    ax.set_xlim(0, 78000)
    ax.set_ylim(total, 0)
    fig.canvas.draw()
    y = 0.0
    bar = 0.19
    for gname, rows in groups:
        y += group_in
        ax.text(-0.67 * 78000, y - 0.13, gname.upper(), fontsize=10.5, fontweight=600, color=INK2, va="center", clip_on=False)
        ax.plot([-0.67 * 78000, 78000 * 1.095], [y - 0.01, y - 0.01], color=GRID, lw=0.8, clip_on=False, solid_capstyle="butt")
        for name, sub, ours, theirs, mult in rows:
            c = y + row_in / 2
            hbar(ax, c - bar / 2 - 0.012, ours, bar, OURS)
            hbar(ax, c + bar / 2 + 0.012, theirs, bar, THEIRS)
            ax.text(ours + 860, c - bar / 2 - 0.012, f"{ours:,}", fontsize=10.5, fontweight=600, color=INK, va="center")
            ax.text(theirs + 860, c + bar / 2 + 0.012, f"{theirs:,}", fontsize=10.5, color=INK2, va="center")
            ax.text(-0.67 * 78000, c - 0.1, name, fontsize=12, fontweight=600, color=INK, va="center", clip_on=False)
            ax.text(-0.67 * 78000, c + 0.11, sub, fontsize=9.5, color=INK2, va="center", clip_on=False)
            ax.text(78000 * 1.095, c, mult, fontsize=13.5, fontweight=700, color=INK, va="center", ha="right", clip_on=False)
            y += row_in
    save(fig, "head_to_head")


# ---------- 2. best small channel ----------
def small_channels() -> None:
    panels = [("Typhoon Kristine, 2024", "#1 of 32 small channels", [38204, 23402, 14650, 13993, 11177]),
              ("Typhoon Yagi, 2024", "#1 of 12 small channels", [46043, 14647, 1837, 863, 370]),
              ("Typhoon Champi in Japan, 2026", "#1 of 16 small channels", [17588, 13488, 5094, 3069, 2408])]
    h = 3.25
    fig = fig_for(h)
    heading(fig, "The top small channel on three major storms", "Views on each channel's best live stream. Small means under 100,000 subscribers.", h)
    legend(fig, 1 - 0.92 / h, [(OURS, "Our channel"), (THEIRS, "Other small channels, by rank")])
    for i, (t, s, vals) in enumerate(panels):
        ax = fig.add_axes([0.02 + i * 0.327 + 0.05, 0.03, 0.195, 1 - 1.72 / h])
        clean(ax)
        ax.set_xlim(0, 46043)
        ax.set_ylim(5, 0)
        fig.canvas.draw()
        ax.text(-0.25 * 46043, -0.95, t, fontsize=11.5, fontweight=600, color=INK, va="center", clip_on=False)
        ax.text(-0.25 * 46043, -0.42, s, fontsize=10.5, color=INK2, va="center", clip_on=False)
        for j, v in enumerate(vals):
            hbar(ax, j + 0.5, v, 0.56, OURS if j == 0 else THEIRS)
            ax.text(-0.04 * 46043, j + 0.5, "Us" if j == 0 else f"#{j + 1}", fontsize=10.5, fontweight=600 if j == 0 else 400, color=INK if j == 0 else INK2, ha="right", va="center", clip_on=False)
            ax.text(v + 900, j + 0.5, f"{v:,}", fontsize=10, fontweight=600 if j == 0 else 400, color=INK if j == 0 else INK2, va="center", clip_on=False)
    save(fig, "small_channels")


# ---------- 3. count of wins ----------
def wins() -> None:
    rows = [("Cyclone Murasu, 2026", 43), ("Typhoon Krathon/Julian, 2024", 27), ("Typhoon Yagi, 2024", 21), ("Typhoon Kristine, 2024", 18),
            ("Typhoon Man-yi/Pepito, 2024", 18), ("Typhoon Kong-rey/Leon, 2024", 7), ("US midterms in Spanish, 2026", 1)]
    h = 3.65
    fig = fig_for(h)
    heading(fig, "135 live streams from channels with 1M+ subscribers fell below ours", "Count of streams that drew fewer views than our best stream on each event.", h)
    ax = fig.add_axes([0.335, 0.03, 0.60, 1 - 0.85 / h - 0.03])
    clean(ax)
    ax.set_xlim(0, 47)
    ax.set_ylim(len(rows), 0)
    fig.canvas.draw()
    for i, (n, v) in enumerate(rows):
        hbar(ax, i + 0.5, v, 0.56, OURS)
        ax.text(v + 0.6, i + 0.5, str(v), fontsize=11.5, fontweight=600, color=INK, va="center")
        ax.text(-1, i + 0.5, n, fontsize=11.5, color=INK, va="center", ha="right", clip_on=False)
    save(fig, "wins")


# ---------- 4. audience efficiency ----------
def efficiency() -> None:
    rows = [("ABS-CBN", "Typhoon Kristine", 8.7, 0.03, "280×"), ("TBS", "US midterms in Japanese", 2.6, 0.16, "16×"),
            ("NTV", "Cyclone Murasu", 11.2, 1.3, "9×"), ("Telemundo", "US midterms in Spanish", 1.2, 0.15, "8×")]
    row_in, top_in = 0.62, 1.28
    h = top_in + row_in * len(rows) + 0.1
    fig = fig_for(h)
    heading(fig, "More views per subscriber than the biggest networks", "Live-stream views divided by the channel's subscriber count, on one stream each.", h)
    legend(fig, 1 - 0.92 / h, [(OURS, "Our stream"), (THEIRS, "Their stream")])
    ax = fig.add_axes([0.28, 0.02, 0.62, row_in * len(rows) / h])
    clean(ax)
    ax.set_xlim(0, 13)
    ax.set_ylim(len(rows), 0)
    fig.canvas.draw()
    for i, (n, s, o, t, m) in enumerate(rows):
        hbar(ax, i + 0.5 - 0.17, o, 0.31, OURS)
        hbar(ax, i + 0.5 + 0.17, t, 0.31, THEIRS)
        ax.text(o + 0.15, i + 0.5 - 0.17, f"{o:g}", fontsize=10.5, fontweight=600, color=INK, va="center")
        ax.text(t + 0.15, i + 0.5 + 0.17, f"{t:g}", fontsize=10.5, color=INK2, va="center")
        ax.text(-5.45, i + 0.5 - 0.17, n, fontsize=12, fontweight=600, color=INK, va="center", clip_on=False)
        ax.text(-5.45, i + 0.5 + 0.2, s, fontsize=9.5, color=INK2, va="center", clip_on=False)
        ax.text(13 * 1.115, i + 0.5, m, fontsize=13.5, fontweight=700, color=INK, va="center", ha="right", clip_on=False)
    save(fig, "efficiency")


# ---------- 5. uptime ----------
def uptime() -> None:
    rows = [("Typhoon Champi", "Oct 20–23 · 6 broadcasts", 49.6, 2.2, "95.8%"), ("Cyclone Arnab", "Oct 26–27 · 5 broadcasts", 25.1, 0, "100%"),
            ("Cyclone Murasu", "Nov 2–3 · 4 broadcasts", 46.3, 0.9, "98.2%"), ("US midterms", "Nov 3–4 · 3 broadcasts", 33.0, 0, "100%")]
    h = 3.45
    fig = fig_for(h)
    heading(fig, "98% uptime across 157 broadcast hours, and 100% on election night", "Hours on air by event, added across simultaneous streams.", h)
    legend(fig, 1 - 0.92 / h, [(OURS, "On air"), (CRITICAL, "Outage")])
    ax = fig.add_axes([0.245, 0.03, 0.50, 1 - 1.25 / h - 0.03])
    clean(ax)
    ax.set_xlim(0, 54)
    ax.set_ylim(len(rows), 0)
    fig.canvas.draw()
    for i, (n, s, on, off, pct) in enumerate(rows):
        hbar(ax, i + 0.5, on, 0.5, OURS, round_end=not off)
        if off:
            hbar(ax, i + 0.5, off - 0.1, 0.5, CRITICAL, x0=on + 0.1)
        ax.text(on + off + 0.6, i + 0.5, f"{on + off:.1f} h" + (f"  ({off:.1f} h outage)" if off else ""), fontsize=10.5, color=INK2, va="center")
        ax.text(-24.3, i + 0.5 - 0.15, n, fontsize=12, fontweight=600, color=INK, va="center", clip_on=False)
        ax.text(-24.3, i + 0.5 + 0.2, s, fontsize=9.5, color=INK2, va="center", clip_on=False)
        ax.text(54 * 1.47, i + 0.5, pct, fontsize=14, fontweight=700, color=INK, va="center", ha="right", clip_on=False)
    save(fig, "uptime")


# ---------- 6. election-night health strip ----------
def strip() -> None:
    data = json.loads(HEALTH.read_text())
    names = [("es", "Spanish"), ("ja", "Japanese"), ("zh", "Chinese")]
    et = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M") - timedelta(hours=5)
    h = 2.95
    fig = fig_for(h)
    heading(fig, "Election night: 198 of 198 stream health checks passed", "Three simultaneous 11-hour broadcasts, checked every 10 minutes. No encoder restarts. Times are US Eastern.", h)
    legend(fig, 1 - 0.92 / h, [(GOOD, "Rated healthy by YouTube (no failed checks)")])
    ax = fig.add_axes([0.115, 0.135, 0.865, 1 - 1.72 / h])
    ax.set_facecolor(SURFACE)
    t0, t1 = datetime(2026, 11, 3, 20, 15), datetime(2026, 11, 4, 7, 35)
    ax.set_xlim(t0, t1)
    ax.set_ylim(3, 0)
    for i, (k, label) in enumerate(names):
        for row in data[k]:
            x = mdates.date2num(et(row[0]))
            ax.add_patch(Rectangle((x - 0.0016, i + 0.14), 0.0032, 0.72, facecolor=GOOD if row[2] in ("good", "ok") else CRITICAL, edgecolor="none"))
        ax.text(-0.012, i + 0.5, label, transform=ax.get_yaxis_transform(), fontsize=11.5, fontweight=600, color=INK, va="center", ha="right")
    for when, txt in [(datetime(2026, 11, 3, 21, 0), "9 pm: TX, KS and MI polls closed"), (datetime(2026, 11, 4, 1, 0), "1 am: Alaska polls closed")]:
        ax.plot([when, when], [-0.05, 3], color=INK2, lw=0.8, solid_capstyle="butt", clip_on=False)
        ax.text(when, -0.13, txt, fontsize=10, color=INK2, ha="left", va="bottom", clip_on=False)
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[21, 23, 1, 3, 5, 7]))
    ax.xaxis.set_major_formatter(lambda v, _=None: mdates.num2date(v).strftime("%-I %p").lower().replace(" ", " "))
    ax.set_yticks([])
    ax.tick_params(axis="x", length=0, colors=INK2, labelsize=10.5, pad=5)
    save(fig, "election_strip")


# ---------- 7. quality funnel ----------
def funnel() -> None:
    rows = [("Drafts written", 2747, "#86b6ef"), ("Scripts sent to final inspection", 967, "#5598e7"), ("Passed and published", 886, OURS)]
    h = 2.5
    fig = fig_for(h)
    heading(fig, "92% of scripts passed inspection; 8% were stopped before air", "Election night, all three streams. When a script failed, the last approved version stayed on air.", h)
    ax = fig.add_axes([0.335, 0.05, 0.60, 1 - 0.9 / h - 0.05])
    clean(ax)
    ax.set_xlim(0, 3100)
    ax.set_ylim(len(rows), 0)
    fig.canvas.draw()
    for i, (n, v, c) in enumerate(rows):
        hbar(ax, i + 0.5, v, 0.56, c)
        ax.text(v + 35, i + 0.5, f"{v:,}", fontsize=12, fontweight=600, color=INK, va="center")
        ax.text(-70, i + 0.5, n, fontsize=11.5, color=INK, va="center", ha="right", clip_on=False)
    save(fig, "funnel")


# ---------- 8. languages ----------
def languages() -> None:
    rows = [("English", "Jun 2021", datetime(2021, 6, 30)), ("Chinese", "Jul 2024", datetime(2024, 7, 25)), ("Japanese", "Aug 2024", datetime(2024, 8, 25)),
            ("Vietnamese", "Sep 2024", datetime(2024, 9, 7)), ("Telugu", "Oct 2026", datetime(2026, 10, 26)), ("Tamil", "Oct 2026", datetime(2026, 10, 26)),
            ("Spanish", "Nov 2026", datetime(2026, 11, 4))]
    h = 3.65
    fig = fig_for(h)
    heading(fig, "From one language to seven", "Date of the first live stream in each language.", h)
    ax = fig.add_axes([0.135, 0.115, 0.76, 1 - 0.85 / h - 0.115])
    ax.set_facecolor(SURFACE)
    x0, x1 = datetime(2020, 7, 1), datetime(2027, 1, 1)
    ax.set_xlim(x0, x1)
    ax.set_ylim(len(rows), 0)
    for i, (n, d, when) in enumerate(rows):
        ax.plot([x0, x1], [i + 0.5, i + 0.5], color=GRID, lw=0.8, solid_capstyle="butt", zorder=0)
        ax.plot([when], [i + 0.5], "o", ms=8, color=OURS, mec=SURFACE, mew=1.5, zorder=2)
        ax.text(-0.012, i + 0.5, n, transform=ax.get_yaxis_transform(), fontsize=11.5, fontweight=600, color=INK, va="center", ha="right")
        ax.annotate(d, (when, i + 0.5), xytext=(-9, 0), textcoords="offset points", fontsize=10, color=INK2, va="center", ha="right")
    ax.set_yticks([])
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", length=0, colors=INK2, labelsize=10.5)
    save(fig, "languages")


# ---------- 9. output ----------
def output() -> None:
    rows = [("2021–22", "24 broadcasts", 53.9, THEIRS), ("2024 season", "35 broadcasts", 98.8, THEIRS), ("Oct 20–Nov 4, 2026", "18 broadcasts in 15 days", 156.8, OURS)]
    h = 2.55
    fig = fig_for(h)
    heading(fig, "157 broadcast hours in 15 days, more than in all of 2024", "Live broadcast hours by period, added across simultaneous streams.", h)
    ax = fig.add_axes([0.28, 0.04, 0.63, 1 - 0.85 / h - 0.04])
    clean(ax)
    ax.set_xlim(0, 180)
    ax.set_ylim(len(rows), 0)
    fig.canvas.draw()
    for i, (n, s, v, c) in enumerate(rows):
        hbar(ax, i + 0.5, v, 0.5, c)
        ax.text(v + 2, i + 0.5, f"{round(v)} h", fontsize=12, fontweight=600, color=INK, va="center")
        ax.text(-74, i + 0.5 - 0.14, n, fontsize=11.5, fontweight=600, color=INK, va="center", clip_on=False)
        ax.text(-74, i + 0.5 + 0.2, s, fontsize=9.5, color=INK2, va="center", clip_on=False)
    save(fig, "output")


# ---------- 10. countries ----------
def countries() -> None:
    rows = [("Philippines", 370330), ("India", 68887), ("Japan", 45619), ("Taiwan", 25444), ("Vietnam", 7967), ("United States", 6233)]
    h = 3.15
    fig = fig_for(h)
    heading(fig, "An audience in 41 countries", "Views by country, top six. Weather streams only; election geography is not yet reported.", h)
    ax = fig.add_axes([0.2, 0.03, 0.72, 1 - 0.85 / h - 0.03])
    clean(ax)
    ax.set_xlim(0, 420000)
    ax.set_ylim(len(rows), 0)
    fig.canvas.draw()
    for i, (n, v) in enumerate(rows):
        hbar(ax, i + 0.5, v, 0.56, OURS)
        ax.text(v + 4000, i + 0.5, f"{v:,}", fontsize=11.5, fontweight=600, color=INK, va="center")
        ax.text(-8000, i + 0.5, n, fontsize=11.5, color=INK, va="center", ha="right", clip_on=False)
    save(fig, "countries")


# ---------- 11. market size ----------
def markets() -> None:
    rows = [("Cyclone Murasu, India", 18.652, "2026"), ("Typhoon Champi, Taiwan", 15.719, "2026"), ("Typhoon Man-yi/Pepito", 11.045, "2024"), ("US midterms, Spanish", 10.045, "2026"),
            ("US midterms, Japanese", 4.735, "2026"), ("US midterms, Chinese", 4.413, "2026"), ("Typhoon Yagi", 4.024, "2024"), ("Typhoon Krathon/Julian", 2.948, "2024"),
            ("Typhoon Kristine", 2.529, "2024"), ("Typhoon Kong-rey/Leon", 1.023, "2024"), ("Typhoon Champi, Japan", 0.324, "2026")]
    h = 4.75
    fig = fig_for(h)
    heading(fig, "About 75 million live-stream views across the events we covered", "All live streams we could measure on each event. Our share is about 0.7%, so there is room to grow.", h)
    ax = fig.add_axes([0.3, 0.02, 0.62, 1 - 0.85 / h - 0.02])
    clean(ax)
    ax.set_xlim(0, 21)
    ax.set_ylim(len(rows), 0)
    fig.canvas.draw()
    for i, (n, v, _y) in enumerate(rows):
        hbar(ax, i + 0.5, v, 0.56, OURS)
        ax.text(v + 0.25, i + 0.5, f"{v:.1f}M", fontsize=11, fontweight=600, color=INK, va="center")
        ax.text(-0.4, i + 0.5, n, fontsize=11.5, color=INK, va="center", ha="right", clip_on=False)
    save(fig, "markets")


# ---------- 12. the stack, as an assembly line ----------
def stack() -> None:
    rows = [("Demand planning", "Size each market by event and language before launch", "YouTube Data API, Wikimedia pageviews", False),
            ("Sourcing", "Agents search the web and official agencies, then pull full articles", "LangGraph agents, SearXNG, Trafilatura", False),
            ("Inbound inspection", "Score every source and flag facts that conflict", "Source scoring, NER and NLI fact-check models", False),
            ("Knowledge store", "Index verified facts so writers retrieve only what they need", "e5 embeddings, FAISS, official data feeds", True),
            ("Production", "Write scripts in each language, looking up facts while writing", "DeepSeek V4 Flash, Qwen3-8B with an RL-trained retrieval model", True),
            ("Final inspection", "Block unsupported numbers, loaded wording and unattributed claims", "Rule-based checks plus an LLM reviewer", False),
            ("Packaging", "Voice each sentence and sync the graphics to the narration", "Kokoro, Parler and MMS voices; HTML and D3 graphics", False),
            ("Distribution", "Encode and ship live broadcasts", "Chromium, FFmpeg, YouTube Live API, AWS EC2 and S3", False)]
    row_in, top_in, ctrl_in = 0.60, 1.05, 0.72
    h = top_in + row_in * len(rows) + ctrl_in + 0.2
    fig = fig_for(h)
    heading(fig, "The tech stack, as an assembly line", "Each stage does one job and hands off to the next. Dark stages are retrieval, where Andy's subteam focuses.", h)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(h, 0)
    ax.axis("off")
    ax.patch.set_alpha(0)
    ax.text(0.16, top_in - 0.1, "STAGE", fontsize=9.5, fontweight=600, color=MUTED, va="center")
    ax.text(2.02, top_in - 0.1, "WHAT IT DOES", fontsize=9.5, fontweight=600, color=MUTED, va="center")
    ax.text(5.12, top_in - 0.1, "TOOLS", fontsize=9.5, fontweight=600, color=MUTED, va="center")
    import textwrap
    for i, (stage, what, tools, mine) in enumerate(rows):
        y = top_in + row_in * i + row_in / 2
        ax.add_patch(FancyBboxPatch((0.16, y - 0.21), 1.68, 0.42, boxstyle="round,pad=0,rounding_size=0.05", facecolor=OURS if mine else "#eef3fb", edgecolor="none"))
        ax.text(1.0, y, stage, fontsize=11.5, fontweight=600, color="#ffffff" if mine else "#104281", ha="center", va="center")
        ax.text(2.02, y, textwrap.fill(what, 42), fontsize=10.5, color=INK, va="center", linespacing=1.15)
        ax.text(5.12, y, textwrap.fill(tools, 36), fontsize=10, color=INK2, va="center", linespacing=1.15)
        if i < len(rows) - 1:
            ax.annotate("", xy=(1.0, y + row_in - 0.2), xytext=(1.0, y + 0.22), arrowprops=dict(arrowstyle="-|>", color="#86b6ef", lw=1.2, shrinkA=0, shrinkB=0, mutation_scale=9))
    yc = top_in + row_in * len(rows) + ctrl_in / 2 + 0.03
    ax.add_patch(FancyBboxPatch((0.16, yc - 0.31), W - 0.32, 0.62, boxstyle="round,pad=0,rounding_size=0.05", facecolor="#f0efec", edgecolor="none"))
    ax.text(0.3, yc, "Control tower", fontsize=11.5, fontweight=700, color=INK, va="center")
    ax.text(2.02, yc, textwrap.fill("An AI agent watches every stage, restarts failures and verifies race calls", 42), fontsize=10.5, color=INK, va="center", linespacing=1.15)
    ax.text(5.12, yc, "Claude Code, monitoring scripts", fontsize=10, color=INK2, va="center")
    save(fig, "stack")


if __name__ == "__main__":
    for f in (head_to_head, small_channels, wins, efficiency, uptime, strip, funnel, languages, output, countries, markets, stack):
        f()
    print("charts written to", OUT)
