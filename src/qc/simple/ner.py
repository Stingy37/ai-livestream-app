"""Step 1 of the simple QC engine: sentences and entities.
NERExtractor splits passages into sentences and asks the Lumen LLM which entities each sentence
mentions, then groups the sentences by entity so we know which ones to compare.
"""

import json
import logging
import os
import time

import nltk
from nltk.tokenize.punkt import PunktTokenizer

log = logging.getLogger(__name__)

BASE_URL = "https://lumen.computes.illinois.edu/v1"
MODEL = "deepseek-v4-flash"
KEY_NAME = "LUMEN_API_KEY"  # the key is read from this environment variable only
ABBREVIATIONS = ["no", "nos", "st", "mt", "gov", "dr"]  # a period after these does not end a sentence
RATE_LIMIT_RETRIES = 3  # how many times to wait and retry after an HTTP 429
DEFAULT_WAIT = 5  # seconds to wait if the server does not say how long
FILLER_WORDS = {"the", "a", "an", "of", "in", "on", "at", "to", "by", "and", "for", "about", "more", "than", "with", "from"}
TYPES = "PERSON, ORG, LOCATION, DATE, QUANTITY, EVENT"
SYSTEM_PROMPT = (
    f"You extract named entities from text. Allowed types: {TYPES}.\n"
    'Reply in exactly this JSON shape: {"entities": [{"text": "...", "type": "..."}]}\n'
    "Return ONLY valid JSON. Include only entities that appear in the text."
)


class QuotaError(Exception):
    """The Lumen coin budget is spent, so retrying is pointless."""


# Turn the model's reply into a list of entities, or None if the reply is not valid.
def parse_entities(reply):
    try:
        data = json.loads((reply or "").replace("```json", "").replace("```", ""))
        entities = data["entities"]
        for e in entities:
            if not (isinstance(e["text"], str) and isinstance(e["type"], str)):
                return None
        return entities
    except (ValueError, KeyError, TypeError):
        return None


# Decide what to do about an API error: return seconds to wait, or raise a clear message.
def handle_error(error, attempt):
    status = getattr(error, "status_code", None)
    if status == 429:
        if "insufficient_quota" in str(getattr(error, "body", "")):
            raise QuotaError("Lumen coin budget is spent (insufficient_quota). Stopping.")
        if attempt >= RATE_LIMIT_RETRIES:
            raise RuntimeError("Rate limited too many times. Try again later.")
        headers = getattr(getattr(error, "response", None), "headers", None) or {}
        return float(headers.get("retry-after", DEFAULT_WAIT))
    messages = {
        401: "401: the API key is missing or wrong. Check LUMEN_API_KEY.",
        403: "403: model access has not been acknowledged for this key in Lumen.",
        404: "404: model name not found.",
        503: "503: Lumen is temporarily unavailable. Try again later.",
    }
    raise RuntimeError(messages.get(status, f"API error: {type(error).__name__}"))


# The matching words of an entity: lowercase, numbers and punctuation removed, small filler words dropped.
# Example: "130 km/h" -> ["km/h"], "Typhoon Marisol" -> ["typhoon", "marisol"], "12,000" -> [].
def entity_words(text):
    letters_only = "".join(ch if ch.isalpha() or ch == "/" else " " for ch in text.lower())
    return [w for w in letters_only.split() if len(w) >= 2 and w not in FILLER_WORDS]


class NERExtractor:
    # saved_records: earlier output of run(), reused so we do not pay for the same sentence twice.
    # max_calls: the most LLM calls allowed in this run (None means no limit).
    def __init__(self, model=MODEL, saved_records=None, max_calls=None):
        self.model = model
        self.saved = {r["text"]: r["entities"] for r in saved_records or []}
        self.max_calls = max_calls
        self.calls = 0
        self.client = None
        self.splitter = None

    # Split a passage into sentences, keeping "Signal No. 3" together.
    def split_sentences(self, passage):
        if self.splitter is None:
            try:
                self.splitter = PunktTokenizer("english")
            except LookupError:
                nltk.download("punkt_tab", quiet=True)  # one-time download of the splitter data
                self.splitter = PunktTokenizer("english")
            self.splitter._params.abbrev_types.update(ABBREVIATIONS)
        return self.splitter.tokenize(passage)

    # Send one question to the LLM and return the text of its reply.
    # Used for entity extraction here, and by NLIChecker to ask "do these two sentences contradict?".
    def ask_llm(self, system_prompt, user_text):
        if self.client is None:
            from openai import OpenAI

            if not os.environ.get(KEY_NAME):
                raise RuntimeError(f"Set the {KEY_NAME} environment variable first.")
            self.client = OpenAI(base_url=BASE_URL, api_key=os.environ[KEY_NAME])
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}]
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                reply = self.client.chat.completions.create(model=self.model, messages=messages)
            except Exception as error:
                time.sleep(handle_error(error, attempt))
                continue
            log.info("Token usage: %s", reply.usage)
            return reply.choices[0].message.content  # never read the reasoning field

    # Entities of one sentence: a saved answer if we have one, else the LLM (one retry on bad JSON).
    def extract(self, sentence):
        if sentence in self.saved:
            return self.saved[sentence]
        if self.max_calls is not None and self.calls >= self.max_calls:
            return []
        self.calls += 1
        for _ in range(2):
            entities = parse_entities(self.ask_llm(SYSTEM_PROMPT, "Extract the entities from this passage:\n" + sentence))
            if entities is not None:
                self.saved[sentence] = entities  # remember it, so the same sentence is never paid for twice
                return entities
            log.warning("The reply was not valid JSON")
        return []

    # Split every passage and extract entities: one record per sentence.
    def run(self, passages):
        records = []
        for source_id, text in passages.items():
            for i, sentence in enumerate(self.split_sentences(text)):
                entities = self.extract(sentence)
                records.append({"source_id": source_id, "sentence_index": i, "text": sentence, "entities": entities})
        return records

    # One dictionary: entity word -> the sentences whose entities contain that word.
    # Using words instead of the exact text means "Typhoon Marisol" meets "Marisol",
    # "October 14, 2026" meets "October 13, 2026", and "130 km/h" meets "150 km/h".
    def group_by_entity(self, records):
        groups = {}
        for record in records:
            for word in sorted({w for e in record["entities"] for w in entity_words(e["text"])}):
                groups.setdefault(word, []).append(record)
        return groups
