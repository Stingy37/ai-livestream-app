"""Go live on YouTube: Data API broadcast + the encoder pushing the stream page to YouTube's RTMPS ingest.

    PY=/home/andyshi2/.conda/envs/ai-livestream/bin/python
    $PY scripts/youtube_live.py --config saved_configs/japan.json --lang ja --create-only [--start 2026-10-20T21:00+09:00]
    $PY scripts/youtube_live.py --config saved_configs/japan.json --lang ja [--hours 6] [--stream japan]
    $PY scripts/youtube_live.py --config saved_configs/japan.json --lang ja --dry-run

1. Prepares the broadcast (or reuses the one --create-only prepared, kept in .run/youtube/<config>.json):
   a reusable 1080p ingest stream for this config, a broadcast bound to it, video metadata (category, tags,
   languages, synthetic-content disclosure) and a thumbnail rendered from live data (scripts/youtube_thumbnail.py).
   The title's headline is the thumbnail's, so the two always agree with each other and with the desk.
2. Starts scripts/encoder.sh with OUT = the RTMPS ingest URL + key (the key is never printed or logged).
3. Waits until YouTube reports the broadcast live (auto-start), then every minute logs the stream's health and
   restarts the encoder if it died; every --refresh-min it re-renders the thumbnail and, when the headline changed,
   updates the title and thumbnail. Ctrl+C, SIGTERM or `touch .run/STOP_YOUTUBE` (with --stream X:
   .run/STOP_YOUTUBE_X) ends the broadcast.

YOUTUBE_TITLE / YOUTUBE_DESCRIPTION override the generated text. Requires secrets/youtube_token.json
(scripts/youtube_auth.py, once). The pipeline itself (content, audio, publishing to EC2) runs separately:
scripts/run_livestream.sh with the same config.
"""

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from broadcast import youtube  # noqa: E402
import youtube_thumbnail  # noqa: E402

log = logging.getLogger("youtube")
STOP_FILE = REPO / ".run" / "STOP_YOUTUBE"
STATE_DIR = REPO / ".run" / "youtube"
PREVIEW = f"http://127.0.0.1:{os.environ.get('PREVIEW_PORT', '8095')}/"
LANGUAGE_NAMES_JA = {"en": "英語", "ja": "日本語", "tl": "タガログ語", "zh": "中国語"}
LANGUAGE_NAMES_ZH = {"en": "英語", "ja": "日語", "tl": "他加祿語", "zh": "中文"}
YT_LANGUAGE = {"zh": "zh-TW", "zh-tw": "zh-TW"}   # YouTube language codes where ours differ


# storm names in Telugu / Tamil script for the India titles (as src/desk/bulletin.py IN_STORM)
INDIA_STORM = {"ARNAB": ("అర్నాబ్", "அர்னாப்"), "MURASU": ("మురసు", "முரசு")}


def desk_storm() -> dict:
    try:
        return json.load(urllib.request.urlopen(youtube_thumbnail.stream_page() + "live/desk.json", timeout=15)).get("storm") or {}
    except OSError:
        return {}


def metadata(cfg: dict, lang: str, thumb: dict) -> dict:
    """Title, description and tags, from the same live summary the thumbnail drew; the narration language comes from the config.
    ja: 【LIVE】猛烈な台風NN号 + headline | number + topics | English.  zh (Taiwan): 【直播】強烈颱風 name + headline | number + topics.
    tl/en: LIVE + PAGASA name + headline. Key words first: phones cut titles at about 40 characters."""
    name = cfg.get("config", {}).get("name", "Typhoon Desk")
    audio = (cfg.get("defaults") or {}).get("language", "en")
    st = desk_storm() or cfg.get("config", {}).get("storm", {})
    en_storm = f"{st.get('title', 'Typhoon')} {st.get('name', '')}".strip().title()
    tx = thumb.get("text", {})
    towns = [place_ja(t) for t in tx.get("towns", [])]
    stamp = tx.get("stamp", "")
    if lang in ("te", "ta") and tx.get("l1"):   # India (Cyclone Arnab): IMD relay in Telugu / Tamil, news-style thumbnail
        # research/market/thumbnails_india.md: "Cyclone <name>" in English lifts discovery; titles that START with LIVE do
        # worse; the countdown stays out of the title (it would force an hourly title update)
        cd = r"\s*(?:తీరం దాటడానికి)?\s*\d+\s*గంటలు|\s*(?:கரையை கடக்க)?\s*(?:இன்னும்)?\s*\d+\s*மணி நேரம்"
        clean = lambda s: re.sub(r"\s*\bLIVE\b", "", re.sub(cd, "", re.sub(r"[{}\[\]]", "", s or ""))).strip()   # the title leads with LIVE already
        day = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        te = lang == "te"
        tail = "IMD తాజా అప్‌డేట్స్" if te else "IMD நேரலை அறிவிப்புகள்"
        parts = [x for x in (clean(tx["l1"]), clean(tx.get("l2")), f"{tail} {day.day}/{day.month}") if x]
        title = "Cyclone Arnab LIVE 🔴 " + " | ".join(parts)
        while len(title.encode("utf-16-le")) // 2 > 100 and len(parts) > 1:   # YouTube's limit is 100 characters
            parts.pop()                                                        # drop the tail, then the second hook
            title = "Cyclone Arnab LIVE 🔴 " + " | ".join(parts)
        lead = " ".join(clean(tx.get(k)) for k in ("l1", "l2", "l3") if clean(tx.get(k)))
        desc = "\n".join([
            lead,
            ("అర్నాబ్ తుఫాను (Cyclone Arnab) లైవ్: భారత వాతావరణ శాఖ (IMD) అధికారిక బులెటిన్లు, తుఫాను మార్గం, తీరం దాటే సమయం, "
             "జిల్లాల వారీ హెచ్చరికలు, విశాఖపట్నం - మచిలీపట్నం డాప్లర్ రాడార్ చిత్రాలు, ఉపగ్రహ చిత్రాలు నిరంతరం." if te else
             "அர்னாப் புயல் (Cyclone Arnab) நேரலை: இந்திய வானிலை ஆய்வு மையத்தின் (IMD) அதிகாரப்பூர்வ அறிக்கைகள், புயலின் பாதை, "
             "கரையைக் கடக்கும் நேரம், மாவட்ட வாரியான எச்சரிக்கைகள், டாப்ளர் ரேடார் மற்றும் செயற்கைக்கோள் படங்கள் தொடர்ந்து."),
            "",
            "■ " + ("గమనిక" if te else "குறிப்பு"),
            ("・ఈ వ్యాఖ్యానం IMD బులెటిన్ల ఆధారంగా AI స్వరంతో చదువుతున్నది. ఇది అధికారిక హెచ్చరిక సేవ కాదు." if te else
             "・இந்த விவரிப்பு IMD அறிக்கைகளின் அடிப்படையில் AI குரலில் வாசிக்கப்படுகிறது. இது அதிகாரப்பூர்வ எச்சரிக்கை சேவை அல்ல."),
            ("・హెచ్చరికలు, ఖాళీ చేయించడం, సెలవుల కోసం IMD, APSDMA, జిల్లా యంత్రాంగం ప్రకటనలను పాటించండి." if te else
             "・எச்சரிக்கைகள், வெளியேற்றம், விடுமுறை அறிவிப்புகளுக்கு IMD மற்றும் மாவட்ட நிர்வாகத்தின் அறிவிப்புகளைப் பின்பற்றவும்."),
            ("・సమయాలు భారత కాలమానం (IST)." if te else "・நேரங்கள் இந்திய நேரம் (IST)."),
            "",
            "■ IMD: https://mausam.imd.gov.in  ·  RSMC New Delhi: https://rsmcnewdelhi.imd.gov.in",
            "",
            f"{name}. Student-run cyclone desk relaying IMD bulletins with a synthetic voice. Not an official warning service.",
            "",
            ("Cyclone Arnab Live | Arnab Toofan | అర్నబ్ తుఫాన్ | Heavy Rain Alerts | AP Weather Update | Telangana Rain | IMD Red Alert"
             if te else "Cyclone Arnab Live | அர்னாப் புயல் நேரலை | Chennai Rain | Tamil Nadu Weather Update | IMD"),
            ("#CycloneArnab #అర్నాబ్తుఫాను #HeavyRainAlert #APWeather #Telangana #Kakinada #Visakhapatnam #IMD" if te else
             "#CycloneArnab #அர்னாப்புயல் #ChennaiRains #TamilNadu #IMD"),
        ])
        tags = (["Cyclone Arnab", "Cyclone Arnab live", "Arnab cyclone", "Arnab Toofan", "అర్నాబ్ తుఫాను", "అర్నబ్ తుఫాన్", "ఆర్నబ్ తుఫాన్", "తుఫాను",
                 "Heavy Rain Alerts", "AP Weather Update", "AP weather", "Telangana rain", "Red Alert AP", "Andhra Pradesh cyclone",
                 "Kakinada", "Visakhapatnam", "Vizag", "IMD", "cyclone live", "weather update",
                 "Cyclone Arnab landfall", "Kakinada cyclone", "Yanam"] if te else
                ["Cyclone Arnab", "Arnab Cyclone", "Cyclone Arnab live", "அர்னாப் புயல்", "அர்னாப் புயல் நேரலை", "புயல்",
                 "Chennai rain", "Tamil Nadu rain", "TN weather", "Tamil Nadu weather update", "IMD", "cyclone live"])   # IMD: no heavy rain for TN
        storm = (st.get("name") or "").strip()
        if storm and storm.upper() != "ARNAB":       # the wording above was written for Arnab: put the desk's storm in
            local = INDIA_STORM.get(storm.upper(), (storm.title(), storm.title()))
            swap = lambda s: re.sub("అర్నాబ్|అర్నబ్|ఆర్నబ్", local[0], re.sub("அர்னாப்", local[1], s.replace("Arnab", storm.title())))
            title, desc, tags = swap(title), swap(desc), list(dict.fromkeys(swap(t) for t in tags))
            near = youtube_thumbnail.desk_value("in", "imd", "landfall", "near") or ""
            if near and near != "Kakinada":          # the Arnab tags name its landfall (Kakinada, Yanam): use IMD's town
                desc = desc.replace("#Kakinada", f"#{near.replace(' ', '')}")
                tags = list(dict.fromkeys(t.replace("Kakinada", near) for t in tags if t != "Yanam"))
            while len(title.encode("utf-16-le")) // 2 > 100 and " | " in title:   # a longer name can push it past 100
                title = title.rsplit(" | ", 1)[0]
    elif lang == "en" and tx.get("l1") and (st.get("name") or "").upper() in INDIA_STORM:   # India in English (Indian English voice)
        # the te/ta pattern: "Cyclone <name> LIVE 🔴" + the thumbnail's lines; the countdown stays out of the title
        storm = (st.get("name") or "").strip().title()
        near = youtube_thumbnail.desk_value("in", "imd", "landfall", "near") or ""
        between = youtube_thumbnail.desk_value("in", "imd", "landfall", "between") or []
        case = lambda s: " ".join(w if w in ("IMD", "AP") else "km/h" if w == "KM/H" else w.capitalize() for w in s.split())
        cd = r"(?:IMD:\s*)?LANDFALL IN \d+ (?:HOURS|HRS)"
        clean = lambda s: case(re.sub(rf"^\s*CYCLONE {storm}\s*|\s*\bLIVE\b|{cd}", "", re.sub(r"[{}\[\]]", "", s or ""), flags=re.I).strip(" :|·-"))
        day = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        parts = [x for x in (clean(tx["l1"]), clean(tx.get("l2")), f"{near} Landfall" if near else "", f"IMD Updates {day.day}/{day.month}") if x]
        title = f"Cyclone {storm} LIVE 🔴 " + " | ".join(parts)
        while len(title.encode("utf-16-le")) // 2 > 100 and len(parts) > 1:   # YouTube's limit is 100 characters
            parts.pop(-2 if len(parts) > 2 else -1)                            # drop the landfall town, then the tail
            title = f"Cyclone {storm} LIVE 🔴 " + " | ".join(parts)
        where = (f" between {between[0]} and {between[1]}" if len(between) == 2 else "") + (f", near {near}" if near else "")
        desc = "\n".join([
            f"Cyclone {storm}: " + " · ".join(clean(tx.get(k)) for k in ("l1", "l2") if clean(tx.get(k))),
            f"Cyclone {storm} live in English: the India Meteorological Department's (IMD) official bulletins, the storm's track and "
            f"landfall on the Andhra Pradesh coast{where}, district-wise red and orange alerts, Doppler radar and satellite images, "
            "updated through the day.",
            "",
            "■ Note",
            "・The narration is read by an AI voice from IMD bulletins. It is not an official warning service.",
            "・For warnings, evacuation and school holidays, follow IMD, APSDMA and your district administration.",
            "・Times are Indian Standard Time (IST).",
            "",
            "■ IMD: https://mausam.imd.gov.in  ·  RSMC New Delhi: https://rsmcnewdelhi.imd.gov.in  ·  APSDMA: https://apsdma.ap.gov.in",
            "",
            f"{name}. Student-run cyclone desk relaying IMD bulletins with a synthetic voice. Not an official warning service.",
            "",
            " ".join(dict.fromkeys(f"#{x.replace(' ', '')}" for x in
                                   [f"Cyclone{storm}", storm, "AndhraPradesh", *between, near, "APWeather", "IMD", "CycloneLive"] if x)),
        ])
        tags = [f"Cyclone {storm}", f"Cyclone {storm} live", f"{storm} cyclone", f"{storm} landfall", "Andhra Pradesh cyclone",
                "AP weather update", "cyclone live", "IMD", "IMD red alert", "Bay of Bengal cyclone", *between, near,
                f"{near} cyclone" if near else "", "cyclone landfall live", "weather update"]
    elif lang == "ja" and tx.get("l1"):     # the news-style thumbnail (THUMB_STYLE=tw, lang=ja): its lines are the title's hooks
        clean = lambda s: re.sub(r"\s*(?:最接近まで)?\s*あと\s*\d+\s*時間", " 最接近へ", re.sub(r"[{}\[\]]", "", s or "")).strip()
        day = datetime.now(timezone(timedelta(hours=9)))
        title = f"【LIVE】{clean(tx['l1'])} {clean(tx.get('l2'))}｜最新進路・暴風域・衛星画像（気象庁発表） {day.month}/{day.day}"
        lead = "、".join(clean(tx.get(k)) for k in ("l1", "l2", "l3") if clean(tx.get(k))) + "。"
        desc = "\n".join([
            lead + f"台風第{st.get('jma_number', '')[-2:] or ''}号（{en_storm}）の最新情報を、気象庁の発表そのままにお伝えするライブ配信です。"
            "ひまわり9号の衛星画像、気象庁の予報円・進路、沖縄・先島諸島のライブカメラを随時更新しています。",
            "",
            "■ ご注意",
            "・解説は気象庁の発表内容をAI音声で読み上げたものです。独自の予報ではありません。",
            "・警報・避難情報は気象庁と各市町村の発表をご確認ください。",
            "・時刻は日本時間（JST）です。",
            "",
            "■ 公式情報",
            "気象庁 台風情報: https://www.jma.go.jp/bosai/map.html#contents=typhoon",
            "",
            "■ About",
            f"{name}. Student-run typhoon desk relaying JMA's announcements with a synthetic voice. Not an official warning service.",
            "",
            "#台風30号 #台風 #沖縄 #先島諸島 #与那国島 #石垣島 #宮古島",
        ])
        tags = ["台風30号", "台風", "台風情報", "台風 進路", "沖縄 台風", "先島諸島", "与那国島", "石垣島", "宮古島", "暴風域", "ライブ",
                en_storm, "typhoon live", "Okinawa typhoon"]
    elif lang == "ja":
        voice = "" if audio == "ja" else f"（{LANGUAGE_NAMES_JA.get(audio, audio)}解説）"
        word = tx.get("kicker", "").removesuffix("勢力で")          # 猛烈な / 非常に強い / 強い (JMA class)
        title = f"【LIVE】{word}{tx.get('num', '')} {tx.get('head', '')}｜{stamp + ' ' if stamp else ''}最新進路・衛星画像{voice}｜{en_storm} Live"
        num, _, jname = ((st.get("names") or "").split("Japan:")[-1].strip() or tx.get("num", "")).partition(" ")
        intl = f"{num}（{jname.strip()}）" if jname.strip() else num
        town, _, when = tx.get("when", "").partition(" 最接近 ")     # "与那国島 最接近 23日(金)夜遅く"
        lead = (f"{word}{intl}は中心気圧{stamp}、{tx.get('head', '')}。" + (f"{town}には{when}に最接近する見込みです。" if when else "")) if stamp else ""
        desc = "\n".join([
            lead + f"{intl}の最新情報を、気象庁などの発表に基づいてライブでお伝えします。ひまわり9号の衛星画像、気象庁の予報円と暴風域、"
            "各機関の観測値、警報・注意報を随時更新しています。",
            f"Live desk for {en_storm} (JMA {tx.get('num', '')}) near Okinawa and the Sakishima Islands: Himawari-9 satellite loops, "
            "the JMA forecast track and cone, agency-by-agency numbers and warnings, updated continuously.",
            "",
            "■ ご注意",
            f"・この配信はAI音声（{LANGUAGE_NAMES_JA.get(audio, audio)}）による自動解説です。原稿は各機関の発表をもとにAIが作成し、矛盾がないか確認しています。",
            "・気象庁などの予報を説明するもので、独自の予報ではありません。数値モデルの図（スパゲッティ図）は参考情報です。",
            "・避難の判断は、お住まいの自治体の避難情報と気象庁の警報・注意報に従ってください。",
            "・画面の時刻は日本時間（JST）です。",
            "",
            "■ 公式情報",
            "気象庁 台風情報: https://www.jma.go.jp/bosai/map.html#contents=typhoon",
            "沖縄気象台: https://www.jma-net.go.jp/okinawa/",
            "沖縄県: https://www.pref.okinawa.lg.jp/",
            "JTWC（米軍合同台風警報センター）: https://www.metoc.navy.mil/jtwc/jtwc.html",
            "",
            "■ About",
            f"{name}. Student-run typhoon desk. The script is written by AI from agency sources and checked for "
            "contradictions; the narration is a synthetic voice. Not an official warning service: follow JMA and your local government.",
            "",
            " ".join(["#" + tx.get("num", "台風"), "#台風情報", "#沖縄", "#先島諸島", "#" + en_storm.replace(" ", "")]),
        ])
        tags = [tx.get("num", ""), "台風", "台風情報", "台風 進路", "沖縄 台風", "先島諸島", *towns, "ライブ", en_storm,
                f"Typhoon {st.get('name', '').title()}", "typhoon live", "Okinawa typhoon"]
    elif lang == "zh":
        voice = "" if audio.split("-")[0] == "zh" else f"（{LANGUAGE_NAMES_ZH.get(audio, audio)}解說）"
        local = (st.get("names") or "").split("Taiwan:")[-1].split("·")[0].strip() or st.get("name", "")
        title = f"【直播】{tx.get('kicker', '')}{local} {tx.get('head', '')}｜{stamp + ' ' if stamp else ''}最新路徑・衛星雲圖{voice}｜{en_storm} Live"
        town, _, when = tx.get("when", "").partition("最接近 ")       # "台北最接近 10/24(六)清晨"
        lead = (f"{tx.get('kicker', '')}{local}中心氣壓{stamp}，{tx.get('head', '')}" + (f"，預計{when}最接近{town}。" if when else "。")) if stamp else ""
        if tx.get("l1"):         # the Taiwan news-style thumbnail (THUMB_STYLE=tw): its lines are the title's hooks
            # the countdown ("倒數12小時") stays in the thumbnail only: in the title it would force an hourly title update
            clean = lambda s: re.sub(r"\s*倒數\s*\d+\s*小時", "", re.sub(r"[{}\[\]]", "", s or "")).strip()
            day = datetime.now(timezone(timedelta(hours=8)))
            title = f"【LIVE】{clean(tx['l1'])} {clean(tx.get('l2'))}｜各縣市颱風假・豪雨強風特報・最新路徑・各地即時影像 {day.month}/{day.day}"
            lead = "，".join(clean(tx.get(k)) for k in ("l1", "l2", "l3") if clean(tx.get(k))) + "。"
        desc = "\n".join([
            lead + f"{local}颱風（{en_storm}）最新動態直播：各縣市停班停課一覽（行政院人事行政總處）、中央氣象署颱風警報與豪雨／強風特報、"
            "台灣各地即時影像、向日葵9號衛星雲圖、各國氣象機關（中央氣象署、日本氣象廳、JTWC）的路徑預報與觀測數值，持續自動更新。",
            f"Live desk for {en_storm} near Taiwan: Himawari-9 satellite, official forecast tracks, agency numbers and warnings.",
            "",
            "■ 注意",
            f"・本直播為AI語音（{LANGUAGE_NAMES_ZH.get(audio.split('-')[0], audio)}）自動解說，內容由AI依各機關發布資料撰寫並經一致性檢查。",
            "・本直播說明官方預報，並非獨立預報；數值模式圖（系集路徑）僅供參考。",
            "・海上／陸上颱風警報以中央氣象署發布為準；停班停課以各縣市政府公告為準。",
            "・畫面時間為台灣時間（UTC+8）。",
            "",
            "■ 官方資訊",
            "中央氣象署 颱風消息: https://www.cwa.gov.tw/V8/C/P/Typhoon/TY_NEWS.html",
            "行政院人事行政總處 停班停課資訊: https://www.dgpa.gov.tw/typh/daily/nds.html",
            "日本氣象廳 颱風資訊: https://www.jma.go.jp/bosai/map.html#contents=typhoon",
            "",
            "■ About",
            f"{name}. Student-run typhoon desk. AI-written from agency sources and checked for contradictions; synthetic voice. "
            "Not an official warning service: follow CWA and your local government.",
            "",
            " ".join([f"#{local}颱風", "#颱風假", "#停班停課", "#颱風", "#颱風路徑", "#" + en_storm.replace(" ", "")]),
        ])
        tags = [f"{local}颱風", local, "颱風假", "停班停課", "颱風", "颱風路徑", "颱風動態", "海上陸上颱風警報", "豪雨特報", "即時影像",
                "衛星雲圖", "中央氣象署", "直播", en_storm,
                f"Typhoon {st.get('name', '').title()}", "Taiwan typhoon", "typhoon live"]
    elif tx.get("num"):
        local = tx["num"].split()[-1].title()
        head = tx.get("head", "").title()
        title = f"LIVE: {tx['num'].title()} ({en_storm}) — {head}{' | ' + stamp.replace('km/h', ' km/h') if stamp else ''}"
        ph = tx.get("when", "")
        desc = "\n".join([
            f"{tx['num'].title()} ({en_storm}): {head.replace(': ', ' sa ')}. Lakas ng hangin {stamp.replace('km/h', ' km/h')}. {ph + '.' if ph else ''}".strip(),
            f"Live na update sa Bagyong {local}: Himawari-9 satellite, landas at taya ng PAGASA, JMA at JTWC, mga Wind Signal at "
            "pinakamalapit na paglapit sa Batanes at Northern Luzon. Tuloy-tuloy na ina-update.",
            f"Live updates on Typhoon {local} ({en_storm}): satellite, official PAGASA / JMA / JTWC tracks, wind signals and closest approach.",
            "",
            "■ PAALALA / NOTE",
            "• Ang narration ay AI voice. Ang script ay isinulat ng AI mula sa mga opisyal na bulletin at sinuri kung may salungatan.",
            "• Hindi ito opisyal na babala. Sundin ang PAGASA, NDRRMC at ang inyong LGU para sa babala at paglikas.",
            "• Oras sa screen: Philippine time (UTC+8).",
            "",
            "■ OPISYAL NA IMPORMASYON",
            "PAGASA Tropical Cyclone Bulletin: https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin",
            "NDRRMC: https://ndrrmc.gov.ph/",
            "",
            "■ About",
            f"{name}. Student-run typhoon desk. AI-written from agency sources and checked for contradictions; synthetic voice.",
            "",
            f"#Bagyong{local} #{local}PH #PAGASA #{en_storm.replace(' ', '')}",
        ])
        tags = [f"Bagyong {local}", en_storm, "typhoon", "typhoon live", "PAGASA", "bagyo", *tx.get("towns", [])]
    else:
        title = f"LIVE: {name}"
        desc = (f"{name}. A continuously updating student-run typhoon desk: agency positions and forecasts, satellite loops, "
                "closest-approach maps and AI-written, fact-checked updates read by a synthetic voice. Always follow your national "
                "weather agency and local government for warnings and evacuation decisions.")
        tags = [en_storm, "typhoon", "typhoon live", *tx.get("towns", [])]
    tags = [t for t in dict.fromkeys(tags) if t]
    while sum(len(t) + 2 for t in tags) > 480:          # YouTube's tag budget is 500 characters
        tags.pop()
    return {"title": os.environ.get("YOUTUBE_TITLE") or file_title() or title, "description": os.environ.get("YOUTUBE_DESCRIPTION") or desc,
            "tags": tags, "language": YT_LANGUAGE.get(lang, lang or "en"), "audio_language": YT_LANGUAGE.get(audio, audio)}


def file_title() -> str:
    """YOUTUBE_TITLE_FILE's first line: a title that can change while live (title experiments), "" when unset or empty."""
    path = os.environ.get("YOUTUBE_TITLE_FILE", "")
    try:
        return Path(path).read_text(encoding="utf-8").strip().splitlines()[0][:100] if path else ""
    except (OSError, IndexError):
        return ""


def place_ja(name: str) -> str:
    return {"Yonaguni": "与那国島", "Ishigaki": "石垣島", "Miyakojima": "宮古島", "Naha": "那覇"}.get(name, name)


def apply_metadata(bc_id: str, meta: dict, thumb_path: Path, yt) -> None:
    youtube.update_video(bc_id, meta["title"], meta["description"], meta["tags"], language=meta["language"],
                         audio_language=meta["audio_language"], synthetic=True, yt=yt)
    try:
        youtube.set_thumbnail(bc_id, thumb_path, yt)
    except Exception as error:  # noqa: BLE001 - a missing thumbnail must not block the stream
        log.warning("thumbnail upload failed (custom thumbnails need a phone-verified channel): %s", error)


def prepare(a, cfg: dict, yt, start: datetime | None) -> dict:
    stem = Path(a.config).stem
    thumb_path, thumb = youtube_thumbnail.render(a.lang)
    meta = metadata(cfg, a.lang, thumb)
    stream = youtube.ensure_stream(f"encoder-{stem}", yt)
    bc = youtube.create_broadcast(meta["title"], meta["description"], stream["id"], a.privacy, yt, start=start)
    apply_metadata(bc["id"], meta, thumb_path, yt)
    state = {"broadcast_id": bc["id"], "stream_id": stream["id"], "privacy": a.privacy, "lang": a.lang, "title": meta["title"],
             "headline": thumb.get("text", {}).get("head"), "created": datetime.now(timezone.utc).isoformat()}
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / f"{stem}.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("broadcast %r created (%s): https://youtube.com/watch?v=%s", meta["title"], a.privacy, bc["id"])
    return state


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(REPO / "saved_configs" / "example.json"))
    ap.add_argument("--lang", default="", help="page language, e.g. ja or tl (the page's ?lang=)")
    ap.add_argument("--stream", default=os.environ.get("EC2_STREAM_ID", ""),
                    help="EC2 stream to broadcast (its page /s/<id>/); the same EC2_STREAM_ID the pipeline publishes to")
    ap.add_argument("--privacy", default=os.environ.get("YOUTUBE_PRIVACY", "unlisted"), choices=["public", "unlisted", "private"])
    ap.add_argument("--hours", type=float, default=float(os.environ.get("YOUTUBE_HOURS", "6")))
    ap.add_argument("--start", default="", help="scheduled start shown to viewers, ISO time (default: in one hour)")
    ap.add_argument("--refresh-min", type=float, default=float(os.environ.get("YOUTUBE_REFRESH_MIN", "60")))
    ap.add_argument("--create-only", action="store_true", help="prepare the broadcast (metadata + thumbnail) and exit")
    ap.add_argument("--new", action="store_true", help="ignore a prepared broadcast and create a new one")
    ap.add_argument("--dry-run", action="store_true", help="create nothing; render the thumbnail and print the metadata")
    a = ap.parse_args()
    stop_file = STOP_FILE
    if a.stream:
        os.environ["EC2_STREAM_ID"] = a.stream      # encoder.sh and the thumbnail read it
        stop_file = STOP_FILE.with_name(f"STOP_YOUTUBE_{a.stream}")   # stop one stream without touching the others
    logging.basicConfig(level="INFO", format="%(asctime)s  %(levelname)-7s  %(message)s")

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    yt = youtube.service()
    ch = youtube.channel(yt)
    log.info("channel: %s", ch.get("snippet", {}).get("title", "?"))
    if a.dry_run:
        thumb_path, thumb = youtube_thumbnail.render(a.lang)
        print(json.dumps(dict(metadata(cfg, a.lang, thumb), thumbnail=str(thumb_path)), ensure_ascii=False, indent=2))
        return 0

    start = datetime.fromisoformat(a.start) if a.start else datetime.now(timezone.utc) + timedelta(hours=1)
    state_path = STATE_DIR / f"{Path(a.config).stem}.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() and not a.new else None
    if state and youtube.broadcast_status(state["broadcast_id"], yt) not in ("created", "ready", "testing", "testStarting"):
        log.info("prepared broadcast %s is no longer usable; creating a new one", state["broadcast_id"])
        state = None
    if state is None:
        state = prepare(a, cfg, yt, start)
    else:
        log.info("using prepared broadcast https://youtube.com/watch?v=%s", state["broadcast_id"])
    if state.get("privacy") != a.privacy:                  # e.g. prepared unlisted, going live public
        youtube.set_privacy(state["broadcast_id"], a.privacy, yt)
        state["privacy"] = a.privacy
        log.info("broadcast privacy set to %s", a.privacy)
    if a.create_only:
        return 0

    bc_id = state["broadcast_id"]
    stream = next(s for s in yt.liveStreams().list(part="id,snippet,cdn,status", id=state["stream_id"]).execute()["items"])
    youtube.bind(bc_id, stream["id"], yt)
    url, key = youtube.ingest(stream)
    env = dict(os.environ, OUT=f"{url}/{key}", STREAM_LANG=a.lang)
    enc_log = open(REPO / ".run" / "encoder" / "youtube_encoder.log", "a")
    start_encoder = lambda: subprocess.Popen(["bash", str(REPO / "scripts" / "encoder.sh")], env=env, stdout=enc_log,
                                            stderr=subprocess.STDOUT, start_new_session=True)
    enc = start_encoder()
    stopping = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stopping.update(flag=True))
    signal.signal(signal.SIGINT, lambda *_: stopping.update(flag=True))
    stop_file.unlink(missing_ok=True)

    status = youtube.go_live(bc_id, wait_s=180, yt=yt)
    log.info("broadcast status: %s", status)
    deadline = time.time() + a.hours * 3600
    next_refresh = time.time() + a.refresh_min * 60
    health_every = float(os.environ.get("YOUTUBE_HEALTH_MIN", "10")) * 60    # 2 quota units per check: every minute = 2,880/day
    next_health = 0.0
    try:                                                    # the thumbnail summary the description and tags come from
        last_thumb = json.loads((REPO / "output" / "youtube" / f"thumb_{a.lang or 'en'}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last_thumb = {}
    try:
        while not stopping["flag"] and time.time() < deadline and not stop_file.exists():
            time.sleep(60)
            if enc.poll() is not None:
                log.warning("encoder exited (rc %s); restarting", enc.returncode)
                enc = start_encoder()
            if time.time() >= next_health:
                next_health = time.time() + health_every
                try:
                    h = youtube.health(stream["id"], yt)
                    log.info("stream %s, health %s, broadcast %s", h.get("streamStatus"), (h.get("healthStatus") or {}).get("status"),
                             youtube.broadcast_status(bc_id, yt))
                except Exception as error:  # noqa: BLE001 - monitoring must never stop the stream
                    log.warning("health check failed: %s", error)
            ft = file_title()
            if ft and ft != state.get("title") and not os.environ.get("YOUTUBE_TITLE"):   # YOUTUBE_TITLE_FILE changed
                try:
                    meta = metadata(cfg, a.lang, last_thumb)
                    yt = youtube.service()
                    youtube.update_video(bc_id, meta["title"], meta["description"], meta["tags"], language=meta["language"],
                                         audio_language=meta["audio_language"], yt=yt)
                    state["title"] = meta["title"]
                    log.info("title set from %s: %s", os.environ["YOUTUBE_TITLE_FILE"], meta["title"])
                except Exception as error:  # noqa: BLE001
                    log.warning("title update failed: %s", error)
            if a.refresh_min > 0 and time.time() >= next_refresh and not os.environ.get("YOUTUBE_TITLE"):
                next_refresh = time.time() + a.refresh_min * 60
                try:
                    thumb_path, thumb = youtube_thumbnail.render(a.lang)
                    last_thumb = thumb
                    meta = metadata(cfg, a.lang, thumb)
                    # a fresh client: after an idle hour the old connection is gone, and uploads (POST) are not retried
                    yt = youtube.service()
                    if meta["title"] != state.get("title"):
                        apply_metadata(bc_id, meta, thumb_path, yt)
                        state["title"] = meta["title"]
                        log.info("headline changed; title and thumbnail updated: %s", meta["title"])
                    else:
                        youtube.set_thumbnail(bc_id, thumb_path, yt)   # same headline, newer satellite frame
                except Exception as error:  # noqa: BLE001
                    log.warning("thumbnail refresh failed: %s", error)
    finally:
        log.info("ending broadcast")
        try:
            os.killpg(enc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            youtube.end(bc_id, yt)
        except Exception as error:  # noqa: BLE001
            log.warning("could not end the broadcast via the API: %s", error)
        state_path.unlink(missing_ok=True)
        stop_file.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
