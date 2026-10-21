"""Spoken-length targets: turn a style rule's duration ("220 to 260 seconds", "about 4 minutes") into words.

Used by the script writer (word budget in its brief) and the rewriter (length guard), so both agree.
SPEECH_WPS is Kokoro's measured delivery rate including the pauses between sentences (about 1.85
words per second at speed 1.0 across the first runs).
"""

from __future__ import annotations

import os
import re

_SECONDS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*seconds", re.I)
_MINUTES = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-|–)\s*(\d+(?:\.\d+)?)\s*minutes", re.I)
_ABOUT_MIN = re.compile(r"(?:about|around|roughly)\s+(\d+(?:\.\d+)?)\s*minutes?", re.I)


def words_per_second() -> float:
    try:
        return float(os.environ.get("SPEECH_WPS", "1.85"))
    except ValueError:
        return 1.85


def target_seconds(rules: str) -> tuple[float, float] | None:
    """(low, high) seconds from the style rules, or None when they give no duration."""
    rules = rules or ""
    if m := _SECONDS.search(rules):
        return float(m.group(1)), float(m.group(2))
    if m := _MINUTES.search(rules):
        return float(m.group(1)) * 60, float(m.group(2)) * 60
    if m := _ABOUT_MIN.search(rules):
        s = float(m.group(1)) * 60
        return 0.9 * s, 1.1 * s
    return None


def target_words(rules: str) -> tuple[int, int] | None:
    """(low, high) word counts for the style rules' duration at the measured speaking rate."""
    t = target_seconds(rules)
    if not t:
        return None
    wps = words_per_second()
    return int(t[0] * wps), int(t[1] * wps)
