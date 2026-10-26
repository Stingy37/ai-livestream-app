"""Offline tests for the shared Lumen client: no API calls, no key needed."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from models import llm_api
from models.llm_api import LumenClient, QuotaError, handle_error, parse_json


def api_error(status, body=None, headers=None):
    response = httpx.Response(status, headers=headers or {}, request=httpx.Request("POST", "http://lumen"))
    return openai.APIStatusError("boom", response=response, body=body)


def fake_reply(text, prompt=10, completion=5):
    usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)
    return SimpleNamespace(usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def client_with(outcomes):
    """A LumenClient whose API returns (or raises) each outcome in turn."""
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    lumen = LumenClient()
    lumen.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return lumen, calls


def test_quota_error_stops_without_retrying():
    lumen, calls = client_with([api_error(429, body={"code": "insufficient_quota"})])
    with pytest.raises(QuotaError):
        lumen.ask("sys", "hi")
    assert len(calls) == 1


def test_rate_limit_waits_then_retries(monkeypatch):
    waits = []
    monkeypatch.setattr(llm_api.time, "sleep", waits.append)
    lumen, calls = client_with([api_error(429, headers={"retry-after": "2"}), fake_reply("ok")])
    assert lumen.ask("sys", "hi") == "ok"
    assert waits == [2.0] and len(calls) == 2


@pytest.mark.parametrize("status, text", [(401, "LUMEN_API_KEY"), (403, "acknowledged"), (503, "unavailable")])
def test_http_errors_have_clear_messages(status, text):
    with pytest.raises(RuntimeError, match=text):
        handle_error(api_error(status), 0)


def test_token_usage_is_counted():
    lumen, _ = client_with([fake_reply("a", 100, 20), fake_reply("b", 50, 10)])
    lumen.ask("s", "u")
    lumen.ask("s", "u")
    assert (lumen.calls, lumen.prompt_tokens, lumen.completion_tokens) == (2, 150, 30)
    assert "150 prompt" in lumen.usage_summary()


def test_ask_json_retries_once_on_bad_json():
    lumen, calls = client_with([fake_reply("nope"), fake_reply('```json\n{"x": 1}\n```')])
    assert lumen.ask_json("s", "u") == {"x": 1}
    assert len(calls) == 2


def test_parse_json_rejects_non_objects():
    assert parse_json("[1, 2]") is None and parse_json(None) is None


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("LUMEN_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match="LUMEN_API_KEY"):
        LumenClient().ask("s", "u")


def test_client_has_a_timeout_and_no_sdk_retries(monkeypatch):
    seen = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setenv("LUMEN_API_KEY", "test-key")
    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    LumenClient()._get_client()
    assert seen["timeout"] == llm_api.TIMEOUT <= 120 and seen["max_retries"] == 0
