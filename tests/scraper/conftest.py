import sys
from pathlib import Path

import pytest

# Put src/ on the path so tests can write "from scraper.search import ..."
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


@pytest.fixture(autouse=True)
def isolated_scraper(monkeypatch, tmp_path):
    """Keep every test's cache in its own temp folder, and skip the search throttle's waiting."""
    from scraper import fetch, search

    monkeypatch.setattr(fetch, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(search, "MIN_INTERVAL", 0)
