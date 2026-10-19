"""Step 2 of the simple QC engine: do two sentences contradict each other?
NLIChecker first asks a free local Hugging Face model; if that model is almost certain the pair contradicts, the
pair is flagged right away. Otherwise the Lumen LLM decides, because it understands numbers, dates and meaning.
"""

import hashlib
import json

import torch

MODEL = "cross-encoder/nli-roberta-base"
SURE_THRESHOLD = 0.99  # the local model alone flags a pair only when P(contradiction) is at least this
MAX_TOKENS = 256  # longer input is cut off instead of crashing
NUM_THREADS = 4  # more threads made scoring about 45 times slower on this machine
RULES = (
    "Two statements CONTRADICT when both cannot be true at the same time: they give different values for the same "
    "thing (a number, date, time, place, name, count or level), or one says something is true or happened and the "
    "other says it is not or did not, or one clearly implies the opposite of the other.\n"
    "They do NOT contradict when they talk about different things (two different quantities can share a unit), "
    "when one only adds detail, when the values are roughly the same, or when they are only worded differently.\n"
)
# For one pair of sentences.
JUDGE_PROMPT = (
    "You are a careful fact checker. Decide whether two statements contradict each other.\n" + RULES +
    'Return ONLY valid JSON: {"contradiction": true or false, "reason": "one short sentence"}'
)
# For two short documents read together (their sentences are numbered from 1).
PASSAGE_PROMPT = (
    "You are a careful fact checker. You get Passage A and Passage B with numbered sentences.\n" + RULES +
    "Be thorough, like an editor marking every inconsistency. Also report statements a normal reader would see as "
    "conflicting even if some unusual explanation could make both true: for example 'a town' versus 'the village', "
    "'the last one was A' versus 'the last one was B', 'only' or 'exclusively' versus a counterexample, or a total "
    "that does not match its parts. Use general knowledge when needed, such as the dates of historical periods or "
    "adding up numbers.\n"
    "Find every pair of sentences, one from A and one from B, that contradict each other. If the two passages are "
    "the same text, look for contradictions inside it; a single sentence can contradict itself, then use its number "
    "for both a and b.\n"
    'Return ONLY valid JSON: {"contradictions": [{"a": number, "b": number, "reason": "one short sentence"}]} '
    "using the sentence numbers, or an empty list if nothing contradicts."
)
# A second, differently worded question for short documents. Asking twice catches more contradictions.
SECOND_PASSAGE_PROMPT = (
    "You review text for factual consistency before it is published. You get Passage A and Passage B with "
    "numbered sentences, usually about the same subject.\n"
    "For each sentence in A, ask: does anything in B make it false, doubtful or impossible? Look closely at numbers, "
    "dates, names, places, yes or no facts, and words like only, first, last, all and never. Use general knowledge "
    "when needed. If the two passages are the same text, check whether any sentence conflicts with another sentence "
    "or with itself (then use the same number twice).\n"
    "Ignore differences in wording, extra detail, and statements about different things.\n"
    'Return ONLY valid JSON: {"contradictions": [{"a": number, "b": number, "reason": "one short sentence"}]} '
    "using the sentence numbers, or an empty list."
)


# A short fingerprint of a question's wording and the model that answers it, like a Java hashCode() of the text.
# It goes at the start of every saved answer's key: change one word of a prompt, or switch models, and the
# fingerprint changes, so old answers are not reused by mistake.
def fingerprint(prompt, judge_model):
    return hashlib.sha1((judge_model + "\n" + prompt).encode()).hexdigest()[:8]


# Turn the LLM's reply into (True or False, reason), or None if the reply is not valid.
def parse_verdict(reply):
    try:
        data = json.loads((reply or "").replace("```json", "").replace("```", ""))
        if isinstance(data["contradiction"], bool):
            return data["contradiction"], str(data.get("reason", ""))
    except (ValueError, KeyError, TypeError):
        pass
    return None


# Turn a passage reply into a list of {"a", "b", "reason"} (sentence positions counted from 0), or None if not valid.
def parse_contradictions(reply, size_a, size_b):
    try:
        found = []
        for item in json.loads((reply or "").replace("```json", "").replace("```", ""))["contradictions"]:
            a, b = item["a"], item["b"]
            if not (isinstance(a, int) and isinstance(b, int) and 1 <= a <= size_a and 1 <= b <= size_b):
                return None  # a sentence number that does not exist
            found.append({"a": a - 1, "b": b - 1, "reason": str(item.get("reason", ""))})
        return found
    except (ValueError, KeyError, TypeError):
        return None


class NLIChecker:
    # ask_llm: a function (system_prompt, user_text) -> reply text, usually NERExtractor.ask_llm.
    #          None means "local model only".
    # judge_model: name of the LLM behind ask_llm, used in the saved answers' fingerprint.
    # saved_judgments: earlier LLM answers, reused so we never pay twice for the same question.
    def __init__(self, model_name=MODEL, sure_threshold=SURE_THRESHOLD, ask_llm=None, saved_judgments=None,
                 judge_model="deepseek-v4-flash"):
        self.model_name = model_name
        self.judge_model = judge_model
        self.sure_threshold = sure_threshold
        self.ask_llm = ask_llm
        self.judgments = dict(saved_judgments or {})
        self.llm_calls = 0
        self.tokenizer = None
        self.model = None

    # Load the model the first time it is needed, and only once.
    def load(self):
        if self.model is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            torch.set_num_threads(NUM_THREADS)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.eval()

    # Probabilities for one direction (premise first, hypothesis second).
    # The label names come from the model's own config, so we never guess which index is which.
    def probabilities(self, premise, hypothesis):
        self.load()
        inputs = self.tokenizer(premise, hypothesis, return_tensors="pt", truncation=True, max_length=MAX_TOKENS)
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0].tolist()
        names = [self.model.config.id2label[i].lower() for i in range(len(probs))]
        return dict(zip(names, probs))

    # Ask the LLM whether two sentences contradict. A saved answer is reused; one retry on a bad reply.
    def ask_judge(self, sentence_a, sentence_b):
        # same key whichever order the pair comes in, starting with the prompt's fingerprint
        key = fingerprint(JUDGE_PROMPT, self.judge_model) + " " + " || ".join(sorted([sentence_a, sentence_b]))
        if key not in self.judgments:
            self.llm_calls += 1
            verdict = None
            for _ in range(2):
                verdict = parse_verdict(self.ask_llm(JUDGE_PROMPT, f"Statement A: {sentence_a}\nStatement B: {sentence_b}"))
                if verdict is not None:
                    break
            if verdict is None:
                verdict = (False, "no valid answer from the LLM")
            self.judgments[key] = {"contradiction": verdict[0], "reason": verdict[1]}
        return self.judgments[key]

    # Short documents: ask two differently worded questions and keep every contradiction either one found.
    # Returns a list of {"a": position in A, "b": position in B, "reason"}; an empty list means none.
    def check_passages(self, sentences_a, sentences_b):
        found = list(self.ask_passages(PASSAGE_PROMPT, sentences_a, sentences_b))
        for item in self.ask_passages(SECOND_PASSAGE_PROMPT, sentences_a, sentences_b):
            if (item["a"], item["b"]) not in [(f["a"], f["b"]) for f in found]:
                found.append(item)  # only add pairs the first question did not already report
        return found

    # One LLM call reads both whole passages with one prompt. The fingerprint keeps each prompt's answers apart.
    def ask_passages(self, prompt, sentences_a, sentences_b):
        key = fingerprint(prompt, self.judge_model) + " A:\n" + "\n".join(sentences_a) + "\nB:\n" + "\n".join(sentences_b)
        if key not in self.judgments:
            self.llm_calls += 1
            numbered_a = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences_a, start=1))
            numbered_b = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences_b, start=1))
            question = f"Passage A:\n{numbered_a}\n\nPassage B:\n{numbered_b}"
            if sentences_a == sentences_b:  # the same text twice: say so, so the LLM checks it against itself
                question = "Passage A and Passage B are the same text. Check it for contradictions inside itself.\n\n" + question
            found = None
            for _ in range(2):
                reply = self.ask_llm(prompt, question)
                found = parse_contradictions(reply, len(sentences_a), len(sentences_b))
                if found is not None:
                    break
            self.judgments[key] = found or []
        return self.judgments[key]

    # Score the pair in both orders (NLI depends on order) and keep the higher contradiction.
    # Near-certain contradictions are flagged by the local model; every other pair goes to the LLM.
    def check(self, sentence_a, sentence_b):
        forward = self.probabilities(sentence_a, sentence_b)
        backward = self.probabilities(sentence_b, sentence_a)
        best = forward if forward["contradiction"] >= backward["contradiction"] else backward
        if best["contradiction"] >= self.sure_threshold or self.ask_llm is None:
            flagged = best["contradiction"] >= self.sure_threshold
            return {"label": max(best, key=best.get), "probabilities": best, "flagged": flagged, "source": "nli", "reason": ""}
        verdict = self.ask_judge(sentence_a, sentence_b)
        label = "contradiction" if verdict["contradiction"] else "no contradiction"
        return {"label": label, "probabilities": best, "flagged": verdict["contradiction"], "source": "llm",
                "reason": verdict["reason"]}
