"""QC for election scripts: deterministic checks first (numbers, alignment, wording rules), then an LLM review.

check(script, ctx) -> list[str]  problems (empty = pass); each one is phrased as feedback for the writer.
ctx: {"lang", "kind": "state"|"national", "phase", "facts": {visual: [..]}, "snapshot": {...}, "allowed_visuals": [...]}

Rules from research/election/legal.md: banned words (s7), no calls without AP (rules 1-7), nothing about counts in
preview (27-29), votes-left wording (13), balance (40), positions attributed (31), the numbers rule (every figure
said on a beat must be on that beat's graphic: what makes the narration line up with the screen).
"""
from __future__ import annotations

import json
import re

from models.lumen import get_pool

BANNED = {
    "es": ["aplastante", "arrollador", "paliza", "arrasa", "barre", "contundente", "debacle", "batacazo", "impactante", "sorpresa",
           "remontada", "colapso", "histórico", "histórica", "ola roja", "ola azul", "ultraderecha", "extrema derecha", "extrema izquierda",
           "radical", "extremista", "socialista", "comunista", "fascista", "woke", "élite", "robada", "amañada", "fraude", "trampa",
           "ilegítim", "proyectado", "proyecta", "ganará", "virtual ganador", "polémic", "cuestionado", "títere", "favorito",
           "seguro ganador", "va ganando", "va perdiendo", "en problemas", "impulso", "masiva", "decepcionante", "conservador", "progresista",
           "moderado", "MAGA", "crucial", "decisiva", "decisivo", "reñida", "reñido", "estrecha", "estrecho", "cómoda", "cómodo", "apretada", "amplia ventaja", "gran ventaja", "gran diferencia", "amplía", "ampliando", "recorta", "acorta", "remonta"],
    "ja": ["圧勝", "大勝", "地滑り", "惨敗", "完敗", "楽勝", "大敗", "衝撃", "激震", "番狂わせ", "大逆転", "崩壊", "歴史的", "赤い波", "青い波",
           "極右", "極左", "過激", "急進", "強硬派", "社会主義者", "共産主義者", "ファシスト", "エリート", "不正選挙", "盗まれ", "操作され",
           "不正", "正当性", "勝利確実", "優勢", "安泰", "問題の", "物議", "傀儡", "民主党左派", "勝ちそう", "負けそう", "有利", "不利",
           "保守派", "リベラル派", "穏健派", "予想されます", "見込みです", "確実です", "激戦", "大接戦", "天王山", "わずかに", "僅差", "大きく", "大きな差", "大差", "広がって", "縮まって", "伸ばして", "追い上げ", "引き離"],
    "zh": ["压倒性", "大胜", "惨败", "碾压", "横扫", "完胜", "震撼", "爆冷", "大逆转", "翻盘", "崩盘", "红潮", "蓝潮", "红色浪潮", "蓝色浪潮",
           "极右", "极左", "激进", "极端", "强硬派", "社会主义者", "共产", "法西斯", "精英", "舞弊", "作弊", "做票", "被偷", "操纵", "不合法",
           "稳赢", "冻蒜", "笃定", "胜券在握", "争议", "备受", "傀儡", "蓝营", "绿营", "白左", "川粉", "保守派", "自由派", "温和派", "优势明显",
           "预计将", "有望", "关键", "激烈", "微弱", "悬殊", "焦点之战", "大幅领先", "差距扩大", "差距缩小", "拉大", "缩小差距", "追赶", "反超"],
}
# a winner may be named only in a sentence that relays the AP declaration
WIN_WORDS = {"es": ["ganó", "ganador", "ganadora", "victoria", "derrotó", "gana la", "gana el"],
             "ja": ["当選", "勝利", "当確", "勝った", "敗れ", "破った"],
             "zh": ["胜选", "当选", "获胜", "赢得", "击败", "胜出"]}
AP_WORDS = {"es": ["AP", "Associated Press"], "ja": ["AP通信", "AP"], "zh": ["美联社"]}
LEAD_WORDS = {"es": ["lidera", "aventaja", "va adelante", "ventaja", "por detrás", "va detrás"],
              "ja": ["リード", "上回", "下回", "追っています", "先行"],
              "zh": ["领先", "落后"]}
REMAIN_WORDS = {"es": ["votos restantes", "quedan por contar", "faltan por contar", "del voto escrutado", "escrutado el", "% de los votos esperados"],
                "ja": ["残りの票", "残り票", "開票率", "残っている票"],
                "zh": ["剩余", "尚余", "计票率", "开票率"]}
CLOSED_WORDS = {"es": ["cerraron las urnas", "han cerrado las urnas", "urnas ya cerraron", "cierre de urnas ya"],
                "ja": ["投票が締め切られ", "投票は締め切られ", "投票を締め切り"],
                "zh": ["投票已经结束", "投票已结束", "已经截止投票", "投票截止了"]}
MAX_LINE = {"es": 190, "ja": 80, "zh": 60}
TARGET = {"state": {"es": (1100, 1600), "ja": (560, 820), "zh": (400, 600)},
          "national": {"es": (900, 1350), "ja": (420, 620), "zh": (300, 460)}}
SAFE_NUMBERS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 2020, 2022, 2024, 2026, 2027, 2028, 2030, 2032, 50, 51, 100}

_NUM = {
    "zh": re.compile(r"(\d+(?:[.,]\d+)*)\s*(亿|万|千)?(?:\s*(\d{1,4})(?=[^\d.,]|$))?"),
    "ja": re.compile(r"(\d+(?:[.,]\d+)*)\s*(億|万|千)?(?:\s*(\d{1,4})(?=[^\d.,]|$))?"),
    "es": re.compile(r"(\d+(?:[.,]\d+)*)\s*(millones|millón|mil)?"),
}
_MULT = {"亿": 1e8, "億": 1e8, "万": 1e4, "千": 1e3, "millones": 1e6, "millón": 1e6, "mil": 1e3}


def _num_value(tok: str, lang: str) -> float | None:
    if lang == "es":
        # Spanish: "." groups thousands (exactly 3 digits after), "," is the decimal mark; accept English style too
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", tok):
            return float(tok.replace(".", ""))
        if re.fullmatch(r"\d{1,3}(,\d{3})+", tok):
            return float(tok.replace(",", ""))
        return float(tok.replace(",", "."))
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", tok):
        return float(tok.replace(",", ""))
    try:
        return float(tok.replace(",", ""))
    except ValueError:
        return None


_CJK_UNIT = {"亿": 1e8, "億": 1e8, "万": 1e4, "千": 1e3}
_CJK_RUN = re.compile(r"(?:\d+(?:[.,]\d+)*\s*[亿億万千]?)+")


def _cjk_value(run: str) -> float | None:
    """'26万7千' -> 267000, '184万690' -> 1840690, '1.2万' -> 12000, '3億2000万' -> 320000000."""
    total, any_unit = 0.0, False
    for num, unit in re.findall(r"(\d+(?:[.,]\d+)*)\s*([亿億万千]?)", run):
        v = _num_value(num, "ja")
        if v is None:
            return None
        if unit:
            total += v * _CJK_UNIT[unit]
            any_unit = True
        else:
            total += v
    return total if any_unit or total else total


def numbers(text: str, lang: str) -> list[float]:
    out = []
    # clock times and dates are not figures (11:30, 11月18日, 18 de noviembre)
    text = re.sub(r"\d{1,2}:\d{2}", " ", text)
    text = re.sub(r"\d{1,2}\s*月\s*\d{1,2}\s*日", " ", text)
    text = re.sub(r"\d{1,2}\s+de\s+(noviembre|diciembre|enero)", " ", text)
    text = re.sub(r"\d{1,2}\s*(時|点|日)", " ", text)
    if lang in ("ja", "zh"):
        for m in _CJK_RUN.finditer(text):
            v = _cjk_value(m.group(0))
            if v is not None:
                out.append(v)
        return out
    text = re.sub(r"(?i)(\d+(?:,\d+)?)\s+mil\s+millones", lambda m: f"{float(m.group(1).replace(',', '.')) * 1000:g} millones", text)
    text = re.sub(r"(?i)\bmil millones\b", "1000 millones", text)
    text = re.sub(r"(?i)\bun millón\b", "1 millón", text)
    for m in _NUM["es"].finditer(text):
        v = _num_value(m.group(1), lang)
        if v is None:
            continue
        if m.group(2):
            v *= _MULT[m.group(2)]
        out.append(v)
    return out


def _allowed(facts: list[str], lang: str = "") -> list[float]:
    vals = []
    for f in facts:
        for tok in re.findall(r"\d+(?:\.\d+)?", f.replace(",", "")):
            vals.append(float(tok))
        if lang:
            vals += numbers(f, lang)
    return vals


def _supported(x: float, allowed: list[float]) -> bool:
    if x in SAFE_NUMBERS or (x == int(x) and 0 <= x <= 24):
        return True
    for a in allowed:
        if x == a:
            return True
        if x < 100 and abs(x - a) < 0.95 and a < 100:            # "52 percent" for 52.1, "4 points" for 4.4
            return True
        if x >= 100 and a >= 100 and abs(x - a) / a <= 0.012:  # "about 1.23 million" for 1,234,567
            return True
        if x >= 100 and a >= 100 and abs(x - a) / a <= 0.06 and (str(int(x)).rstrip("0") != str(int(x))):  # "about 1.2 million"
            return True
    return False


def _names_unit(text: str, uid: str, snap: dict, lang: str) -> bool:
    row = next((u for u in snap["units"]["rows"] if u["id"] == uid), None)
    if not row:
        return False
    if row["name"].lower() in text.lower():
        return True
    if lang == "es":
        return re.search(r"(?<!\w)" + re.escape(row["short"]) + r"(?!\w)", text) is not None
    return False                     # with its suffix (ハリス郡 / 哈里斯县 / 第1選挙区): no substring false hits


def _names(snap: dict, kind: str) -> dict[str, str]:
    if kind != "state":
        return {}
    return {u["id"]: u["short"] for u in snap["units"]["rows"]}


def deterministic(script: dict, ctx: dict) -> list[str]:
    lang, kind, snap, facts = ctx["lang"], ctx["kind"], ctx["snapshot"], ctx["facts"]
    P: list[str] = []
    beats = script.get("beats")
    if not isinstance(beats, list) or not beats:
        return ["The output must be JSON {\"beats\": [...]} with at least one beat."]
    allowed_vis = ctx["allowed_visuals"]
    all_text = ""
    unit_short = _names(snap, kind)
    cand_short = {c["key"]: c["short"] for c in (snap.get("cards") or [])} if kind == "state" else {}
    cand_focus = {c["key"] for c in (snap.get("candidates") or [])} | set(cand_short) if kind == "state" else set()
    seen_vis = []
    card_lines: dict[str, int] = {k: 0 for k in cand_short}
    for bi, b in enumerate(beats):
        v = b.get("visual")
        if v not in allowed_vis:
            P.append(f"Beat {bi + 1}: visual {v!r} is not allowed now; use only {allowed_vis}.")
            continue
        seen_vis.append(v)
        lines = b.get("lines") or []
        if not lines:
            P.append(f"Beat {bi + 1} ({v}) has no lines.")
        allowed = _allowed(facts.get(v, []), lang)
        for li, ln in enumerate(lines):
            t = (ln.get("text") or "").strip()
            where = f"Beat {bi + 1} ({v}), line {li + 1}"
            if not t:
                P.append(f"{where} is empty.")
                continue
            all_text += t + "\n"
            if ln.get("speaker") not in ("A", "B"):
                P.append(f"{where}: speaker must be \"A\" or \"B\".")
            if len(t) > MAX_LINE[lang]:
                P.append(f"{where} is {len(t)} characters; split it (max {MAX_LINE[lang]}).")
            if re.search(r"[\[\]{}<>#*_|]|\bfocus\b", t):
                P.append(f"{where} contains markup or brackets; write plain spoken text only.")
            for x in numbers(t, lang):
                if not _supported(x, allowed):
                    P.append(f"{where} says the number {x:g}, which is not on this beat's graphic ({v}). Use only that visual's facts.")
            if v == "st_votes_left" and re.search(r"%|por ciento|パーセント|百分之", t) and "2022" not in t:
                P.append(f"{where}: a counted share must be stated against the 2022 total (say 2022 in the sentence).")
            f = ln.get("focus")
            if f is not None and f != "":
                f = str(f)
                if v in ("st_counties", "st_votes_left", "st_history"):
                    if f not in unit_short:
                        P.append(f"{where}: focus {f!r} is not a unit id of this state.")
                    elif not _names_unit(t, f, snap, lang) and unit_short[f] not in t:
                        P.append(f"{where}: focus is {unit_short[f]} but the line does not name it; name the place you focus on.")
                elif v in ("st_candidates", "st_results"):
                    if f not in cand_focus:
                        P.append(f"{where}: focus {f!r} is not a candidate key.")
                    elif v == "st_candidates" and f in cand_short:
                        card_lines[f] += 1
                elif v == "st_senators" and f not in ("0", "1"):
                    P.append(f"{where}: senator focus must be \"0\" or \"1\".")
                elif v.startswith("nat_") and not re.fullmatch(r"[A-Z]{2}", f):
                    P.append(f"{where}: focus must be a two-letter state code.")
            # a line on a county beat that names places must focus one of them (the map highlights the focus)
            if kind == "state" and v in ("st_counties", "st_votes_left"):
                named = [uid for uid in unit_short if _names_unit(t, uid, snap, lang)]
                if named and str(ln.get("focus")) not in named:
                    P.append(f"{where} names {[unit_short[u] for u in named]} but focuses {ln.get('focus')!r}; "
                             f"set focus to one of {named}.")
    if kind == "state":
        order = [v for v in ctx["order"] if v in allowed_vis]
        missing = [v for v in order if v not in seen_vis]
        if missing:
            P.append(f"Missing visuals: {missing}. Cover every item, in this order: {order}.")
        if "st_candidates" in seen_vis and card_lines:
            lo, hi = min(card_lines.values()), max(card_lines.values())
            if lo == 0 or hi - lo > 1:
                P.append(f"Balance: on st_candidates each candidate needs lines focused on them within ±1 of each other; now {card_lines}.")
    low = all_text.lower()
    for w in BANNED[lang]:
        if lang == "es":
            stem = w.endswith(("ilegítim", "polémic"))
            hit = re.search(r"(?<!\w)" + re.escape(w.lower()) + (r"" if stem else r"(?!\w)"), low)
        else:
            hit = w in all_text
        if hit:
            P.append(f"Banned or loaded word {w!r}: rephrase neutrally.")
    has_call = bool(snap.get("call")) if kind == "state" else any(r.get("status") == "declared" for r in snap.get("races", []))
    # winner words: about TONIGHT's race only (history, senators' and candidates' careers may say who won before)
    tonight = "\n".join((ln.get("text") or "") for b in beats if b.get("visual") not in ("st_history", "st_senators", "st_candidates")
                        for ln in (b.get("lines") or []))
    for sent in re.split(r"(?<=[.!?。！？])\s*", tonight):
        if not sent.strip() or re.search(r"(19|20)[0-2]\d", sent):
            continue
        if re.search(r"まだ|ていません|ありません|出ていない|尚未|还没|没有|未宣布|aún no|todavía no|no ha |ninguna|ningún", sent):
            continue                                  # "no race has been declared yet" is true and allowed
        if any((w in sent.lower()) if lang == "es" else (w in sent) for w in WIN_WORDS[lang]):
            if not has_call:
                P.append(f"\"{sent.strip()[:60]}\": no race has been declared; do not say anyone won.")
            elif not any(a in sent for a in AP_WORDS[lang]):
                P.append(f"\"{sent.strip()[:60]}\": a winner may only be named in a sentence attributed to AP.")
    for w in REMAIN_WORDS[lang]:
        if w in (low if lang == "es" else all_text):
            P.append(f"{w!r}: votes left only as 'counted so far equals X% of the 2022 total'.")
    if kind == "state" and ctx["phase"] == "preview":
        cur = "\n".join((ln.get("text") or "") for b in beats if b.get("visual") != "st_history" for ln in (b.get("lines") or []))
        for w in LEAD_WORDS[lang] + CLOSED_WORDS[lang]:
            if (w in cur.lower()) if lang == "es" else (w in cur):
                P.append(f"{w!r}: polls are still open in {snap['state_name']}; no leads, no results, never say polls have closed.")
    n = len(re.sub(r"\s+", "", all_text)) if lang != "es" else len(all_text)
    lo, hi = TARGET[kind][lang]
    if n < lo:
        P.append(f"Too short ({n} characters); write {lo}-{hi}. Add explanation from the facts, not repetition.")
    elif n > hi * (1.6 if lang == "es" else 1.3):      # es drafts run long; a long scene beats a stale one on air
        P.append(f"Far too long ({n} characters); cut to {lo}-{hi}: drop the least important facts, you need not use them all.")
    elif n > hi:
        P.append(f"Too long ({n} characters); keep it to {lo}-{hi}.")
    if kind == "state" and snap.get("rcv") and ctx["phase"] != "preview" and snap.get("results_available"):
        rc = {"es": "primera", "ja": "第1希望", "zh": "第一选择"}[lang]
        if rc not in all_text:
            P.append(f"Ranked-choice state: say these are first-choice votes ({rc}).")
    return P


JUDGE = """You review a script for a strictly neutral, AI-narrated election-results broadcast. Report only real problems:
1. loaded or evaluative wording about candidates, parties, places or turnout (adjectives, labels, characterisations),
   including hype or intensity words such as key, crucial, fierce, slim, narrow, comfortable, big, huge, close race;
2. predictions or implications of who will win, momentum, "path to victory", "must-win", "expected", "favoured";
3. advocacy, calls to vote for/against anyone, or voting-procedure advice;
4. a claim about a winner that is not the given AP declaration;
5. imbalance: one candidate described more favourably or at greater length than the other;
6. any fact (name, number, office, position, date) that is not in the FACTS;
7. positions not attributed to the candidate ("X says/supports ...");
8. unnatural or ungrammatical sentences a native newsreader would not say.
Return JSON {"problems": ["<beat/line>: <problem> -> <fix>", ...]} (empty list if none)."""


def llm_review(script: dict, ctx: dict) -> list[str]:
    facts = json.dumps(ctx["facts"], ensure_ascii=False)
    body = json.dumps(script, ensure_ascii=False)
    try:
        raw = get_pool().chat([{"role": "system", "content": JUDGE},
                               {"role": "user", "content": f"Language: {ctx['lang']}\nFACTS:\n{facts}\n\nSCRIPT:\n{body}"}],
                              json_mode=True, max_tokens=1500, temperature=0.0)
        got = json.loads(raw).get("problems") or []
        ok = ("no issue", "no problem", "acceptable", "is correct", "is fine", "not a problem", "no change")
        return [str(x) for x in got if str(x).strip() and not any(o in str(x).lower() for o in ok)][:8]
    except Exception as error:  # noqa: BLE001
        return [] if "json" not in str(error).lower() else []


def check(script: dict, ctx: dict, use_llm: bool = True) -> tuple[list[str], list[str]]:
    """(hard problems, review notes). Hard problems block; review notes go back to the writer once."""
    hard = deterministic(script, ctx)
    review = llm_review(script, ctx) if use_llm and not hard else []
    return hard, review
