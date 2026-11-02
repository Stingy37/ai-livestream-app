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


# ---- India (Cyclone Arnab): IMD's structured bulletin (desk.json in.imd) composed in Telugu and Tamil --------------
# No translation model: fixed phrasing + tables. A name missing from the tables is left out (the voices cannot read
# Latin script), never guessed.
IN_CLASS = {"D": ("వాయుగుండం", "காற்றழுத்த தாழ்வு மண்டலம்"), "DD": ("తీవ్ర వాయుగుండం", "ஆழ்ந்த காற்றழுத்த தாழ்வு மண்டலம்"),
            "CS": ("తుఫాను", "புயல்"), "SCS": ("తీవ్ర తుఫాను", "தீவிர புயல்"), "VSCS": ("అతి తీవ్ర తుఫాను", "மிகத் தீவிர புயல்"),
            "ESCS": ("అత్యంత తీవ్ర తుఫాను", "அதி தீவிர புயல்"), "SuCS": ("సూపర్ తుఫాను", "சூப்பர் புயல்")}
IN_DIR = {"N": ("ఉత్తర", "வடக்கு"), "NNE": ("ఉత్తర-ఈశాన్య", "வடக்கு-வடகிழக்கு"), "NE": ("ఈశాన్య", "வடகிழக்கு"),
          "ENE": ("తూర్పు-ఈశాన్య", "கிழக்கு-வடகிழக்கு"), "E": ("తూర్పు", "கிழக்கு"), "ESE": ("తూర్పు-ఆగ్నేయ", "கிழக்கு-தென்கிழக்கு"),
          "SE": ("ఆగ్నేయ", "தென்கிழக்கு"), "SSE": ("దక్షిణ-ఆగ్నేయ", "தெற்கு-தென்கிழக்கு"), "S": ("దక్షిణ", "தெற்கு"),
          "SSW": ("దక్షిణ-నైరుతి", "தெற்கு-தென்மேற்கு"), "SW": ("నైరుతి", "தென்மேற்கு"), "WSW": ("పశ్చిమ-నైరుతి", "மேற்கு-தென்மேற்கு"),
          "W": ("పశ్చిమ", "மேற்கு"), "WNW": ("పశ్చిమ-వాయవ్య", "மேற்கு-வடமேற்கு"), "NW": ("వాయవ్య", "வடமேற்கு"),
          "NNW": ("ఉత్తర-వాయవ్య", "வடக்கு-வடமேற்கு")}
# place: (Telugu, Tamil, Tamil "from <place>")
IN_PLACE = {"Visakhapatnam": ("విశాఖపట్నం", "விசாகப்பட்டினம்", "விசாகப்பட்டினத்திலிருந்து"),
            "Kakinada": ("కాకినాడ", "காக்கிநாடா", "காக்கிநாடாவிலிருந்து"), "Machilipatnam": ("మచిలీపట్నం", "மசிலிப்பட்டினம்", "மசிலிப்பட்டினத்திலிருந்து"),
            "Bapatla": ("బాపట్ల", "பாபட்லா", "பாபட்லாவிலிருந்து"), "Narsapur": ("నరసాపురం", "நரசாபூர்", "நரசாபூரிலிருந்து"), "Yanam": ("యానాం", "ஏனாம்", "ஏனாமிலிருந்து"),
            "Kalingapatnam": ("కళింగపట్నం", "கலிங்கப்பட்டினம்", "கலிங்கப்பட்டினத்திலிருந்து"), "Nellore": ("నెల్లూరు", "நெல்லூர்", "நெல்லூரிலிருந்து"),
            "Chennai": ("చెన్నై", "சென்னை", "சென்னையிலிருந்து"), "Puducherry": ("పుదుచ్చేరి", "புதுச்சேரி", "புதுச்சேரியிலிருந்து"),
            "Gopalpur": ("గోపాల్‌పూర్", "கோபால்பூர்", "கோபால்பூரிலிருந்து"), "Puri": ("పూరీ", "பூரி", "பூரியிலிருந்து"),
            "Paradip": ("పారాదీప్", "பாரதீப்", "பாரதீப்பிலிருந்து"), "Ongole": ("ఒంగోలు", "ஓங்கோல்", "ஓங்கோலிலிருந்து"),
            "Port Blair": ("పోర్ట్ బ్లెయిర్", "போர்ட் பிளேர்", "போர்ட் பிளேரிலிருந்து"),
            "Coastal Andhra Pradesh": ("కోస్తా ఆంధ్ర", "கடலோர ஆந்திரா", ""), "Andhra Pradesh": ("ఆంధ్రప్రదేశ్", "ஆந்திரப் பிரதேசம்", ""),
            "Rayalaseema": ("రాయలసీమ", "ராயலசீமா", ""), "Telangana": ("తెలంగాణ", "தெலங்கானா", ""), "Odisha": ("ఒడిశా", "ஒடிசா", ""),
            "South Odisha": ("దక్షిణ ఒడిశా", "தெற்கு ஒடிசா", ""), "Tamil Nadu": ("తమిళనాడు", "தமிழ்நாடு", ""),
            "North Coastal Tamil Nadu": ("ఉత్తర కోస్తా తమిళనాడు", "வட கடலோர தமிழ்நாடு", ""), "Karaikal": ("కారైక్కల్", "காரைக்கால்", ""),
            "East Godavari": ("తూర్పు గోదావరి", "கிழக்கு கோதாவரி", ""), "West Godavari": ("పశ్చిమ గోదావరి", "மேற்கு கோதாவரி", ""),
            "Konaseema": ("కోనసీమ", "கோனசீமா", ""), "Krishna": ("కృష్ణా", "கிருஷ்ணா", ""), "Guntur": ("గుంటూరు", "குண்டூர்", ""),
            "Prakasam": ("ప్రకాశం", "பிரகாசம்", ""), "Anakapalli": ("అనకాపల్లి", "அனகாபள்ளி", ""), "Srikakulam": ("శ్రీకాకుళం", "ஸ்ரீகாகுளம்", ""),
            "Vizianagaram": ("విజయనగరం", "விஜயநகரம்", ""), "Eluru": ("ఏలూరు", "ஏலூரு", ""), "Alluri Sitharama Raju": ("అల్లూరి సీతారామరాజు", "அல்லூரி சீதாராம ராஜு", ""),
            "Tiruvallur": ("తిరువళ్లూరు", "திருவள்ளூர்", ""), "Chengalpattu": ("చెంగల్పట్టు", "செங்கல்பட்டு", ""), "Kancheepuram": ("కాంచీపురం", "காஞ்சிபுரம்", ""),
            "Ranipet": ("రాణిపేట", "ராணிப்பேட்டை", ""), "Vellore": ("వెల్లూరు", "வேலூர்", ""), "Villupuram": ("విల్లుపురం", "விழுப்புரம்", "")}
# district names (IMD's spelling) for each stream's own state: AP in Telugu, Tamil Nadu + Puducherry in Tamil
TE_DISTRICT = {"Srikakulam": "శ్రీకాకుళం", "Vizianagaram": "విజయనగరం", "Parvathipuram Manyam": "పార్వతీపురం మన్యం",
               "Alluri Sitharama Raju": "అల్లూరి సీతారామరాజు", "Visakhapatnam": "విశాఖపట్నం", "Anakapalli": "అనకాపల్లి", "Kakinada": "కాకినాడ",
               "Konaseema": "కోనసీమ", "Dr. B.R. Ambedkar Konaseema": "కోనసీమ", "East Godavari": "తూర్పు గోదావరి", "West Godavari": "పశ్చిమ గోదావరి",
               "Eluru": "ఏలూరు", "Krishna": "కృష్ణా", "NTR": "ఎన్టీఆర్", "Guntur": "గుంటూరు", "Palnadu": "పల్నాడు", "Bapatla": "బాపట్ల",
               "Prakasam": "ప్రకాశం", "Nellore": "నెల్లూరు", "Sri Potti Sriramulu Nellore": "నెల్లూరు", "Kurnool": "కర్నూలు", "Nandyal": "నంద్యాల",
               "Anantapur": "అనంతపురం", "Ananthapuramu": "అనంతపురం", "Sri Sathya Sai": "శ్రీ సత్యసాయి", "YSR Kadapa": "కడప", "Kadapa": "కడప",
               "Annamayya": "అన్నమయ్య", "Chittoor": "చిత్తూరు", "Tirupati": "తిరుపతి",
               # IMD's district-warning layer spells some names its own way
               "Vishakhapatnam": "విశాఖపట్నం", "Tirupathi": "తిరుపతి", "Anantapuramu": "అనంతపురం", "SPSR Nellore": "నెల్లూరు",
               "Parvathipurammanyam": "పార్వతీపురం మన్యం", "Srisathyasai": "శ్రీ సత్యసాయి"}
TA_DISTRICT = {"Chennai": "சென்னை", "Tiruvallur": "திருவள்ளூர்", "Chengalpattu": "செங்கல்பட்டு", "Kancheepuram": "காஞ்சிபுரம்",
               "Ranipet": "ராணிப்பேட்டை", "Vellore": "வேலூர்", "Tirupathur": "திருப்பத்தூர்", "Tiruvannamalai": "திருவண்ணாமலை",
               "Villupuram": "விழுப்புரம்", "Kallakurichi": "கள்ளக்குறிச்சி", "Cuddalore": "கடலூர்", "Mayiladuthurai": "மயிலாடுதுறை",
               "Nagapattinam": "நாகப்பட்டினம்", "Tiruvarur": "திருவாரூர்", "Thanjavur": "தஞ்சாவூர்", "Pudukkottai": "புதுக்கோட்டை",
               "Ramanathapuram": "ராமநாதபுரம்", "Thoothukudi": "தூத்துக்குடி", "Tirunelveli": "திருநெல்வேலி", "Tenkasi": "தென்காசி",
               "Kanyakumari": "கன்னியாகுமரி", "Virudhunagar": "விருதுநகர்", "Madurai": "மதுரை", "Sivaganga": "சிவகங்கை", "Theni": "தேனி",
               "Dindigul": "திண்டுக்கல்", "Tiruchirappalli": "திருச்சிராப்பள்ளி", "Karur": "கரூர்", "Perambalur": "பெரம்பலூர்",
               "Ariyalur": "அரியலூர்", "Namakkal": "நாமக்கல்", "Salem": "சேலம்", "Dharmapuri": "தர்மபுரி", "Krishnagiri": "கிருஷ்ணகிரி",
               "Erode": "ஈரோடு", "Tiruppur": "திருப்பூர்", "Coimbatore": "கோயம்புத்தூர்", "The Nilgiris": "நீலகிரி", "Nilgiris": "நீலகிரி",
               "Puducherry": "புதுச்சேரி", "Karaikal": "காரைக்கால்",
               # IMD's district-warning layer spells some names its own way
               "Kallakkurichi": "கள்ளக்குறிச்சி", "Ranippettai": "ராணிப்பேட்டை", "Sivagangai": "சிவகங்கை", "Thirunelveli": "திருநெல்வேலி",
               "Thiruvarur": "திருவாரூர்", "Thiruchirapalli": "திருச்சிராப்பள்ளி", "Thiruppur": "திருப்பூர்", "Tiruppattar": "திருப்பத்தூர்",
               "Thiruvallur": "திருவள்ளூர்", "Thiruvannamalai": "திருவண்ணாமலை", "Yanam": "ஏனாம்"}
IN_COLOUR = {"red": ("రెడ్ అలర్ట్", "சிவப்பு எச்சரிக்கை"), "orange": ("ఆరెంజ్ అలర్ట్", "ஆரஞ்சு எச்சரிக்கை"), "yellow": ("ఎల్లో అలర్ట్", "மஞ்சள் எச்சரிக்கை")}
IN_PART = {"early morning": ("తెల్లవారుజామున", "அதிகாலை"), "morning": ("ఉదయం", "காலை"), "forenoon": ("ఉదయం", "முற்பகல்"),
           "noon": ("మధ్యాహ్నం", "நண்பகல்"), "afternoon": ("మధ్యాహ్నం", "மதியம்"), "evening": ("సాయంత్రం", "மாலை"), "night": ("రాత్రి", "இரவு"),
           "midnight": ("అర్ధరాత్రి", "நள்ளிரவு")}
IN_RAIN = {"heavy": ("భారీ", "கனமழை"), "very heavy": ("అతి భారీ", "மிக கனமழை"), "extremely heavy": ("అత్యంత భారీ", "அதி கனமழை"),
           "heavy to very heavy": ("భారీ నుంచి అతి భారీ", "கனமழை முதல் மிக கனமழை"),
           "very heavy to extremely heavy": ("అతి భారీ నుంచి అత్యంత భారీ", "மிக கனமழை முதல் அதி கனமழை")}
# storm names in Telugu and Tamil script (the MMS voices cannot read Latin); a storm missing here is called "the cyclone"
IN_STORM = {"ARNAB": ("అర్నాబ్", "அர்னாப்"), "MURASU": ("మురసు", "முரசு")}
IN_MONTH = {10: ("అక్టోబర్", "அக்டோபர்"), 11: ("నవంబర్", "நவம்பர்"), 12: ("డిసెంబర్", "டிசம்பர்")}


def _i(lang: str) -> int:
    return 0 if lang == "te" else 1


IN_ALIAS = {"vishakhapatnam": "Visakhapatnam", "vizag": "Visakhapatnam", "costal andhra pradesh": "Coastal Andhra Pradesh",
            "pondicherry": "Puducherry", "kakinada port": "Kakinada"}
# IMD's area phrases ("north costal Andhra Pradesh", "eastern parts of Telangana", "districts of coastal Andhra Pradesh from
# Krishna to Anakapalli") -> names: ordered rules, every match kept; sea areas are left to the marine warnings
IN_AREA_RULES = [
    (r"north\s+co?a?stal\s+andhra", ("ఉత్తర కోస్తా ఆంధ్ర", "வட கடலோர ஆந்திரா")), (r"south\s+co?a?stal\s+andhra", ("దక్షిణ కోస్తా ఆంధ్ర", "தெற்கு கடலோர ஆந்திரா")),
    (r"(?<!north )(?<!south )co?a?stal\s+andhra", ("కోస్తా ఆంధ్ర", "கடலோர ஆந்திரா")), (r"rayalaseema", ("రాయలసీమ", "ராயலசீமா")),
    (r"^(?!.*co?a?stal).*andhra pradesh", ("ఆంధ్రప్రదేశ్", "ஆந்திரப் பிரதேசம்")), (r"yanam", ("యానాం", "ஏனாம்")),
    (r"eastern parts of telangana", ("తూర్పు తెలంగాణ", "கிழக்கு தெலங்கானா")), (r"^(?!.*eastern parts).*telangana", ("తెలంగాణ", "தெலங்கானா")),
    (r"south(ern)?\s+odisha", ("దక్షిణ ఒడిశా", "தெற்கு ஒடிசா")), (r"interior.*odisha", ("అంతర్గత ఒడిశా", "உள் ஒடிசா")),
    (r"^(?!.*(south|interior)).*odisha", ("ఒడిశా", "ஒடிசா")), (r"north\s+tamil\s+nadu", ("ఉత్తర తమిళనాడు", "வட தமிழ்நாடு")),
    (r"^(?!.*north).*tamil\s+nadu", ("తమిళనాడు", "தமிழ்நாடு")), (r"puducherry", ("పుదుచ్చేరి", "புதுச்சேரி")), (r"karaikal", ("కారైక్కల్", "காரைக்கால்")),
    (r"chhattisgarh", ("ఛత్తీస్‌గఢ్", "சத்தீஸ்கர்")), (r"jharkhand", ("జార్ఖండ్", "ஜார்கண்ட்")), (r"bihar", ("బిహార్", "பீகார்")),
    (r"west bengal", ("పశ్చిమ బెంగాల్", "மேற்கு வங்கம்")), (r"vidarbha", ("విదర్భ", "விதர்பா")), (r"madhya pradesh", ("మధ్యప్రదేశ్", "மத்தியப் பிரதேசம்")),
    (r"uttar pradesh", ("ఉత్తరప్రదేశ్", "உத்தரப் பிரதேசம்")), (r"andaman", ("అండమాన్", "அந்தமான்"))]


def _place(name: str, lang: str, form: int = 0) -> str:
    key = (name or "").strip()
    key = IN_ALIAS.get(key.lower(), key)
    row = IN_PLACE.get(key) or next((v for k, v in IN_PLACE.items() if k.lower() == key.lower()), None)
    return (row[_i(lang)] if form == 0 else row[2]) if row else ""


def _area_names(phrase: str, lang: str) -> list[str]:
    """One IMD area phrase -> Telugu / Tamil names (empty for sea areas and anything unknown)."""
    whole = _place(phrase, lang)
    if whole:
        return [whole]
    # "Yanam (Puducherry)": the bracket names the territory Yanam belongs to, not Puducherry town
    low = re.sub(r"\([^)]*\)", " ", (phrase or "").lower()).replace("costal", "coastal")
    if "north tamil nadu coast" in low:          # the one coastal strip the Tamil stream must name
        return ["ఉత్తర తమిళనాడు తీరం" if lang == "te" else "வட தமிழக கடலோரம்"]
    if "bay of bengal" in low or "andaman sea" in low or " coast" in low and "district" not in low and "andhra" not in low:
        return []
    m = re.search(r"from\s+([a-z ]+?)\s+to\s+([a-z ]+?)(\s|$)", low)
    if m and _place(m.group(1).title(), lang) and _place(m.group(2).title(), lang):
        a, b = _place(m.group(1).title(), lang), _place(m.group(2).title(), lang)
        return [f"{a} నుంచి {b} వరకు కోస్తా జిల్లాలు" if lang == "te" else f"{a} முதல் {b} வரையிலான கடலோர மாவட்டங்கள்"]
    return [names[_i(lang)] for rx, names in IN_AREA_RULES if re.search(rx, low)]


def _range(v, lang: str, unit: str) -> str:
    """[100, 110] -> "100-110 km/h" (the voice reads it as 100 to 110), 120 -> "120 km/h"."""
    if v is None or v == []:
        return ""
    s = f"{v[0]}-{v[1]}" if isinstance(v, (list, tuple)) and len(v) == 2 else str(v[0] if isinstance(v, (list, tuple)) else v)
    return f"{s} {unit}"


def _in_date(date: str, part: str, lang: str) -> str:
    m = re.match(r"\d{4}-(\d{2})-(\d{2})", date or "")
    if not m:
        return ""
    mon = IN_MONTH.get(int(m.group(1)), ("", ""))[_i(lang)]
    p = IN_PART.get((part or "").lower(), ("", ""))[_i(lang)]
    if not p:                                   # "on 27 October": Telugu 27న, Tamil 27 அன்று
        return f"{mon} {int(m.group(2))}న" if lang == "te" else f"{mon} {int(m.group(2))} அன்று"
    return f"{mon} {int(m.group(2))} {p}"


def _in_areas(areas: list | None, lang: str) -> str:
    names = list(dict.fromkeys(n for a in areas or [] for n in _area_names(a, lang)))
    return (", ".join(names[:-1]) + (" మరియు " if lang == "te" else " மற்றும் ") + names[-1]) if len(names) > 1 else (names[0] if names else "")


def _ta_as(noun: str) -> str:
    """Tamil "as a <class>": புயல் -> புயலாக, மண்டலம் -> மண்டலமாக."""
    return noun[:-2] + "லாக" if noun.endswith("ல்") else noun[:-2] + "மாக" if noun.endswith("ம்") else noun + "ஆக"


def _in_imd(desk: dict) -> dict:
    imd = (desk.get("in") or {}).get("imd") or {}
    if not imd:
        raise ValueError("desk.json has no in.imd (IMD bulletin)")
    return imd


def _ist(iso: str, lang: str) -> str:
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    try:
        t = _dt.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_tz(_td(hours=5, minutes=30)))
    except (AttributeError, ValueError):
        return ""
    mon = IN_MONTH.get(t.month, ("", ""))[_i(lang)]
    return f"{mon} {t.day}, {t.hour}:{t.minute:02d}"


def _in_now(desk: dict, lang: str) -> str:
    imd = _in_imd(desk)
    te = lang == "te"
    name = _in_storm(desk, lang)
    cls = IN_CLASS.get(imd.get("class_short") or "", ("తుఫాను", "புயல்"))[_i(lang)]
    out = [(f"భారత వాతావరణ శాఖ, {_ist(imd.get('issuedUTC', ''), lang)} గంటలకు విడుదల చేసిన బులెటిన్ ప్రకారం." if te else
            f"இந்திய வானிலை ஆய்வு மையம் {_ist(imd.get('issuedUTC', ''), lang)} மணிக்கு வெளியிட்ட அறிக்கையின்படி.")]
    pos = []
    home = ("Andhra Pradesh",) if te else ("Tamil Nadu", "Puducherry", "Andhra Pradesh")      # each stream's own coast first
    ordered = sorted(imd.get("position") or [], key=lambda p: home.index(p.get("state")) if p.get("state") in home else len(home))
    for p in ordered[:2]:
        d = IN_DIR.get(p.get("dir", ""), ("", ""))[_i(lang)]
        if not d:
            continue
        if te and _place(p.get("place"), lang):
            pos.append(f"{_place(p['place'], lang)} నుంచి {d} దిశలో సుమారు {p['km']} km")
        elif not te and _place(p.get("place"), lang, 2):
            pos.append(f"{_place(p['place'], lang, 2)} {d} திசையில் சுமார் {p['km']} km")
    if pos:
        out.append((f"{name} {cls} ప్రస్తుతం " + ", ".join(pos) + " దూరంలో కేంద్రీకృతమై ఉంది.") if te else
                   (f"{name} {cls} தற்போது " + ", ".join(pos) + " தொலைவில் மையம் கொண்டுள்ளது."))
    mv = imd.get("movement") or {}
    if IN_DIR.get(mv.get("dir", "")) and mv.get("kmh"):
        d = IN_DIR[mv["dir"]][_i(lang)]
        out.append(f"ఇది గంటకు {mv['kmh']} km వేగంతో {d} దిశగా కదులుతోంది." if te else f"இது மணிக்கு {mv['kmh']} km வேகத்தில் {d} நோக்கி நகர்கிறது.")
    unit = "km" if te else "km/h"
    w, g = _range(imd.get("wind_kmh"), lang, unit), _range(imd.get("gust_kmh"), lang, unit)
    if w:
        out.append((f"తుఫాను కేంద్రం వద్ద గాలుల వేగం గంటకు {w}" + (f", గరిష్ఠంగా {g}" if g else "") + ".") if te else
                   (f"புயலின் மையப் பகுதியில் காற்றின் வேகம் {w}" + (f", அதிகபட்சமாக {g}" if g else "") + "."))
    if imd.get("pressure_hpa"):
        out.append(f"కేంద్రంలో వాయుపీడనం {imd['pressure_hpa']:g} hPa." if te else f"மையத்தில் காற்றழுத்தம் {imd['pressure_hpa']:g} hPa.")
    return "\n".join(out)


IN_REL_TE = {"north": "ఉత్తరంగా", "south": "దక్షిణంగా", "east": "తూర్పుగా", "west": "పశ్చిమంగా"}   # "to the south of Ongole"


def _in_landfall(desk: dict, lang: str) -> str:
    imd = _in_imd(desk)
    lf = imd.get("landfall") or {}
    te = lang == "te"
    between = [n for n in (_place(x, lang) for x in lf.get("between") or []) if n]
    if len(between) < 2 and not _place(lf.get("near"), lang):
        raise ValueError("IMD gives no landfall place this bulletin")
    when = _in_date(lf.get("date", ""), lf.get("part_of_day", ""), lang)
    cls = IN_CLASS.get(lf.get("class_short") or "", ("", ""))[_i(lang)]
    near = _place(lf.get("near"), lang)
    out = []
    if te:
        s = "భారత వాతావరణ శాఖ అంచనా ప్రకారం, తుఫాను "
        s += f"{between[0]}, {between[1]} మధ్య " if len(between) >= 2 else ""
        rel = IN_REL_TE.get(lf.get("near_rel") or "")
        s += (f"{near}కు {rel} " if rel else f"{near} సమీపంలో ") if near else ""
        s += f"{when} " if when else ""
        s += (f"{cls}గా " if cls else "") + "తీరం దాటే అవకాశం ఉంది."
    else:
        s = "இந்திய வானிலை ஆய்வு மையத்தின் கணிப்பின்படி, புயல் "
        s += f"{between[0]} மற்றும் {between[1]} இடையே " if len(between) >= 2 else ""
        s += f"{near} அருகே " if near else ""
        s += f"{when} " if when else ""
        s += (f"{_ta_as(cls)} " if cls else "") + "கரையைக் கடக்கக்கூடும்."
    out.append(s)
    unit = "km" if te else "km/h"
    w, g = _range(lf.get("wind_kmh"), lang, unit), _range(lf.get("gust_kmh"), lang, unit)
    if w:
        out.append((f"తీరం దాటే సమయంలో గాలుల వేగం గంటకు {w}" + (f", గరిష్ఠంగా {g}" if g else "") + " ఉండవచ్చు.") if te else
                   (f"கரையைக் கடக்கும்போது காற்றின் வேகம் {w}" + (f", அதிகபட்சமாக {g}" if g else "") + " இருக்கலாம்."))
    sg = imd.get("surge") or {}
    if sg.get("m"):
        num = lambda x: f"{x:g}" if isinstance(x, float) else str(x)
        m = sg["m"]
        h = f"{num(m[0])}-{num(m[1])}" if isinstance(m, (list, tuple)) and len(m) == 2 else num(m)
        areas = _in_areas((sg.get("peak_areas") or []) + (sg.get("peak_near") or []) or sg.get("areas"), lang)
        out.append((f"{areas} " if areas else "") + (f"లోతట్టు ప్రాంతాల్లో సముద్రపు అలలు సుమారు {h} మీటర్ల ఎత్తు వరకు ఎగసిపడే ప్రమాదం ఉంది." if te else
                   f"தாழ்வான பகுதிகளில் கடல் அலைகள் சுமார் {h} மீட்டர் உயரம் வரை எழும் அபாயம் உள்ளது."))
    return "\n".join(out)


def _in_today() -> str:
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    return _dt.now(_tz(_td(hours=5, minutes=30))).strftime("%Y-%m-%d")


def _in_warnings(desk: dict, lang: str) -> str:
    """Rain and wind for the stream's own region (three and one items), district colours, fishermen: short enough to hear."""
    imd = _in_imd(desk)
    te = lang == "te"
    today = _in_today()
    home = ("andhra", "yanam", "telangana") if te else ("tamil", "puducherry", "chennai", "karaikal")   # Telugu: AP and Telangana
    mine = lambda x: (any(k in re.sub(r"\([^)]*\)", " ", " ".join(x.get("areas") or []).lower()) for k in home)
                      and (x.get("date") or today) >= today)
    out = []
    for r in sorted(filter(mine, imd.get("rain") or []), key=lambda r: r.get("date") or "")[:3]:
        lvl = IN_RAIN.get((r.get("level") or "").lower(), ("", ""))[_i(lang)]
        areas = _in_areas(r.get("areas"), lang)
        when = _in_date(r.get("date", ""), "", lang)
        if lvl and areas:
            out.append(f"{when} {areas}లో {lvl} వర్షాలు కురిసే అవకాశం ఉంది." if te else f"{when} {areas} பகுதிகளில் {lvl} பெய்ய வாய்ப்புள்ளது.")
    unit = "km" if te else "km/h"
    for w in sorted(filter(mine, imd.get("wind_warnings") or []), key=lambda w: -max(w.get("kmh") or [0]))[:1]:
        areas, k, g = _in_areas(w.get("areas"), lang), _range(w.get("kmh"), lang, unit), _range(w.get("gust_kmh"), lang, unit)
        if areas and k:
            out.append((f"{areas}లో గంటకు {k}" + (f", గరిష్ఠంగా {g}" if g else "") + " వేగంతో ఈదురుగాలులు వీచే అవకాశం ఉంది.") if te else
                       (f"{areas} பகுதிகளில் {k}" + (f", அதிகபட்சமாக {g}" if g else "") + " வேகத்தில் பலத்த காற்று வீசக்கூடும்."))
    out += _in_district_alerts(desk, lang)
    if imd.get("fishermen"):
        out.append("మత్స్యకారులు సముద్రంలోకి వేటకు వెళ్లవద్దని భారత వాతావరణ శాఖ సూచించింది." if te else
                   "மீனவர்கள் கடலுக்குச் செல்ல வேண்டாம் என இந்திய வானிலை ஆய்வு மையம் அறிவுறுத்தியுள்ளது.")
    if not out:
        raise ValueError("IMD gives no rain / wind / district / fishermen warning for this region this bulletin")
    out.append("అధికారిక హెచ్చరికలు, సహాయక చర్యల కోసం జిల్లా యంత్రాంగం ప్రకటనలను పాటించండి." if te else
               "அதிகாரப்பூர்வ எச்சரிக்கைகள் மற்றும் நிவாரண நடவடிக்கைகளுக்கு மாவட்ட நிர்வாகத்தின் அறிவிப்புகளைப் பின்பற்றவும்.")
    return "\n".join(out)


def _in_district_alerts(desk: dict, lang: str) -> list[str]:
    """IMD's district colours (desk.json in.districts_days) for the stream's own state, the next days, red and orange first."""
    te = lang == "te"
    days = (desk.get("in") or {}).get("districts_days") or {}
    states, names = (("Andhra Pradesh",), TE_DISTRICT) if te else (("Tamil Nadu", "Puducherry"), TA_DISTRICT)
    by_date: dict[str, dict[str, list[str]]] = {}
    for st in states:
        for district, entries in (days.get(st) or {}).items():
            local = names.get(district)
            for e in entries or []:
                if local and e.get("colour") in IN_COLOUR:
                    by_date.setdefault(e["date"], {}).setdefault(e["colour"], []).append(local)
    out = []
    today = _in_today()
    for date in [d for d in sorted(by_date) if d >= today][:2]:
        when = _in_date(date, "", lang)
        top = next((c for c in ("red", "orange", "yellow") if by_date[date].get(c)), None)
        if not top:
            continue
        ds = sorted(set(by_date[date][top]))
        shown = ", ".join(ds[:8])
        n = len(ds)
        label = IN_COLOUR[top][_i(lang)]
        if te:
            whom = f"{shown} సహా {n} జిల్లాలకు" if n > 8 else (f"{shown} జిల్లాలకు" if n > 1 else f"{shown} జిల్లాకు")
            line = f"{when} భారత వాతావరణ శాఖ {whom} {label} జారీ చేసింది."
        else:
            whom = f"{shown} உட்பட {n} மாவட்டங்களுக்கு" if n > 8 else (f"{shown} மாவட்டங்களுக்கு" if n > 1 else f"{shown} மாவட்டத்திற்கு")
            line = f"{when} இந்திய வானிலை ஆய்வு மையம் {whom} {label} விடுத்துள்ளது."
        nxt = next((c for c in ("orange", "yellow") if c != top and by_date[date].get(c) and ("red", "orange", "yellow").index(c) > ("red", "orange", "yellow").index(top)), None)
        if nxt:
            k = len(set(by_date[date][nxt]))
            line += (f" మరో {k} జిల్లాలకు {IN_COLOUR[nxt][0]}." if te else f" மேலும் {k} மாவட்டங்களுக்கு {IN_COLOUR[nxt][1]}.")
        out.append(line)
    return out


def _in_storm(desk: dict, lang: str) -> str:
    """The desk storm's name in Telugu / Tamil script, or "" when IN_STORM does not have it."""
    row = IN_STORM.get(((desk.get("storm") or {}).get("name") or "").strip().upper())
    return row[_i(lang)] if row else ""


def in_te_open(desk: dict) -> str:
    return f"{(_in_storm(desk, 'te') + ' ') if _in_storm(desk, 'te') else ''}తుఫాను లైవ్ అప్‌డేట్స్. భారత వాతావరణ శాఖ తాజా బులెటిన్లు, తుఫాను మార్గం, రాడార్ చిత్రాలను నిరంతరం అందిస్తున్నాం."


def in_ta_open(desk: dict) -> str:
    return f"{(_in_storm(desk, 'ta') + ' ') if _in_storm(desk, 'ta') else ''}புயல் நேரலை. இந்திய வானிலை ஆய்வு மையத்தின் சமீபத்திய அறிக்கைகள், புயலின் பாதை, ரேடார் படங்களை தொடர்ந்து வழங்குகிறோம்."


def in_te_close(desk: dict) -> str:
    return ("ఇవి భారత వాతావరణ శాఖ అధికారిక సమాచారం ఆధారంగా అందించిన తాజా వివరాలు. తుఫాను సమయంలో ఇంట్లోనే సురక్షితంగా ఉండండి, "
            "అధికారుల సూచనలు పాటించండి.")


def in_ta_close(desk: dict) -> str:
    return ("இவை இந்திய வானிலை ஆய்வு மையத்தின் அதிகாரப்பூர்வ தகவல்களின் அடிப்படையிலான சமீபத்திய விவரங்கள். புயலின் போது பாதுகாப்பாக இருங்கள், "
            "அதிகாரிகளின் அறிவுறுத்தல்களைப் பின்பற்றுங்கள்.")


TEMPLATES.update({
    "in_te_open": in_te_open, "in_ta_open": in_ta_open, "in_te_close": in_te_close, "in_ta_close": in_ta_close,
    "in_te_now": lambda d: _in_now(d, "te"), "in_ta_now": lambda d: _in_now(d, "ta"),
    "in_te_landfall": lambda d: _in_landfall(d, "te"), "in_ta_landfall": lambda d: _in_landfall(d, "ta"),
    "in_te_warnings": lambda d: _in_warnings(d, "te"), "in_ta_warnings": lambda d: _in_warnings(d, "ta"),
})


# ---- India, English (Indian English voice, models/tts_indicparler.py): the same IMD fields with IMD's own English ----
# names, for the Andhra Pradesh coast. The storm's name comes from desk.json storm.name, so the templates follow the desk's storm;
# a depression is not called by a name IMD has not given it yet.
EN_CLASS = {"D": "Depression", "DD": "Deep Depression", "CS": "Cyclonic Storm", "SCS": "Severe Cyclonic Storm",
            "VSCS": "Very Severe Cyclonic Storm", "ESCS": "Extremely Severe Cyclonic Storm", "SuCS": "Super Cyclonic Storm"}
EN_DIR = {"N": "north", "NNE": "north-northeast", "NE": "northeast", "ENE": "east-northeast", "E": "east", "ESE": "east-southeast",
          "SE": "southeast", "SSE": "south-southeast", "S": "south", "SSW": "south-southwest", "SW": "southwest",
          "WSW": "west-southwest", "W": "west", "WNW": "west-northwest", "NW": "northwest", "NNW": "north-northwest"}
EN_MONTH = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
EN_COLOUR = {"red": "a red alert", "orange": "an orange alert", "yellow": "a yellow alert"}
# the English stream follows the storm's coast, as the Telugu stream does: Andhra Pradesh, Yanam and Telangana
EN_HOME = ("andhra", "yanam", "telangana")
EN_HOME_STATES = ("Andhra Pradesh",)
EN_RAIN = ["extremely heavy", "very heavy to extremely heavy", "very heavy", "heavy to very heavy", "heavy"]
# IMD's district-warning layer spells some names its own way (the same quirks as TE_DISTRICT / TA_DISTRICT)
EN_DISTRICT = {"Vishakhapatnam": "Visakhapatnam", "Tirupathi": "Tirupati", "Anantapuramu": "Anantapur", "Ananthapuramu": "Anantapur",
               "SPSR Nellore": "Nellore", "Sri Potti Sriramulu Nellore": "Nellore", "Parvathipurammanyam": "Parvathipuram Manyam",
               "Srisathyasai": "Sri Sathya Sai", "Dr. B.R. Ambedkar Konaseema": "Konaseema", "Kallakkurichi": "Kallakurichi",
               "Ranippettai": "Ranipet", "Sivagangai": "Sivaganga", "Thirunelveli": "Tirunelveli", "Thiruvarur": "Tiruvarur",
               "Thiruchirapalli": "Tiruchirappalli", "Thiruppur": "Tiruppur", "Tiruppattar": "Tirupathur", "Thiruvallur": "Tiruvallur",
               "Thiruvannamalai": "Tiruvannamalai"}


def _en_cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _en_and(names: list[str]) -> str:
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else (names[0] if names else "")


def _en_name(desk: dict, class_short: str = "") -> str:
    """'Cyclonic Storm Murasu'; 'the deep depression' before IMD names it."""
    cls = EN_CLASS.get(class_short or "", "")
    if class_short in ("D", "DD"):
        return f"the {cls.lower()}"
    name = ((desk.get("storm") or {}).get("name") or "").strip().title()
    return " ".join(x for x in (cls, name) if x) or "the cyclone"


def _en_place(name: str | None) -> str:
    key = re.sub(r"\s+", " ", (name or "").strip())
    return IN_ALIAS.get(key.lower(), key)


def _en_areas(areas: list | None, limit: int = 4) -> str:
    """IMD's land area phrases as IMD wrote them ("Yanam (Puducherry)" -> "Yanam in Puducherry"); sea areas left to the
    marine warnings."""
    out = []
    for a in areas or []:
        p = re.sub(r"\s*\(([^)]*)\)", r" in \1", _en_place(a)).replace("costal", "coastal").replace("Costal", "Coastal").replace("&", "and")
        if p and not re.search(r"bay of bengal|andaman sea|arabian sea|gulf of|\bsea\b", p, re.I):
            out.append(p)
    return _en_and(list(dict.fromkeys(out))[:limit])


def _en_date(date: str, part: str = "") -> str:
    m = re.match(r"\d{4}-(\d{2})-(\d{2})", date or "")
    if not m:
        return ""
    d = f"{int(m.group(2))} {EN_MONTH[int(m.group(1)) - 1]}"
    part = (part or "").lower()
    if part in ("noon", "midnight"):
        return f"around {part} on {d}"
    return f"on the {part} of {d}" if part in IN_PART else f"on {d}"


def _en_clock(hhmm: str) -> str:
    """IMD's "2330" -> "11:30 pm", "0400" -> "4 am"."""
    h, m = int(hhmm[:2]), int(hhmm[2:])
    return f"{h % 12 or 12}{f':{m:02d}' if m else ''} {'am' if h < 12 else 'pm'}"


def _en_ist(iso: str) -> str:
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    try:
        t = _dt.fromisoformat(iso.replace("Z", "+00:00")).astimezone(_tz(_td(hours=5, minutes=30)))
    except (AttributeError, ValueError):
        return ""
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'am' if t.hour < 12 else 'pm'} IST on {t.day} {EN_MONTH[t.month - 1]}"


def in_en_now(desk: dict) -> str:
    imd = _in_imd(desk)
    ist = _en_ist(imd.get("issuedUTC", ""))
    out = [f"Here is the latest bulletin from the India Meteorological Department, issued at {ist}." if ist else
           "Here is the latest bulletin from the India Meteorological Department."]
    pos = [f"about {p['km']} km {EN_DIR[p['dir']]} of {_en_place(p['place'])}" for p in (imd.get("position") or [])[:2]
           if EN_DIR.get(p.get("dir", "")) and p.get("km") and p.get("place")]
    if pos:
        out.append(f"{_en_cap(_en_name(desk, imd.get('class_short', '')))} is centred " + " and ".join(pos) + ".")
    mv = imd.get("movement") or {}
    if EN_DIR.get(mv.get("dir", "")) and mv.get("kmh"):
        out.append(f"It is moving {EN_DIR[mv['dir']]}wards at about {mv['kmh']} km/h.")
    w, g = _range(imd.get("wind_kmh"), "en", "km/h"), _range(imd.get("gust_kmh"), "en", "km/h")
    if w:
        out.append(f"Maximum sustained winds near the centre are {w}" + (f", gusting to {g}" if g else "") + ".")
    if imd.get("pressure_hpa"):
        out.append(f"The central pressure is {imd['pressure_hpa']:g} hPa.")
    return "\n".join(out)


def in_en_landfall(desk: dict) -> str:
    imd = _in_imd(desk)
    lf = imd.get("landfall") or {}
    between = [p for p in (_en_place(x) for x in lf.get("between") or []) if p]
    near = _en_place(lf.get("near"))
    if len(between) < 2 and not near:
        raise ValueError("IMD gives no landfall place this bulletin")
    s = f"The India Meteorological Department expects {_en_name(desk, imd.get('class_short', ''))} to cross the coast"
    s += f" between {between[0]} and {between[1]}" if len(between) >= 2 else ""
    s += (f", to the {lf['near_rel']} of {near}" if lf.get("near_rel") else f", near {near}") if near else ""
    when = _en_date(lf.get("date", ""), lf.get("part_of_day", ""))
    if lf.get("time_ist"):                       # IMD's own clock times: "between 11:30 pm on 2 November and 4 am on 3 November"
        until = lf.get("until") or {}
        when = f"around {_en_clock(lf['time_ist'])} IST on {_en_date(lf['date'])[3:]}"
        if until.get("time_ist"):
            when = (f"between {_en_clock(lf['time_ist'])} on {_en_date(lf['date'])[3:]} and "
                    f"{_en_clock(until['time_ist'])} IST on {_en_date(until.get('date', ''))[3:]}")
    s += f", {when}" if when else ""
    cls = EN_CLASS.get(lf.get("class_short") or "", "")
    s += f", as a {cls.lower()}" if cls else ""
    out = [s + "."]
    w, g = _range(lf.get("wind_kmh"), "en", "km/h"), _range(lf.get("gust_kmh"), "en", "km/h")
    if w:
        out.append(f"Winds at landfall could reach {w}" + (f", gusting to {g}" if g else "") + ".")
    sg = imd.get("surge") or {}
    if sg.get("m"):
        num = lambda x: f"{x:g}" if isinstance(x, float) else str(x)
        m = sg["m"]
        h = f"{num(m[0])}-{num(m[1])}" if isinstance(m, (list, tuple)) and len(m) == 2 else num(m)
        areas = _en_areas((sg.get("peak_areas") or []) + (sg.get("peak_near") or []) or sg.get("areas"))
        out.append(f"A storm surge of about {h} m could flood low-lying areas" + (f" of {areas}" if areas else "") + ".")
    return "\n".join(out)


def _en_district_alerts(desk: dict) -> list[str]:
    """IMD's district colours (desk.json in.districts_days) for the home state, the next two days, the highest colour."""
    days = (desk.get("in") or {}).get("districts_days") or {}
    by_date: dict[str, dict[str, set]] = {}
    for st in EN_HOME_STATES:
        for district, entries in (days.get(st) or {}).items():
            for e in entries or []:
                if e.get("colour") in EN_COLOUR:
                    by_date.setdefault(e["date"], {}).setdefault(e["colour"], set()).add((EN_DISTRICT.get(district, district), st))
    out = []
    for date in [d for d in sorted(by_date) if d >= _in_today()][:2]:
        top = next((c for c in ("red", "orange", "yellow") if by_date[date].get(c)), None)
        if not top:
            continue
        ds = sorted(by_date[date][top])
        names, states = [d for d, _ in ds], sorted({s for _, s in ds})
        whom = f"{len(names)} districts, including {_en_and(names[:6])}," if len(names) > 6 else _en_and(names)
        out.append(f"{_en_cap(_en_date(date))}, the IMD has issued {EN_COLOUR[top]} for {whom} in {_en_and(states)}.")
    return out


def in_en_warnings(desk: dict) -> str:
    """Rain (three items) and wind (one) for the home region, district colours, fishermen: short enough to hear."""
    imd = _in_imd(desk)
    today = _in_today()
    rank = lambda lvl: EN_RAIN.index(lvl) if lvl in EN_RAIN else len(EN_RAIN)
    home = lambda x: any(k in re.sub(r"\([^)]*\)", " ", " ".join(x.get("areas") or []).lower()) for k in EN_HOME)
    out = []
    rain = [r for r in imd.get("rain") or [] if home(r) and (r.get("date") or today) >= today and _en_areas(r.get("areas"))]
    for r in sorted(rain, key=lambda r: (r.get("date") or "", rank((r.get("level") or "").lower())))[:3]:
        lvl = (r.get("level") or "").lower()
        if lvl in EN_RAIN:
            when = _en_date(r.get("date", ""))
            out.append((f"{_en_cap(when)}, " if when else "") + f"{lvl} rainfall is likely over {_en_areas(r.get('areas'))}.")
    winds = [w for w in imd.get("wind_warnings") or [] if home(w) and (w.get("date") or today) >= today and _en_areas(w.get("areas"))]
    for w in sorted(winds, key=lambda w: -max(w.get("kmh") or [0]))[:1]:
        k, g = _range(w.get("kmh"), "en", "km/h"), _range(w.get("gust_kmh"), "en", "km/h")
        if k:
            out.append(f"Squally winds of {k}" + (f", gusting to {g}," if g else "") + f" are likely over {_en_areas(w.get('areas'))}.")
    out += _en_district_alerts(desk)
    if imd.get("fishermen"):
        out.append("The IMD has advised fishermen not to venture into the sea.")
    if not out:
        raise ValueError("IMD gives no rain / wind / district / fishermen warning this bulletin")
    out.append("For official warnings and relief, please follow the instructions of your district administration.")
    return "\n".join(out)


def in_en_open(desk: dict) -> str:
    name = ((desk.get("storm") or {}).get("name") or "").strip().title()
    return (f"Welcome to our live coverage of Cyclone {name}. " if name else "Welcome to our live cyclone coverage. ") + \
        "We bring you the latest India Meteorological Department bulletins, the storm's track, satellite and radar, through the day."


def in_en_close(desk: dict) -> str:
    return ("These are the latest details, based on official information from the India Meteorological Department. "
            "This stream is not an official warning service. Please stay safe, stay indoors during the storm, "
            "and follow the instructions of your local authorities.")


TEMPLATES.update({"in_en_open": in_en_open, "in_en_now": in_en_now, "in_en_landfall": in_en_landfall,
                  "in_en_warnings": in_en_warnings, "in_en_close": in_en_close})
