"""Offline tests for the fetcher: JSON rendering, html extraction, agency mapping. No network."""

from datetime import datetime, timezone

from scraper.fetch import (FetchResult, Fetcher, agency_for, extract_html, jma_english, render_generic_json,
                           render_jma_typhoon_json, same_domain_links, to_document)

JMA_SPEC = [
    {"part": "title", "issue": {"JST": "2026-10-20T09:45:00+09:00", "UTC": "2026-10-20T00:45:00Z"}, "typhoonNumber": "2630",
     "name": {"jp": "チャンパー", "en": "Champi"}, "category": {"jp": "台風", "en": "TY"}},
    {"part": {"jp": "実況", "en": "Analysis"}, "maximumWind": {"sustained": {"m/s": "50", "kt": "100"}, "gust": {"m/s": "70", "kt": "140"}},
     "galeWarning": [{"area": "東", "range": {"km": 650, "nm": 350}}], "stormWarning": [{"area": {"jp": "全域", "en": "All"}, "range": {"km": 165, "nm": 90}}],
     "category": {"jp": "台風", "en": "TY"}, "scale": "大型", "intensity": "非常に強い", "position": {"deg": [16.0, 135.6]},
     "location": "フィリピンの東", "course": "西北西", "speed": {"km/h": "20", "kt": "11"}, "pressure": "945",
     "validtime": {"JST": "2026-10-20T09:00:00+09:00", "UTC": "2026-10-20T00:00:00Z"}},
    {"part": {"jp": "予報　１２時間後", "en": "Forecast for 12 hours ahead"}, "pressure": "935", "position": {"deg": [17.1, 132.9]},
     "probabilityCircleRadius": {"km": 45, "nm": 25}, "validtime": {"UTC": "2026-10-20T12:00:00Z"}, "intensity": "猛烈な"},
]


def test_jma_json_renders_english_sentences_with_issue_time():
    text, title, issued = render_jma_typhoon_json(JMA_SPEC)
    assert "Typhoon Champi" in title and issued == datetime(2026, 10, 20, 0, 45, tzinfo=timezone.utc)
    assert "center near 16.0N 135.6E" in text and "central pressure 945 hPa" in text
    assert "maximum sustained winds 50 m/s (100 kt, 10-minute average)" in text
    assert "moving WNW at 20 km/h" in text and "east of the Philippines" in text and "very strong" in text
    assert "gale-force winds (>= 15 m/s) within 650 km (350 nm) to the E" in text
    assert "Forecast for 12 hours ahead" in text and "70% probability circle radius 45 km" in text and "violent" in text
    assert text.count("\n") == 2  # one line per part


def test_jma_active_list_and_generic_json():
    text, title, issued = render_jma_typhoon_json([{"tropicalCyclone": "TC2636", "typhoonNumber": "2630", "category": "TY", "issue": "2026-10-20T09:45:00+09:00"}])
    assert "TC2636" in text and issued == datetime(2026, 10, 20, 0, 45, tzinfo=timezone.utc)
    assert render_generic_json({"a": {"b": [1, 2]}, "c": "x"}) == "a.b[0]: 1\na.b[1]: 2\nc: x"


def test_jma_japanese_terms():
    assert jma_english("石垣島の南南西") == "south-southwest of Ishigaki Island"
    assert jma_english("沖縄の南") == "south of Okinawa" and jma_english("北北東") == "NNE" and jma_english("unknown") == "unknown"


HTML = """<html><head><title>Champi update</title><meta property="article:published_time" content="2026-10-19T10:00:00+08:00">
<meta property="og:site_name" content="Example News"></head><body><nav><a href="/menu">Menu</a></nav>
<article><h1>Typhoon Champi maintains strength</h1>
<p>PAGASA said Typhoon Champi was last seen 1,050 km east of Virac, Catanduanes, with maximum sustained winds of 185 km/h near the center and gusts of up to 230 km/h.</p>
<p>The typhoon is moving west-northwestward at 15 km/h and is expected to enter the Philippine Area of Responsibility on Tuesday afternoon, when it will be named Rosal.</p>
<p>Signal No. 3 may be raised over Batanes and the Babuyan Islands, the agency said in its advisory.</p>
<a href="https://example.com/typhoon/bulletin-2">next bulletin</a><a href="https://other.com/x">other site</a><a href="https://example.com/img.png">img</a>
</article></body></html>"""


def test_html_extraction_keeps_story_and_same_domain_links():
    text, meta, links = extract_html(HTML, "https://example.com/typhoon/bulletin-1")
    assert "185 km/h" in text and "Signal No. 3" in text and "Menu" not in text
    assert meta.get("title") and "Champi" in meta["title"]
    assert links == ["https://example.com/menu", "https://example.com/typhoon/bulletin-2"]   # same site only, no images
    assert same_domain_links(HTML, "https://example.com/a") == links


def test_agency_mapping():
    assert agency_for("https://www.jma.go.jp/bosai/typhoon/data/x.json") == "JMA"
    assert agency_for("https://www.metoc.navy.mil/jtwc/products/wp2926web.txt") == "JTWC"
    assert agency_for("https://www.pagasa.dost.gov.ph/weather") == "PAGASA"
    assert agency_for("https://www.gmanetwork.com/news/x", "GMA News Online") == "GMA News Online"
    assert agency_for("https://www.philstar.com/headlines/1") == "Philstar"


def test_extract_dispatch_and_document_conversion(tmp_path):
    f = Fetcher(max_threads=2, cache_dir=tmp_path)
    r = f._extract("https://www.metoc.navy.mil/jtwc/products/wp2926web.txt", 200, "text/plain", "WTPN32 PGTW 192100\n" + "MAX SUSTAINED WINDS - 135 KT, GUSTS 165 KT\n" * 6)
    assert r.ok and r.extraction == "text" and r.published_at is None
    r = f._extract("https://www.jma.go.jp/bosai/typhoon/data/TC2636/specifications.json", 200, "application/json", __import__("json").dumps(JMA_SPEC))
    assert r.ok and r.extraction == "json" and "945 hPa" in r.text
    r = f._extract("https://example.com/typhoon/bulletin-1", 200, "text/html", HTML)
    assert r.ok and r.extraction == "trafilatura" and r.published_at is not None
    d = to_document(r, "search", "typhoon champi pagasa", 1)
    assert d.source_name == "Example News" and d.metadata["discovered_by"] == "search" and d.metadata["text_chars"] == len(d.main_text)
    assert d.main_text == r.text  # complete, never truncated
    bad = f._extract("https://example.com/empty", 200, "text/html", "<html><body><p>short</p></body></html>")
    assert not bad.ok and bad.error.startswith("no main text")


def test_cache_round_trip(tmp_path):
    f = Fetcher(max_threads=1, cache_dir=tmp_path)
    r = FetchResult(url="https://example.com/p", ok=True, status=200, content_type="text/html", text="x" * 200, title="t",
                    published_at=datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc), extraction="trafilatura")
    f._cache_put(r)
    back = f._cache_get("https://example.com/p")
    assert back is not None and back.text == r.text and back.published_at == r.published_at
    assert f._cache_get("https://example.com/other") is None
