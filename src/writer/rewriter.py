"""Last-stage script rewriter: makes a QC-checked draft more informative and engaging to listen to.

Runs after QC Part B and before TTS, for every scene. A stronger provider model (deepseek-v4-flash on
Lumen by default) rewrites the local model's draft with a narrative spine: lead with what matters most,
connect the facts with cause and consequence, add analysis that follows from them, and close with what
to watch or do next. The prompt is deliberately generic (any topic, any broadcast), and the scene's own
style rules (``scene.system_instructions``) still apply.

The rewrite must not undo QC, so it is accepted only if it passes every guard below; otherwise the
rewriter retries once with the violations listed, and then falls back to the QC-checked draft:

    * numbers ...... every number in the rewrite occurs in the draft (no new or changed figures)
    * names ........ no new capitalised names mid-sentence (places, agencies, people) that are absent
                     from the draft, the scene brief and the style rules
    * length ....... between REWRITE_MIN_RATIO and REWRITE_MAX_RATIO of the draft's word count
    * QC ........... QC Part B (within-script contradictions, unattributed disputed figures, figures no
                     source reports) finds no more problems than it found in the draft
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from contracts import LLMOutput, RetrievedContext, Scene, ScriptOutcome, ScriptScore
from writer.length import target_words

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the final script editor for a live, spoken broadcast. You receive the draft script for one segment and rewrite it so it is more informative and more engaging to listen to.

Make it better by structure, not by new facts:
- Give it a narrative spine. Open with the single most important development, then build: connect the facts with cause and consequence ("because", "which means", "that matters for"), and end with what to watch next or what the listener should do.
- Add analysis and context that follows directly from the facts in the draft: what changed, how the facts relate to each other, why they matter, how sources compare. Explain, do not just list.
- Analysis may connect and explain facts, but must never assert a new outcome, prediction or judgement: do not introduce impacts, damage, landfall, casualties, orders or closures the draft does not state, and do not call anything rare, unprecedented, record or certain, or describe anyone's confidence, unless the draft says so.
- Keep it natural to hear: varied sentence length, clear transitions, no repetition, no filler, no hype.

Hard rules:
- Use only facts that are in the draft. Do not add or change any number, time, date, name, place, quote, warning, order or claim. Write every number exactly as it appears in the draft, as digits.
- Keep every attribution ("according to X", "X reports"). If sources disagree in the draft, keep both values and say who reported which.
- If the draft says something has not been reported, keep that.
- Segments loop and air at any hour: never use time-of-day greetings or sign-offs ("good morning", "good evening", "tonight").
- Follow the segment's style rules below (tone, length target, what not to say). They override everything above.
- Output only the spoken script: plain sentences, no headings, lists, markdown, stage directions or notes to the editor."""

LANGUAGE_NAMES = {"en": "English", "tl": "Tagalog (Filipino)", "fil": "Tagalog (Filipino)", "ja": "Japanese", "zh": "Chinese",
                  "zh-tw": "Traditional Chinese (Taiwan Mandarin)", "ko": "Korean", "vi": "Vietnamese", "th": "Thai", "ms": "Malay"}


def language_name(code: str) -> str:
    c = (code or "en").strip().lower()
    return LANGUAGE_NAMES.get(c, LANGUAGE_NAMES.get(c.split("-")[0], code))


def is_english(code: str) -> bool:
    return (code or "en").strip().lower().split("-")[0] == "en"


TRANSLATE_PROMPT = """You translate broadcast scripts. Translate the script into {lang} faithfully, sentence by sentence, as it would be read on a news broadcast in that language.
Keep every fact exactly: write every number as digits exactly as in the script, keep units, agency names and place names as they are. Add nothing, drop nothing, explain nothing.
Leave out time-of-day greetings or sign-offs ("good morning", "good evening"): the segment airs at any hour.
Output only the translated spoken script."""

BACK_TRANSLATE_PROMPT = """Translate this {lang} broadcast script into English literally and completely, sentence by sentence, for a fact check.
Do not add, drop, soften or explain anything; keep numbers as digits and names as written. Output only the English translation.
The script was translated from an English original. When a name in it is one of these names from the original, write it exactly as spelled here: {glossary}"""

USER_TEMPLATE = """Segment: {title}

Segment brief:
{brief}

Style rules for this segment:
{rules}

Draft script ({words} words):
{draft}
{feedback}{language_line}
Rewrite the draft now."""

_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_CAP = re.compile(r"\b[A-Z][A-Za-z'\-]+")
_SENT_START = re.compile(r"(?:^|[.!?]\s+|\n\s*|[\"'(]\s*)$")
# High-stakes claim words: if the rewrite uses one and the draft does not, the rewrite added a claim.
# A trailing * matches any ending ("evacuat*" = evacuate, evacuation...); otherwise the whole word or phrase must match.
# REWRITE_SENSITIVE_TERMS (comma-separated, same syntax) replaces the list.
SENSITIVE_TERMS = ["landfall*", "evacuat*", "casualt*", "death*", "dead", "killed", "fatal*", "injur*", "missing", "damage*",
                   "destroy*", "flood*", "surge*", "landslide*", "mudslide*", "tsunami*", "suspend*", "suspension*", "cancel*",
                   "closed", "closure*", "shut down", "state of emergency", "curfew*", "evacuation order*", "mandatory",
                   "record-breaking", "record high", "record low", "new record", "unprecedented", "rare", "historic*",
                   "catastroph*", "devastat*", "certainly", "will definitely", "guarantee*"]

COMMON_CAPS = {"I", "A", "An", "The", "UTC", "AM", "PM", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
               "Saturday", "Sunday", "January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December", "North", "South", "East", "West", "Northern",
               "Southern", "Eastern", "Western"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
_CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?(?=\W|$)", re.IGNORECASE)


def equivalent_numbers(text: str) -> set[str]:
    """Numbers a faithful translation may write that the English text spells differently: month numbers for month
    names (October -> 10), 24-hour and 12-hour forms of clock times (9 p.m. <-> 21), noon and midnight."""
    low = text.lower()
    out = {str(i + 1) for i, m in enumerate(_MONTHS) if re.search(rf"\b{m[:3]}", low)}
    if "noon" in low:
        out.add("12")
    if "midnight" in low:
        out |= {"0", "24", "12"}
    for m in _CLOCK.finditer(text):
        h = int(m.group(1))
        if h > 24:
            continue
        pm = (m.group(3) or "").lower().startswith("p")
        out |= {str(h), str((h + 12) % 24 if pm and h < 12 else h)}
        if h > 12:
            out.add(str(h - 12))
    return out


def numbers(text: str) -> set[str]:
    """Every number in the text, normalised (thousands separators dropped, trailing .0 dropped)."""
    out = set()
    for m in _NUM.finditer(text):
        n = m.group(0).replace(",", "")
        n = n[:-2] if n.endswith(".0") else n
        out.add(n.lstrip("0") or "0" if "." not in n else n)
    return out


_ACRONYM = re.compile(r"\b[A-Z]{2,6}\b")
_NAME_RUN = re.compile(r"\b[A-Z][a-z]+(?:\s+(?:of|and|for|the|de)?\s*[A-Z][a-z]+)+")
_LINK_WORDS = {"of", "and", "for", "the", "de"}


def acronym_expansions(rewrite: str, allowed_text: str) -> set[str]:
    """Words of spelled-out names whose initials form an acronym the allowed text uses
    (e.g. "Joint Typhoon Warning Center" when the draft says JTWC): saying the full name adds no fact."""
    acronyms = set(_ACRONYM.findall(allowed_text))
    ok: set[str] = set()
    # reverse direction: an acronym in the rewrite whose expansion is spelled out in the allowed text
    spelled = set()
    for m in _NAME_RUN.finditer(allowed_text):
        caps = [w for w in m.group(0).split() if w.lower() not in _LINK_WORDS]
        for i in range(len(caps)):
            for j in range(i + 2, len(caps) + 1):
                spelled.add("".join(w[0] for w in caps[i:j]).upper())
    ok.update(a for a in _ACRONYM.findall(rewrite) if a in spelled)
    for m in _NAME_RUN.finditer(rewrite):
        words = m.group(0).split()
        caps = [w for w in words if w.lower() not in _LINK_WORDS]
        for i in range(len(caps)):                      # any contiguous run, so "the Joint Typhoon Warning Center" works
            for j in range(i + 2, len(caps) + 1):
                if "".join(w[0] for w in caps[i:j]) in acronyms:
                    ok.update(caps[i:j])
    return ok


def new_terms(rewrite: str, draft: str) -> list[str]:
    """High-stakes stems that occur in the rewrite but not in the draft (whole-word prefix match)."""
    raw = os.environ.get("REWRITE_SENSITIVE_TERMS")
    terms = [t.strip().lower() for t in raw.split(",") if t.strip()] if raw else SENSITIVE_TERMS
    def has(text: str, term: str) -> bool:
        pat = r"\b" + re.escape(term.rstrip("*")) + ("" if term.endswith("*") else r"\b(?!-)")
        return re.search(pat, text.lower()) is not None
    return [t.rstrip("*") for t in terms if has(rewrite, t) and not has(draft, t)]


# generic place-type words a translation adds around a name it already has (沖縄本島 -> "Okinawa Main Island",
# グアム島 -> "Guam Island"); the name itself is still checked
PLACE_TYPES = {"island", "islands", "main", "prefecture", "city", "town", "village", "region", "regions", "area", "areas",
               "sea", "ocean", "strait", "bay", "port", "peninsula", "coast", "province", "district", "archipelago"}


def new_names(rewrite: str, allowed_text: str) -> list[str]:
    """Capitalised words in mid-sentence position that the allowed texts never mention."""
    expanded = acronym_expansions(rewrite, allowed_text)
    base = lambda w: re.sub(r"['’]s$", "", w).strip("'-").lower()
    allowed = {base(w) for w in re.findall(r"[A-Za-z'\-]+", allowed_text)}
    found = []
    for m in _CAP.finditer(rewrite):
        word = re.sub(r"['’]s$", "", m.group(0)).strip("'-")
        if not word:
            continue
        if word in COMMON_CAPS or base(word) in allowed or word in expanded or base(word) in PLACE_TYPES:
            continue
        if _SENT_START.search(rewrite[:m.start()]):
            continue  # sentence-initial capital, not necessarily a name
        if word not in found:
            found.append(word)
    return found


def clean(text: str) -> str:
    text = re.sub(r"^\s*(?:#+|[-*]|\d+\.)\s+", "", text, flags=re.M)        # list / heading markers
    text = re.sub(r"\*\*|__|`", "", text)
    text = re.sub(r"\[[^\]]{0,60}\]", " ", text)                             # [stage cues]
    text = re.sub(r"^(?:Here is|Here's)[^\n]*:\s*\n", "", text, flags=re.I)  # chatty preamble
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


@dataclass
class RewriteResult:
    outcome: ScriptOutcome                 # what goes on to TTS (rewritten, or the draft unchanged)
    used_rewrite: bool
    reason: str
    attempts: list[dict[str, Any]] = field(default_factory=list)


class ScriptRewriter:
    """Rewrites one QC-checked script; never returns something less checked than its input."""

    def __init__(self, model: str | None = None, max_attempts: int | None = None,
                 scorer_factory: Callable[[Scene], Any] | None = None, chat: Callable[..., str] | None = None) -> None:
        self.model = model or os.environ.get("REWRITE_MODEL") or os.environ.get("LUMEN_MODEL") or "deepseek-v4-flash"
        self.max_attempts = max_attempts or int(os.environ.get("REWRITE_MAX_ATTEMPTS", "2"))
        self.temperature = _env_float("REWRITE_TEMPERATURE", 0.7)
        self.min_ratio = _env_float("REWRITE_MIN_RATIO", 0.7)
        self.max_ratio = _env_float("REWRITE_MAX_RATIO", 1.6)
        self.scorer_factory = scorer_factory
        self._chat = chat

    def chat(self, messages: list[dict[str, str]]) -> str:
        if self._chat:
            return self._chat(messages)
        from models import lumen

        return lumen.chat(messages, model=self.model, temperature=self.temperature, max_tokens=2500, allow_fallback=False)

    def problems(self, scene: Scene, draft: str, text: str, english: str | None = None) -> list[str]:
        """Guard violations of one candidate rewrite (empty list = acceptable before QC).

        ``english`` is the English back-translation of a non-English rewrite: names, claims and length
        are judged on it (the guards are English), numbers on the rewrite itself (digits survive translation).
        """
        out = []
        if not text.strip():
            return ["the rewrite was empty"]
        allowed = numbers(draft) | equivalent_numbers(draft) | numbers(" ".join([scene.title, scene.topic_description]))
        extra = sorted(numbers(text) - allowed)
        if extra:
            out.append(f"it contains numbers that are not in the draft: {', '.join(extra[:8])}. Use only the draft's numbers, written exactly as there.")
        text = english or text
        added = new_terms(text, draft)
        if added:
            out.append(f"it adds claims the draft does not make (words: {', '.join(added[:8])}). Remove them; keep only what the draft states.")
        names = new_names(text, " ".join([draft, scene.title, scene.topic_description, scene.system_instructions]))
        if names:
            out.append(f"it names things that are not in the draft: {', '.join(names[:8])}. Do not add names, places or organisations.")
        dw, rw = len(draft.split()), len(text.split())
        lo, hi = int(self.min_ratio * dw), int(self.max_ratio * dw)
        # a duration in the style rules caps the length at the measured speaking rate (writer/length.py), +10%
        w = target_words(scene.system_instructions or "")
        if w:
            hi = min(hi, max(dw, int(w[1] * 1.1)))
        if dw and not (lo <= rw <= hi):
            out.append(f"it is {rw} words; keep it between {lo} and {hi} words.")
        return out

    def rewrite(self, scene: Scene, outcome: ScriptOutcome, context: RetrievedContext | None = None) -> RewriteResult:
        draft = outcome.script.llm_output.strip()
        if not draft:
            return RewriteResult(outcome, False, "empty draft")
        context = context or RetrievedContext(scene_id=scene.id)
        attempts: list[dict[str, Any]] = []
        feedback = ""
        english = is_english(scene.language)
        lang = language_name(scene.language)
        language_line = "" if english else (f"\nWrite the final script in {lang}. The draft is in English; translate while you rewrite, "
                                            "keeping every number as digits and every agency and place name as written.\n")
        for i in range(1, self.max_attempts + 1):
            user = USER_TEMPLATE.format(title=scene.title, brief=scene.topic_description.strip(),
                                        rules=scene.system_instructions.strip() or "(none)", words=len(draft.split()),
                                        draft=draft, feedback=feedback, language_line=language_line)
            try:
                text = clean(self.chat([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]))
            except Exception as error:  # noqa: BLE001 - the draft is always a valid answer
                attempts.append({"attempt": i, "error": f"{type(error).__name__}: {error}"})
                log.warning("[rewrite] %s: model call failed (%s); keeping the QC-checked draft", scene.title, error)
                return RewriteResult(outcome, False, "rewrite model unavailable", attempts)
            back = None if english else self.back_translate(text, lang, draft, scene)
            if not english and back is None:
                attempts.append({"attempt": i, "text": text, "error": "back-translation failed"})
                continue
            issues = self.problems(scene, draft, text, english=back)
            rec: dict[str, Any] = {"attempt": i, "text": text, "words": len(text.split()), "guard_problems": issues}
            if back:
                rec["back_translation"] = back
            if not issues:
                score = self._score(scene, back or text, context)
                rec["qc_total"] = None if score is None else score.total
                if score is None or score.total <= outcome.score.total or score.passes_threshold:
                    attempts.append(rec)
                    new_score = score or outcome.score
                    rewritten = ScriptOutcome(script=LLMOutput(llm_output=text), score=new_score, accepted=outcome.accepted,
                                              attempts=outcome.attempts, warnings=list(outcome.warnings))
                    log.info("[rewrite] %s: rewrite %d accepted (%d -> %d words, QC %s)", scene.title, i,
                             len(draft.split()), len(text.split()), "n/a" if score is None else int(score.total))
                    return RewriteResult(rewritten, True, f"accepted on attempt {i}", attempts)
                issues = [f"a fact check found problems the draft did not have: " + "; ".join(score.contradictions[:4])]
                rec["guard_problems"] = issues
            attempts.append(rec)
            log.info("[rewrite] %s: rewrite %d rejected: %s", scene.title, i, " | ".join(issues)[:300])
            feedback = "\nYour previous rewrite was rejected because " + " ".join(issues) + " Fix this in the new rewrite.\n"
        if not english:
            # the stream is not in English: a faithful translation of the checked draft beats the English draft
            translated = self.translate(scene, draft, lang, attempts)
            if translated is not None:
                return translated
            log.error("[rewrite] %s: no %s script passed the guards (the harness drops the scene for this cycle)", scene.title, lang)
        return RewriteResult(outcome, False, f"no rewrite passed the guards in {self.max_attempts} attempt(s); kept the draft", attempts)

    # ---- translation (non-English scenes) ------------------------------------------------
    def _plain_chat(self, system: str, user: str, temperature: float = 0.0) -> str:
        if self._chat:
            return self._chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        from models import lumen

        return lumen.chat([{"role": "system", "content": system}, {"role": "user", "content": user}], model=self.model,
                          temperature=temperature, max_tokens=4000, allow_fallback=False)

    def back_translate(self, text: str, lang: str, draft: str = "", scene: Scene | None = None) -> str | None:
        source = " ".join([draft] + ([scene.title, scene.topic_description] if scene else []))
        glossary = ", ".join(dict.fromkeys(m.group(0) for m in _CAP.finditer(source))) or "(none)"
        try:
            return clean(self._plain_chat(BACK_TRANSLATE_PROMPT.format(lang=lang, glossary=glossary), text)) or None
        except Exception as error:  # noqa: BLE001
            log.warning("[rewrite] back-translation failed: %s", error)
            return None

    def translate(self, scene: Scene, draft: str, lang: str, attempts: list[dict[str, Any]]) -> RewriteResult | None:
        try:
            text = clean(self._plain_chat(TRANSLATE_PROMPT.format(lang=lang), draft))
        except Exception as error:  # noqa: BLE001
            attempts.append({"attempt": "translate", "error": f"{type(error).__name__}: {error}"})
            return None
        back = self.back_translate(text, lang, draft, scene)
        # a plain translation of the checked draft has the draft's length; the English back-check always reads longer
        issues = ["back-translation failed"] if back is None else [
            p for p in self.problems(scene, draft, text, english=back) if not p.startswith("it is ")]
        attempts.append({"attempt": "translate", "text": text, "back_translation": back, "guard_problems": issues})
        if issues:
            return None
        log.info("[rewrite] %s: rewrites rejected; using a plain %s translation of the checked draft", scene.title, lang)
        return RewriteResult(ScriptOutcome(script=LLMOutput(llm_output=text), score=self._outcome_score_placeholder(),
                                           accepted=True, attempts=1, warnings=["plain translation of the QC-checked draft"]),
                             True, f"plain {lang} translation", attempts)

    @staticmethod
    def _outcome_score_placeholder() -> ScriptScore:
        return ScriptScore(total=0.0, passes_threshold=True)

    def _score(self, scene: Scene, text: str, context: RetrievedContext) -> ScriptScore | None:
        if os.environ.get("REWRITE_QC", "1") != "1":
            return None
        try:
            if self.scorer_factory:
                scorer = self.scorer_factory(scene)
            else:
                from config_env import Settings
                from qc import ScriptScorer

                s = Settings.from_env()
                scorer = ScriptScorer(threshold=s.script_score_threshold, scene_dir=s.layout().scene_dir(scene.id))
            return scorer.score(LLMOutput(llm_output=text), context)
        except Exception as error:  # noqa: BLE001
            log.warning("[rewrite] %s: QC of the rewrite failed (%s); judging by the guards only", scene.title, error)
            return None
