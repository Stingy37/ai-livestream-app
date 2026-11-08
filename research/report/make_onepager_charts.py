"""Compact charts for the one-page summary, drawn at their printed size so point sizes are true on paper.

    python research/report/make_onepager_charts.py <fonts_dir> <election_health.json> <out_dir>

Uses the same data, palette and bar shape as make_charts.py (same arguments, because it imports that module).
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from make_charts import CRITICAL, INK, INK2, OURS, OUT, SURFACE, THEIRS, hbar

DPI = 300
HERO_W, SIDE_W, THIRD_W = 4.54, 2.83, 2.39


def canvas(w: float, h: float):
    """A figure whose data coordinates are inches, measured from the top left."""
    fig = plt.figure(figsize=(w, h), facecolor=SURFACE, dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")
    fig.canvas.draw()
    return fig, ax


def save(fig, name: str) -> None:
    fig.savefig(OUT / f"{name}.png", facecolor=SURFACE, dpi=DPI)
    plt.close(fig)


def swatch(ax, x: float, y: float, color: str, label: str) -> None:
    ax.add_patch(Rectangle((x, y - 0.045), 0.09, 0.09, facecolor=color, edgecolor="none"))
    ax.text(x + 0.125, y, label, fontsize=7.5, color=INK2, va="center")


def head_to_head() -> None:
    rows = [("ABP News", "51.4M subs · Cyclone Murasu, 2026", 49294, 38331, "1.3×"),
            ("Firstpost", "9.8M subs · Typhoon Krathon/Julian, 2024", 64625, 28996, "2.2×"),
            ("TV5 News Philippines", "5.1M subs · Typhoon Kristine, 2024", 38204, 6917, "5.5×"),
            ("Associated Press", "4.7M subs · Typhoon Krathon/Julian, 2024", 64625, 45617, "1.4×"),
            ("South China Morning Post", "4.4M subs · Typhoon Yagi, 2024", 46043, 38522, "1.2×"),
            ("CDN 37", "1.1M subs · US midterms in Spanish, 2026", 5001, 3609, "1.4×")]
    top, row = 0.24, 0.345
    h = top + row * len(rows) + 0.02
    fig, ax = canvas(HERO_W, h)
    swatch(ax, 0, 0.07, OURS, "Our live stream")
    swatch(ax, 0.98, 0.07, THEIRS, "Their top live stream")
    ax.text(HERO_W, 0.07, "Our lead", fontsize=7.5, color=INK2, va="center", ha="right")
    x0, span, bar = 1.86, 1.92 / 64625, 0.118
    for i, (name, sub, ours, theirs, lead) in enumerate(rows):
        c = top + row * i + row / 2
        hbar(ax, c - bar / 2 - 0.008, ours * span, bar, OURS, x0=x0, radius_pt=1.6)
        hbar(ax, c + bar / 2 + 0.008, theirs * span, bar, THEIRS, x0=x0, radius_pt=1.6)
        ax.text(x0 + ours * span + 0.04, c - bar / 2 - 0.008, f"{ours:,}", fontsize=7.2, fontweight=600, color=INK, va="center")
        ax.text(x0 + theirs * span + 0.04, c + bar / 2 + 0.008, f"{theirs:,}", fontsize=7.2, color=INK2, va="center")
        ax.text(0, c - 0.062, name, fontsize=8.8, fontweight=600, color=INK, va="center")
        ax.text(0, c + 0.075, sub, fontsize=6.9, color=INK2, va="center")
        ax.text(HERO_W, c, lead, fontsize=10.5, fontweight=700, color=INK, va="center", ha="right")
    save(fig, "op_head_to_head")


def small_channels() -> None:
    rows = [("Typhoon Kristine, 2024", "#1 of 32", 38204, 23402), ("Typhoon Yagi, 2024", "#1 of 12", 46043, 14647),
            ("Typhoon Champi in Japan, 2026", "#1 of 16", 17588, 13488)]
    row = 0.455
    h = row * len(rows)
    fig, ax = canvas(SIDE_W, h)
    x0, span, bar = 0.24, 2.12 / 46043, 0.105
    for i, (name, rank, ours, next_best) in enumerate(rows):
        y = row * i
        ax.text(0, y + 0.075, name, fontsize=8, fontweight=600, color=INK, va="center")
        ax.text(SIDE_W, y + 0.075, rank, fontsize=8, fontweight=700, color=INK, va="center", ha="right")
        for j, (label, v, color, weight, ink) in enumerate([("Us", ours, OURS, 600, INK), ("#2", next_best, THEIRS, 400, INK2)]):
            c = y + 0.205 + j * (bar + 0.014)
            hbar(ax, c, v * span, bar, color, x0=x0, radius_pt=1.6)
            ax.text(0, c, label, fontsize=7.2, fontweight=weight, color=ink, va="center")
            ax.text(x0 + v * span + 0.04, c, f"{v:,}", fontsize=7.2, fontweight=weight, color=ink, va="center")
    save(fig, "op_small_channels")


def output() -> None:
    rows = [("2021–22", "24 broadcasts", 53.9, THEIRS), ("2024 season", "35 broadcasts", 98.8, THEIRS), ("Oct 20–Nov 4, 2026", "18 broadcasts", 156.8, OURS)]
    row, bar = 0.43, 0.135
    fig, ax = canvas(THIRD_W, row * len(rows))
    span = 1.98 / 156.8
    for i, (name, sub, v, color) in enumerate(rows):
        y = row * i
        t = ax.text(0, y + 0.09, name, fontsize=7.8, fontweight=600, color=INK, va="center")
        fig.canvas.draw()
        x_end = ax.transData.inverted().transform((t.get_window_extent().x1, 0))[0]
        ax.text(x_end + 0.05, y + 0.09, f"· {sub}", fontsize=7.2, color=INK2, va="center")
        hbar(ax, y + 0.26, v * span, bar, color, radius_pt=1.6)
        ax.text(v * span + 0.05, y + 0.26, f"{round(v)} h", fontsize=8, fontweight=600, color=INK, va="center")
    save(fig, "op_output")


def uptime() -> None:
    rows = [("Typhoon Champi", 49.6, 2.2, "95.8%"), ("Cyclone Arnab", 25.1, 0, "100%"), ("Cyclone Murasu", 46.3, 0.9, "98.2%"), ("US midterms", 33.0, 0, "100%")]
    row, bar = 0.3225, 0.105
    fig, ax = canvas(THIRD_W, row * len(rows))
    span = (THIRD_W - 0.01) / 51.8
    for i, (name, on, off, pct) in enumerate(rows):
        y = row * i
        t = ax.text(0, y + 0.075, name, fontsize=7.8, fontweight=600, color=INK, va="center")
        fig.canvas.draw()
        x_end = ax.transData.inverted().transform((t.get_window_extent().x1, 0))[0]
        detail = f"· {on + off:.1f} h" + (f", {off:.1f} h outage" if off else "")
        ax.text(x_end + 0.05, y + 0.075, detail, fontsize=7.2, color=INK2, va="center")
        ax.text(THIRD_W, y + 0.075, pct, fontsize=8.6, fontweight=700, color=INK, va="center", ha="right")
        hbar(ax, y + 0.215, on * span, bar, OURS, radius_pt=1.6, round_end=not off)
        if off:
            hbar(ax, y + 0.215, off * span - 0.008, bar, CRITICAL, x0=on * span + 0.008, radius_pt=1.6)
    save(fig, "op_uptime")


def markets() -> None:
    rows = [("Cyclone Murasu, India", 18.652, OURS), ("Typhoon Champi, Taiwan", 15.719, OURS), ("Typhoon Man-yi/Pepito", 11.045, OURS),
            ("US midterms, Spanish", 10.045, OURS), ("US midterms, Japanese", 4.735, OURS), ("US midterms, Chinese", 4.413, OURS),
            ("5 other storm markets", 10.848, THEIRS)]
    row, bar = 0.1845, 0.122
    fig, ax = canvas(THIRD_W, row * len(rows))
    x0, span = 1.14, 0.93 / 18.652
    for i, (name, v, color) in enumerate(rows):
        c = row * i + row / 2
        hbar(ax, c, v * span, bar, color, x0=x0, radius_pt=1.6)
        ax.text(x0 - 0.05, c, name, fontsize=7.2, color=INK, va="center", ha="right")
        ax.text(x0 + v * span + 0.04, c, f"{v:.1f}M", fontsize=7.4, fontweight=600, color=INK, va="center")
    save(fig, "op_markets")


for chart in (head_to_head, small_channels, output, uptime, markets):
    chart()
print("one-pager charts written to", OUT)
