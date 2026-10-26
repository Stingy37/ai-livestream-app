"""Offline tests for fetching and extraction: every request goes to a fake transport."""

from datetime import datetime, timezone
from pathlib import Path

import os
import time

import httpx

from scraper.fetch import Fetcher, PageCache, USER_AGENT

FAKES = Path(__file__).resolve().parents[2] / "fakes" / "scraper"
ARTICLE = (FAKES / "article.html").read_text(encoding="utf-8")
NO_METADATA = (FAKES / "article_no_metadata.html").read_text(encoding="utf-8")
NO_BODY = (FAKES / "no_body.html").read_text(encoding="utf-8")


def fake_web(pages, robots="User-agent: *\nAllow: /\n", robots_status=200):
    """A Fetcher whose network is the ``pages`` dict (url -> html or status code). Records every request."""
    requests = []

    def handler(request):
        requests.append(request)
        url = str(request.url)
        if url.endswith("/robots.txt"):
            return httpx.Response(robots_status, text=robots)
        page = pages.get(url, 404)
        if isinstance(page, int):
            return httpx.Response(page)
        if page.startswith("REDIRECT "):
            return httpx.Response(301, headers={"location": page.split(" ", 1)[1]})
        return httpx.Response(200, text=page, headers={"content-type": "text/html; charset=utf-8"})

    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": USER_AGENT})
    return requests, client


def test_article_text_and_metadata(tmp_path):
    _, client = fake_web({"https://wire.example/a": ARTICLE})
    [doc] = Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://wire.example/a"])
    assert doc.url == "https://wire.example/a"
    assert doc.title == "Typhoon Marisol makes landfall in Aurora"
    assert doc.source_name == "Pacific Wire Service"
    assert doc.author == "Jane Roe"
    assert doc.published_at == datetime(2026, 10, 15, tzinfo=timezone.utc)
    assert doc.metadata["published_date_only"] is True  # the page gave a day; 00:00 UTC is a stand-in
    assert isinstance(doc.fetched_at, datetime)
    assert doc.fetched_at - doc.published_at  # both timezone-aware, so QC's recency maths cannot crash
    assert "12,000 people" in doc.main_text and "Signal No. 3" in doc.main_text
    assert "MENU" not in doc.main_text and "cookies" not in doc.main_text


def test_missing_metadata_stays_none(tmp_path):
    _, client = fake_web({"https://news.example/b": NO_METADATA})
    [doc] = Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://news.example/b"])
    assert doc.author is None and doc.published_at is None
    assert doc.source_name == "news.example"  # no site name on the page, so the domain


def test_failures_are_dropped_and_order_is_kept(tmp_path):
    pages = {"https://a.example/1": NO_METADATA, "https://b.example/2": 500, "https://c.example/3": NO_BODY,
             "https://d.example/4": ARTICLE}
    _, client = fake_web(pages)
    docs = Fetcher(max_threads=4, client=client, cache=PageCache(tmp_path)).fetch_all(list(pages))
    assert [d.url for d in docs] == ["https://a.example/1", "https://d.example/4"]


def test_nothing_usable_returns_empty_list(tmp_path):
    _, client = fake_web({"https://a.example/x": NO_BODY})
    assert Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://a.example/x", "ftp://a/b"]) == []


def test_robots_txt_is_respected(tmp_path):
    requests, client = fake_web({"https://a.example/private/p": ARTICLE, "https://a.example/ok": ARTICLE},
                                robots="User-agent: *\nDisallow: /private/\n")
    docs = Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://a.example/private/p", "https://a.example/ok"])
    assert [d.url for d in docs] == ["https://a.example/ok"]
    assert "https://a.example/private/p" not in [str(r.url) for r in requests]  # never even requested
    assert sum(str(r.url).endswith("robots.txt") for r in requests) == 1  # read once per host


def test_unreadable_robots_skips_host(tmp_path):
    requests, client = fake_web({"https://a.example/ok": ARTICLE}, robots_status=503)
    assert Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://a.example/ok"]) == []


def test_cache_avoids_refetching(tmp_path):
    requests, client = fake_web({"https://wire.example/a": ARTICLE})
    first = Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://wire.example/a"])
    pages_before = len(requests)
    second = Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://wire.example/a"])
    assert len(requests) == pages_before  # second run touched no network
    assert second[0].main_text == first[0].main_text
    assert second[0].fetched_at == first[0].fetched_at  # when it was really fetched, not now


def test_expired_cache_refetches(tmp_path):
    requests, client = fake_web({"https://wire.example/a": ARTICLE})
    Fetcher(client=client, cache=PageCache(tmp_path, ttl=-1)).fetch_all(["https://wire.example/a"])
    Fetcher(client=client, cache=PageCache(tmp_path, ttl=-1)).fetch_all(["https://wire.example/a"])
    assert sum(str(r.url) == "https://wire.example/a" for r in requests) == 2


def test_redirect_to_disallowed_page_is_not_fetched(tmp_path):
    requests, client = fake_web({"https://a.example/ok": "REDIRECT /private/p", "https://a.example/private/p": ARTICLE},
                                robots="User-agent: *\nDisallow: /private/\n")
    assert Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://a.example/ok"]) == []
    assert "https://a.example/private/p" not in [str(r.url) for r in requests]


def test_allowed_redirect_is_followed(tmp_path):
    _, client = fake_web({"https://a.example/old": "REDIRECT https://b.example/new", "https://b.example/new": ARTICLE})
    [doc] = Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://a.example/old"])
    assert doc.url == "https://a.example/old" and "12,000 people" in doc.main_text


def test_redirect_loop_is_dropped(tmp_path):
    _, client = fake_web({"https://a.example/x": "REDIRECT /y", "https://a.example/y": "REDIRECT /x"})
    assert Fetcher(client=client, cache=PageCache(tmp_path)).fetch_all(["https://a.example/x"]) == []


def test_prune_deletes_only_old_cache_files(tmp_path):
    cache = PageCache(tmp_path, keep=60)
    cache.put("https://new.example", "<p>new</p>", datetime.now(timezone.utc))
    cache.put("https://old.example", "<p>old</p>", datetime.now(timezone.utc))
    (tmp_path / "search").mkdir()
    old_search = tmp_path / "search" / "q.json"
    old_search.write_text("{}")
    long_ago = time.time() - 3600
    for path in (cache._path("https://old.example"), old_search):
        os.utime(path, (long_ago, long_ago))
    cache.prune()
    assert cache.get("https://new.example") is not None
    assert not cache._path("https://old.example").exists() and not old_search.exists()


def test_user_agent_has_contact_and_optional_extra(monkeypatch):
    from scraper.fetch import user_agent

    monkeypatch.delenv("SCRAPER_CONTACT", raising=False)
    assert "https://github.com/" in user_agent()
    monkeypatch.setenv("SCRAPER_CONTACT", "team@example.edu")
    assert user_agent().endswith("; team@example.edu)")
