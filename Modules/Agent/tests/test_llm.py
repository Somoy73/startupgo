"""The openai-compatible client (NVIDIA): JSON-schema calls, retries, usage, image transcription; and the [llm] settings."""

import base64
import io
import json
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

import pytest

from startup_agent import llm as llm_module
from startup_agent.cache import JsonCache
from startup_agent.config import AgentSettings
from startup_agent.errors import AgentError
from startup_agent.factory import build_llm
from startup_agent.llm import CachedLLM, OpenAICompatibleClient, UsageStats

SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}}


class FakeHTTP:
    """Answers queued responses: a dict becomes a 200 JSON body, an int an HTTP error with that status."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((json.loads(request.data), dict(request.headers), timeout))
        response = self.responses.pop(0)
        if isinstance(response, int):
            headers = Message()
            if response == 429:
                headers["Retry-After"] = "2"
            raise HTTPError(request.full_url, response, "err", headers, io.BytesIO(b'{"detail":"busy"}'))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self.body).encode()


def answer(content, usage=None):
    http = FakeHTTP()
    http.body = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}], **({"usage": usage} if usage else {})}
    return http


@pytest.fixture
def client(monkeypatch):
    def make(*responses, **kwargs):
        http = FakeHTTP(*responses)
        http.body = {"choices": [{"message": {"content": kwargs.pop("content", '{"summary": "ok"}')}, "finish_reason": "stop"}],
                     "usage": {"prompt_tokens": 100, "completion_tokens": 20, "completion_tokens_details": {"reasoning_tokens": 5}}}
        monkeypatch.setattr(llm_module, "urlopen", http)
        sleeps = []
        stats = UsageStats()
        c = OpenAICompatibleClient(endpoint="https://api.example/v1/", api_key="k", model="m", max_tokens=512,
                                   extra_body={"chat_template_kwargs": {"enable_thinking": False}}, stats=stats, sleep=sleeps.append, **kwargs)
        return c, http, sleeps, stats
    return make


def test_json_call_sends_the_schema_and_provider_fields_and_records_usage(client):
    c, http, _, stats = client({})
    assert c.complete_json(system="s", user="u", schema=SCHEMA) == {"summary": "ok"}
    body, headers, timeout = http.requests[0]
    assert body["response_format"] == {"type": "json_schema", "json_schema": {"name": "result", "schema": SCHEMA, "strict": True}}
    assert (body["model"], body["max_tokens"], body["chat_template_kwargs"]) == ("m", 512, {"enable_thinking": False})
    assert body["messages"] == [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert headers["Authorization"] == "Bearer k" and timeout == 120
    assert (stats.llm_requests, stats.prompt_tokens, stats.output_tokens, stats.thinking_tokens) == (1, 100, 20, 5)


def test_rate_limits_and_busy_servers_are_retried_then_given_up(client):
    c, http, sleeps, stats = client(429, 502, {})
    assert c.complete_json(system="s", user="u", schema=SCHEMA) == {"summary": "ok"}
    assert sleeps == [2.0, 20] and stats.retries == 2 and stats.waited_seconds == 22 and len(http.requests) == 3

    c, http, sleeps, _ = client(503, 503, 503, 503)
    with pytest.raises(AgentError, match=r"failed \(503\): .*busy"):
        c.complete_json(system="s", user="u", schema=SCHEMA)
    assert len(http.requests) == 4 and sleeps == [5, 20, 60]

    c, http, sleeps, _ = client(400)
    with pytest.raises(AgentError, match=r"failed \(400\)"):
        c.complete_json(system="s", user="u", schema=SCHEMA)
    assert sleeps == []


def test_transcribe_sends_the_image_inline_and_only_for_multimodal_models(client):
    c, http, _, _ = client({}, content="Net revenue EUR 4.2 million", multimodal=True)
    assert c.transcribe("Transcribe", data=b"\x89PNG", mime="image/png") == "Net revenue EUR 4.2 million"
    body = http.requests[0][0]
    assert "response_format" not in body
    assert body["messages"] == [{"role": "user", "content": [
        {"type": "text", "text": "Transcribe"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(b"\x89PNG").decode()}},
    ]}]

    c, http, _, _ = client({}, multimodal=False)
    with pytest.raises(AgentError, match="not set up to read images"):
        c.transcribe("Transcribe", data=b"x", mime="image/png")
    c, http, _, _ = client({}, multimodal=True)
    with pytest.raises(AgentError, match="takes images, not application/pdf"):
        c.transcribe("Transcribe", data=b"x", mime="application/pdf")
    assert http.requests == []


def test_an_answer_cut_off_at_max_tokens_is_its_own_error(monkeypatch):
    from startup_agent.llm import AnswerCutOff

    http = FakeHTTP({})
    http.body = {"choices": [{"message": {"content": '{"summary": "Blue Ca'}, "finish_reason": "length"}]}
    monkeypatch.setattr(llm_module, "urlopen", http)
    client = OpenAICompatibleClient(endpoint="https://api.example/v1", api_key="k", model="m")
    with pytest.raises(AnswerCutOff, match="max_tokens"):
        client.complete_json(system="s", user="u", schema=SCHEMA)


def test_a_timed_out_call_is_sent_once_more_then_reported(client, monkeypatch):
    from startup_agent.llm import LLMTimeout

    c, http, sleeps, stats = client({})
    calls = []

    def slow_then_fast(request, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise TimeoutError("The read operation timed out")
        return http(request, timeout)

    monkeypatch.setattr(llm_module, "urlopen", slow_then_fast)
    assert c.complete_json(system="s", user="u", schema=SCHEMA) == {"summary": "ok"} and stats.retries == 1

    def always_slow(request, timeout):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(llm_module, "urlopen", always_slow)
    with pytest.raises(LLMTimeout, match="didn't answer within 120 s, twice"):
        c.complete_json(system="s", user="u", schema=SCHEMA)


def test_an_empty_answer_is_an_error(client):
    c, _, _, _ = client({}, content="")
    with pytest.raises(AgentError, match="no content"):
        c.complete_json(system="s", user="u", schema=SCHEMA)


def test_cached_llm_caches_transcripts_by_file_and_prompt(tmp_path):
    class Inner:
        model = "m"
        calls = 0

        def complete_json(self, **kwargs):
            raise AssertionError

        def transcribe(self, prompt, *, data, mime):
            self.calls += 1
            return f"text of {len(data)} bytes"

    stats = UsageStats()
    cached = CachedLLM(Inner(), JsonCache(tmp_path), stats=stats)
    assert cached.transcribe("p", data=b"abc", mime="image/png") == "text of 3 bytes"
    assert cached.transcribe("p", data=b"abc", mime="image/png") == "text of 3 bytes"
    assert cached.transcribe("p", data=b"abcd", mime="image/png") == "text of 4 bytes"
    assert (cached.inner.calls, stats.llm_cached) == (2, 1)


def test_llm_settings_for_openai_compatible_providers(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    config.write_text(
        '[llm]\nprovider = "openai-compatible"\nmodel = "nvidia/x"\napi_key_env = "X_KEY"\nendpoint = "https://api.example/v1"\n'
        'requests_per_minute = 30\nreasoning = false\nmultimodal = true\nmax_tokens = 4096\ntimeout = 90\n',
        encoding="utf-8",
    )
    settings = AgentSettings.load(config)
    assert (settings.llm.reasoning, settings.llm.multimodal, settings.llm.max_tokens, settings.llm.timeout) == (False, True, 4096, 90.0)
    assert settings.llm.reads_images is True

    monkeypatch.setenv("X_KEY", "secret")
    client = build_llm(settings, None, UsageStats())._real()
    assert (client.multimodal, client.max_tokens, client.timeout) == (True, 4096, 90.0)
    assert client.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}
    assert client._limiter is not None and client._limiter.interval == 2.0

    plain = tmp_path / "plain.toml"
    plain.write_text('[llm]\nprovider = "openai-compatible"\napi_key_env = "X_KEY"\nendpoint = "https://api.example/v1"\n'
                     'requests_per_minute = 0\n', encoding="utf-8")
    settings = AgentSettings.load(plain)
    assert (settings.llm.reasoning, settings.llm.multimodal, settings.llm.max_tokens, settings.llm.reads_images) == (None, False, None, False)
    client = build_llm(settings, None)._real()
    assert client.extra_body == {} and client._limiter is None  # no Nemotron field for other endpoints


PROFILES = """
[llm]
default = "nvidia"
temperature = 0.0
requests_per_minute = 20

[llm.nvidia]
provider = "openai-compatible"
model = "nvidia/x"
api_key_env = "X_KEY"
endpoint = "https://integrate.api.nvidia.com/v1"
reasoning = false
multimodal = true

[llm.gemini]
provider = "gemini"
model = "gemini-y"
api_key_env = "Y_KEY"
requests_per_minute = 10
thinking = "minimal"

[search]
provider = "%s"
"""


def test_model_profiles_share_llm_keys_and_one_is_the_default(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(PROFILES % "none", encoding="utf-8")
    settings = AgentSettings.load(config)

    assert (settings.llm.name, settings.llm.model) == ("nvidia", "nvidia/x")
    assert {name: (p.provider, p.requests_per_minute) for name, p in settings.llms.items()} == {
        "nvidia": ("openai-compatible", 20.0), "gemini": ("gemini", 10.0)}  # shared keys, overridden per profile
    gemini = settings.with_llm("gemini")
    assert (gemini.llm.name, gemini.llm.model, gemini.llm.thinking) == ("gemini", "gemini-y", "minimal")
    assert settings.with_llm(None) is settings and settings.with_llm("nvidia") is settings
    assert gemini.with_llm("nvidia").llm == settings.llm
    with pytest.raises(AgentError, match="unknown model 'gpt': config.toml has nvidia, gemini"):
        settings.with_llm("gpt")

    config.write_text((PROFILES % "none").replace('default = "nvidia"', 'default = "claude"'), encoding="utf-8")
    with pytest.raises(AgentError, match="default = 'claude' is not a profile"):
        AgentSettings.load(config)


def test_a_flat_llm_table_is_the_only_profile_named_after_its_provider(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[llm]\nprovider = "gemini"\nmodel = "gemini-y"\n', encoding="utf-8")
    settings = AgentSettings.load(config)
    assert (settings.llm.name, list(settings.llms)) == ("gemini", ["gemini"])
    assert settings.llm.reads_images is True


def test_gemini_search_runs_next_to_the_nvidia_model_with_the_gemini_profile(tmp_path):
    from startup_agent.factory import build_search
    from startup_agent.search import GeminiGoogleSearch

    config = tmp_path / "config.toml"
    config.write_text(PROFILES % "gemini", encoding="utf-8")
    settings = AgentSettings.load(config)
    searcher = build_search(settings, None, user_agent="UA")
    assert isinstance(searcher, GeminiGoogleSearch) and searcher.model == "gemini-y"
    assert searcher._session._limiter.interval == 6.0  # the Gemini profile's 10/min, not NVIDIA's

    alone = tmp_path / "alone.toml"
    alone.write_text('[llm]\nprovider = "openai-compatible"\nendpoint = "https://x/v1"\n[search]\nprovider = "gemini"\n', encoding="utf-8")
    with pytest.raises(AgentError, match=r"needs a Gemini model profile"):
        build_search(AgentSettings.load(alone), None, user_agent="UA")


def test_default_config_has_both_models_with_nvidia_first():
    settings = AgentSettings.load(Path(__file__).resolve().parents[1] / "config.toml")
    assert settings.llm.name == "nvidia" and settings.llm.provider == "openai-compatible"
    assert settings.llm.reasoning is False and settings.llm.multimodal is True
    assert settings.llms["gemini"].provider == "gemini" and settings.gemini_llm().name == "gemini"
