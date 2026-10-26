"""Scenes read straight from official text: no scraping, no LLM, no translation.

A scene opts in with a ``desk://<template>`` source (content_library.sources), and main.py then builds its script here
from DESK_DIR/desk.json instead of running sources -> context -> script -> rewrite. The text quotes the issuing
agency's own wording (CWA's typhoon warning and advisories, DGPA's closure list), so it cannot invent a warning or a
closure, and every item carries its issue time.

    tw_bulletin   CWA typhoon warning, centre and numbers, CWA forecast, land/sea warning areas, DGPA work and school
                  closures by county, land wind advisory, heavy rain advisory, next warning time (Traditional Chinese)
    tw_storm / tw_closures / tw_advisories   the same in three parts, one scene each
    tw_open / tw_close                       fixed station lines (no figures)
"""

from __future__ import annotations

import re
from datetime import datetime

TEMPLATE_PREFIX = "desk://"


def template_of(sources) -> str | None:
    """The template a scene's sources ask for (``desk://tw_bulletin`` -> ``tw_bulletin``), else None."""
    for s in sources or []:
        if isinstance(s, str) and s.startswith(TEMPLATE_PREFIX):
            return s[len(TEMPLATE_PREFIX):].strip("/")
    return None


def _zh_clock(stamp: str) -> str:
    """'2026/10/23 02:30' (Taiwan time) -> '10月23日凌晨2點30分', the way a Taiwanese newsreader says it."""
    m = re.match(r"(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2})", stamp or "")
    if not m:
        return stamp or ""
    _, mo, d, h, mi = map(int, m.groups())
    part = "凌晨" if h < 5 else "清晨" if h < 8 else "上午" if h < 11 else "中午" if h < 13 else "下午" if h < 18 else "晚上"
    h12 = h if h <= 12 else h - 12
    return f"{mo}月{d}日{part}{h12}點" + (f"{mi}分" if mi else "")


def _spoken(text: str) -> str:
    """CWA's web text, tidied for the voice: no brackets around the warning lights, no line breaks, one space style."""
    text = re.sub(r"[（(](紅色燈號|橙色燈號|黃色燈號)[)）]", r"，為\1", text or "")
    text = re.sub(r"(\d+)轉(\d+)公里", r"\2公里", text)           # "每小時24轉8公里" = slowing to 8 km/h
    text = re.sub(r"([今明])\((\d+)日?\)日?", r"\2日", text)       # "今(22日)晚至明(23)日" -> "22日晚至23日"
    text = re.sub(r"[（(]含([^)）]+)[)）]", r"含\1", text)              # "臺東縣(含蘭嶼、綠島)" -> "臺東縣含蘭嶼、綠島"
    text = re.sub(r"\s+", "", text)
    return text.strip("，。 ") + "。" if text.strip() else ""


def _storm(w: dict) -> list[str]:
    """CWA's typhoon warning: issue time and report number, its own summary, centre, movement, numbers, forecast, areas."""
    now_ = w.get("now") or {}
    movement = (w.get("movement") or w.get("text") or "").replace("根據最新資料顯示，", "")
    report = re.sub(r"^(\d+)-(\d+)$", r"\1之\2", str(w.get("report")))      # interim "10-2" is read 「第十之二報」, not "10 minus 2"
    out = [f"中央氣象署在{_zh_clock(w.get('issued'))}，發布{w.get('title', '颱風警報')}第{report}報。" + _spoken(movement)]
    if now_.get("中心位置"):
        out.append(_spoken(now_["中心位置"].replace("的中心位置在", "，颱風中心位置在")))
    if now_.get("前進方向"):
        out.append(_spoken("颱風" + now_["前進方向"]))
    nums = [f"中心氣壓{now_['中心氣壓']}"] if now_.get("中心氣壓") else []
    for k in ("近中心最大風速", "瞬間之最大陣風"):
        if now_.get(k):
            nums.append(re.sub(r"（約每小時\s*\d+\s*公里）", "", now_[k]).replace("瞬間之最大陣風", "瞬間最大陣風"))
    r = now_.get("暴風半徑", "")
    r7, r10 = re.search(r"七級風平均暴風半徑\s*(\d+)\s*公里", r), re.search(r"十級風平均暴風半徑\s*(\d+)\s*公里", r)
    if r7:
        nums.append(f"七級風平均暴風半徑{r7.group(1)}公里" + (f"，十級風平均暴風半徑{r10.group(1)}公里" if r10 else ""))
    if nums:
        out.append(_spoken("，".join(nums)))
    if w.get("forecast"):
        out.append("氣象署預測，" + _spoken(w["forecast"].replace("預測", "", 1)))
    if w.get("land_area"):
        out.append("陸上警戒區域：" + _spoken(w["land_area"]))
    if w.get("sea_area"):
        out.append("海上警戒區域：" + _spoken(w["sea_area"]))
    return out


def _next(w: dict) -> list[str]:
    if not w.get("next"):
        return []
    m = re.match(r"(\d+)月(\d+)日(\d+)時(\d+)分", w["next"])
    nxt = _zh_clock(f"2000/{int(m.group(1)):02d}/{int(m.group(2)):02d} {int(m.group(3)):02d}:{int(m.group(4)):02d}") if m else w["next"]
    return [f"氣象署下一次颱風警報，預定在{nxt}發布。"]


def _closures(cl: dict, lead: str = "停班停課方面，") -> list[str]:
    """DGPA's list: the counties that closed, partial closures by township, the counties open as usual, and its update time."""
    c = cl.get("counties") or {}
    if not c:
        return []
    off = [k for k, v in c.items() if v.get("status") == "off"]
    part = [(k, v) for k, v in c.items() if v.get("status") == "partial"]
    normal = [k for k, v in c.items() if v.get("status") == "normal"]
    s = f"{lead}根據行政院人事行政總處彙整的各縣市政府公告，{cl.get('day') or '今天'}"
    if off:
        s += f"，{'、'.join(off)}，共{len(off)}個縣市停止上班、停止上課"
    for k, v in part:                       # "綠島鄉:今天停止上班、停止上課。" lines -> "臺東縣綠島鄉、蘭嶼鄉停止上班、停止上課"
        groups: dict[str, list[str]] = {}
        for t in v.get("text", []):
            town, _, what = re.sub(r"\s+", "", t).partition(":") if ":" in t else re.sub(r"\s+", "", t).partition("：")
            groups.setdefault(what.replace("今天", "").rstrip("。"), []).append(town)
        s += "；" + "；".join(f"{k}{'、'.join(towns)}{what}" for what, towns in groups.items())
    if normal:
        s += f"；{'、'.join(normal)}照常上班、照常上課"
    return [s + f"。以上為人事行政總處{_zh_clock((cl.get('updated') or '')[:16])}更新的資料。"]


def _advisories(wind: dict | None, rain: dict | None) -> list[str]:
    out = []
    if wind and wind.get("content"):
        out.append(f"陸上強風特報，氣象署{_zh_clock(wind.get('issued'))}發布：" + _spoken(re.sub(r"請注意防範。?\s*$", "", wind["content"])))
    if rain and rain.get("content"):
        out.append(f"豪雨特報，氣象署{_zh_clock(rain.get('issued'))}發布：" + _spoken(rain["content"].split("請注意")[0]))
    return out


FOOTER = "颱風警報以中央氣象署發布為準，停班停課以各縣市政府公告為準。"


def _tw(desk: dict, need: str) -> dict:
    tw = desk.get("tw") or {}
    if not tw.get(need):
        raise ValueError(f"desk.json has no tw.{need}")
    return tw


def tw_bulletin(desk: dict, now: datetime | None = None) -> str:
    tw = desk.get("tw") or {}
    w, cl = tw.get("warning"), tw.get("closures")
    if not (w or cl):
        raise ValueError("desk.json has no CWA warning or DGPA closures (tw section)")
    out = ["以下是官方資訊快報，內容來自中央氣象署與行政院人事行政總處的最新公告。"]
    out += (_storm(w) if w else []) + (_closures(cl) if cl else []) + _advisories(tw.get("wind"), tw.get("rain")) + (_next(w) if w else [])
    return "\n".join(x for x in out + [FOOTER] if x)


def tw_storm(desk: dict) -> str:
    w = _tw(desk, "warning")["warning"]
    return "\n".join(["颱風警報與最新動態。"] + _storm(w) + _next(w) + ["颱風警報以中央氣象署發布為準。"])


def tw_closures(desk: dict) -> str:
    cl = _tw(desk, "closures")["closures"]
    return "\n".join(["停班停課最新資訊。"] + _closures(cl, lead="") + ["停班停課以各縣市政府公告為準；民間企業的出勤，請依勞動部規定辦理。"])


def tw_advisories(desk: dict) -> str:
    tw = desk.get("tw") or {}
    parts = _advisories(tw.get("wind"), tw.get("rain"))
    if not parts:
        raise ValueError("desk.json has no CWA wind or rain advisory")
    return "\n".join(["強風與豪雨特報。"] + parts + ["山區請慎防坍方、落石與土石流，低窪地區慎防積淹水，請避免前往山區、河川與海邊。"])


def tw_open(desk: dict) -> str:
    return ("這裡是USAL颱風資訊台，薔琵颱風台灣即時直播。畫面持續更新中央氣象署的颱風警報、各縣市停班停課、強風與豪雨特報，"
            "以及北部與東部各地的即時影像。")


def tw_close(desk: dict) -> str:
    return ("以上是薔琵颱風的最新官方資訊，本台持續更新。" + FOOTER + "颱風期間請遠離山區、河川及海岸，外出注意掉落物。")


# ---- Japan: JMA's own typhoon information, relayed as announced (気象業務法: never our own forecast) ------------
def _jma_spec(desk: dict) -> list:
    """JMA specifications.json for the storm in desk.json (its URL is in the desk's provenance)."""
    from desk.http import get_json

    url = ((desk.get("provenance") or {}).get("storm") or {}).get("url") or ""
    if "specifications.json" not in url:
        raise ValueError("desk.json does not name a JMA typhoon (provenance.storm.url)")
    return get_json(url, ttl=300)


def _ja_when(iso_jst: str) -> str:
    """'2026-10-23T21:00:00+09:00' -> '23日21時'."""
    m = re.match(r"\d{4}-\d{2}-(\d{2})T(\d{2}):(\d{2})", iso_jst or "")
    return f"{int(m.group(1))}日{int(m.group(2))}時" + (f"{int(m.group(3))}分" if m and int(m.group(3)) else "") if m else ""


def _ja_loc(p: dict) -> str:
    return re.sub(r"(\d)\s*km", r"\1キロ", p.get("location") or "")


def _ja_class(p: dict) -> str:
    size, strength = p.get("scale") or "", p.get("intensity") or ""
    size, strength = ("" if size in ("-", None) else size), ("" if strength in ("-", None) else strength)
    return (f"{size}で{strength}" if size and strength else size or strength)


def _ja_radii(items: list | None, what: str) -> str:
    rs = [f"{a['area']}側{a['range']['km']}キロ" for a in items or [] if a.get("range")]
    return f"{'、'.join(rs)}以内では{what}" if rs else ""


def jp_now(desk: dict) -> str:
    spec = _jma_spec(desk)
    title = next((p for p in spec if p.get("part") == "title"), {})
    now = next((p for p in spec if isinstance(p.get("part"), dict) and p["part"].get("en") == "Analysis"), None)
    if not now:
        raise ValueError("JMA specifications.json has no analysis")
    num = int(str(title.get("typhoonNumber", "00"))[-2:])
    issued = _ja_when((title.get("issue") or {}).get("JST", ""))
    cls = _ja_class(now)
    out = [f"気象庁が{issued}に発表した台風第{num}号の情報です。",
           f"{cls}台風第{num}号は、{_ja_when(now['validtime']['JST'])}には{_ja_loc(now)}にあって、"
           f"1時間におよそ{now['speed']['km/h']}キロの速さで{now.get('course', '')}へ進んでいます。" if (now.get("speed") or {}).get("km/h")
           else f"{cls}台風第{num}号は、{_ja_when(now['validtime']['JST'])}には{_ja_loc(now)}にあって、{now.get('course', '')}へ進んでいます。",
           f"中心気圧は{now.get('pressure')}ヘクトパスカル、中心付近の最大風速は{now['maximumWind']['sustained']['m/s']}メートル、"
           f"最大瞬間風速は{now['maximumWind']['gust']['m/s']}メートルです。"]
    storm = _ja_radii(now.get("stormWarning"), "風速25メートル以上の暴風")
    gale = _ja_radii(now.get("galeWarning"), "風速15メートル以上の強い風")
    if storm or gale:
        out.append("中心の" + "、".join(x for x in (storm, gale) if x) + "が吹いています。")
    out.append("最新の警報や避難の情報は、気象庁と各市町村の発表をご確認ください。")
    return "\n".join(out)


def jp_forecast(desk: dict) -> str:
    spec = _jma_spec(desk)
    title = next((p for p in spec if p.get("part") == "title"), {})
    num = int(str(title.get("typhoonNumber", "00"))[-2:])
    fc = [p for p in spec if isinstance(p.get("part"), dict) and p["part"].get("en", "").startswith("Forecast") and p.get("location")]
    if not fc:
        raise ValueError("JMA specifications.json has no forecast with a location")
    out = [f"気象庁の予報です。"]
    for i, p in enumerate(fc[:4]):
        w = p.get("maximumWind") or {}
        cls = _ja_class(p)
        lead = f"台風第{num}号は、" if i == 0 else ""
        out.append(f"{lead}{_ja_when(p['validtime']['JST'])}には{_ja_loc(p)}に達する見込みで、"
                   + (f"{cls}勢力で、" if cls else "")
                   + f"中心気圧は{p.get('pressure')}ヘクトパスカル、最大風速は{w.get('sustained', {}).get('m/s')}メートル、"
                   f"最大瞬間風速は{w.get('gust', {}).get('m/s')}メートルと予想されています。")
    out.append("予報には誤差があります。最新の台風情報は気象庁の発表をご確認ください。")
    return "\n".join(out)


def jp_islands(desk: dict) -> str:
    """Which islands lie inside JMA's CURRENT storm / gale area (desk.json jp, from JMA's analysis) and JMA's nearest forecast."""
    J = desk.get("jp") or {}
    isl = J.get("islands") or []
    if not isl:
        raise ValueError("desk.json has no jp.islands")
    storm = [i["name"] for i in isl if i["zone"] == "storm"]
    gale = [i["name"] for i in isl if i["zone"] == "gale"]
    out = [f"先島諸島と沖縄の状況です。気象庁が{_ja_when(J.get('issued', ''))}に発表した暴風域と強風域をもとにお伝えします。"]
    if storm:
        out.append(f"{'、'.join(storm)}は、風速25メートル以上の暴風域に入っています。")
    if gale:
        out.append(f"{'、'.join(gale)}は、風速15メートル以上の強風域に入っています。")
    out.append("台風の中心からの距離は、" + "、".join(f"{i['name']}が約{i['km']}キロ" for i in isl) + "です。")
    near = [f for f in J.get("forecast") or [] if f.get("location") and "島" in f["location"]]
    if near:
        f = near[0]
        out.append(f"気象庁の予報では、台風の中心は{_ja_when(f['time'])}には{re.sub(r'(\d)\s*km', r'\1キロ', f['location'])}に達する見込みです。")
    out.append("暴風や高波、大雨に警戒し、不要不急の外出は控えてください。警報や避難の情報は、気象庁と各市町村の発表をご確認ください。")
    return "\n".join(out)


def jp_open(desk: dict) -> str:
    return ("こちらはUSAL台風情報です。台風第30号に関する気象庁の最新情報を、衛星画像や沖縄・先島諸島の各地のライブカメラとともに、"
            "随時更新してお伝えしています。")


def jp_close(desk: dict) -> str:
    return ("以上、気象庁の発表に基づく台風第30号の最新情報でした。この配信は気象庁の発表をそのままお伝えするもので、独自の予報ではありません。"
            "警報や避難の情報は、気象庁と各市町村の発表をご確認ください。")


TEMPLATES = {"jp_now": jp_now, "jp_forecast": jp_forecast, "jp_islands": jp_islands, "jp_open": jp_open, "jp_close": jp_close,
             "tw_bulletin": tw_bulletin, "tw_storm": tw_storm, "tw_closures": tw_closures, "tw_advisories": tw_advisories,
             "tw_open": tw_open, "tw_close": tw_close}


def build(template: str, desk: dict) -> str:
    if template not in TEMPLATES:
        raise ValueError(f"unknown desk template {template!r} (known: {', '.join(TEMPLATES)})")
    return TEMPLATES[template](desk)
