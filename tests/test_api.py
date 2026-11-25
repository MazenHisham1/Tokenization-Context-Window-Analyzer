"""API tests. They use a fake registry, so they need no internet and no model downloads."""
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import MAX_TEXT_CHARS, TokenizerInfo
from src.config import load_config
from src.tokenizers import CustomBPEAdapter, TokenizerLoadError, TokenizerRegistry


@pytest.fixture
def client(my_bpe):
    from pathlib import Path
    _, models = load_config(Path(__file__).parent.parent / "config" / "models.json")
    registry = TokenizerRegistry()
    registry.register(CustomBPEAdapter(my_bpe))
    registry.register_factory("broken", lambda: (_ for _ in ()).throw(
        TokenizerLoadError("broken: cannot load (offline)")))
    infos = [TokenizerInfo(name="my-bpe", family="custom", algorithm="byte-level BPE", exact=True),
             TokenizerInfo(name="broken", family="test", algorithm="", exact=True)]
    return TestClient(create_app(registry, infos, models))


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_tokenizers_does_not_load_anything(client):
    r = client.get("/api/tokenizers")      # 'broken' would raise if listing loaded it
    assert r.status_code == 200 and [t["name"] for t in r.json()] == ["my-bpe", "broken"]


def test_list_models_has_sources(client):
    models = client.get("/api/models").json()
    assert models and all(m["source_url"].startswith("http") and m["context_window"] > 0 for m in models)


def test_tokenize_ok(client):
    r = client.post("/api/tokenize", json={"text": "low lowest 😊", "tokenizer": "my-bpe"})
    body = r.json()
    assert r.status_code == 200
    assert body["count"] == len(body["tokens"]) > 0
    assert body["chars"] == 12 and body["bytes"] == len("low lowest 😊".encode())
    assert body["tokens"][0]["start"] == 0 and body["tokens"][-1]["end"] == body["bytes"]


def test_tokenize_empty_text_is_zero_tokens(client):
    body = client.post("/api/tokenize", json={"text": "", "tokenizer": "my-bpe"}).json()
    assert body["count"] == 0 and body["tokens"] == [] and body["chars_per_token"] is None


def test_unknown_tokenizer_is_404(client):
    assert client.post("/api/tokenize", json={"text": "x", "tokenizer": "nope"}).status_code == 404


def test_load_failure_is_503_with_message(client):
    r = client.post("/api/tokenize", json={"text": "x", "tokenizer": "broken"})
    assert r.status_code == 503 and "offline" in r.json()["detail"]


def test_text_over_the_limit_is_422(client):
    r = client.post("/api/tokenize", json={"text": "a" * (MAX_TEXT_CHARS + 1), "tokenizer": "my-bpe"})
    assert r.status_code == 422
    assert "aaaa" not in r.text            # the 422 reply must not echo the user's text back


def test_missing_fields_are_422(client):
    assert client.post("/api/tokenize", json={"text": "x"}).status_code == 422


def test_lone_surrogate_is_422_not_500(client):
    r = client.post("/api/tokenize", content='{"text": "\\ud800", "tokenizer": "my-bpe"}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "text"]


def test_default_app_builds_offline():
    from api.server import app  # reads the real config, trains my-bpe, loads no model
    names = [t["name"] for t in TestClient(app).get("/api/tokenizers").json()]
    assert "my-bpe" in names and "o200k_base" in names


def test_tokenize_caps_the_returned_tokens_but_reports_the_full_count(client):
    from api.schemas import TOKENIZE_MAX_TOKENS
    text = "zqxj kwvp " * 600                         # rare letters: almost one token per character
    body = client.post("/api/tokenize", json={"text": text, "tokenizer": "my-bpe"}).json()
    assert body["count"] > TOKENIZE_MAX_TOKENS
    assert len(body["tokens"]) == TOKENIZE_MAX_TOKENS and body["truncated"] is True


def test_tokenize_small_text_is_not_truncated(client):
    body = client.post("/api/tokenize", json={"text": "hello", "tokenizer": "my-bpe"}).json()
    assert body["truncated"] is False and body["count"] == len(body["tokens"])
