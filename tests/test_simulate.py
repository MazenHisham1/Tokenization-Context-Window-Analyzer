"""/api/simulate with tiny local tokenizers (offline)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import MAX_MESSAGES, TokenizerInfo
from src.bpe import BPETokenizer
from src.config import ModelSpec
from src.tokenizers import CustomBPEAdapter, HeuristicAdapter, TokenizerRegistry

TEXT = "the quick brown fox jumps over the lazy dog. " * 3


@pytest.fixture(scope="module")
def client():
    reg = TokenizerRegistry()
    reg.register(CustomBPEAdapter(BPETokenizer().train(TEXT * 10, vocab_size=300), name="bpe"))
    reg.register(HeuristicAdapter("est", 4))
    infos = [
        TokenizerInfo(name="bpe", family="custom", algorithm="bpe", exact=True),
        TokenizerInfo(name="est", family="estimate", algorithm="chars/4", exact=False, has_tokens=False),
    ]

    def mk(model_id, tokenizer):
        return ModelSpec(model_id, model_id, tokenizer, 100, "test", date(2026, 1, 1))

    models = {"m": mk("m", "bpe"), "e": mk("e", "est"), "x": mk("x", "missing")}
    return TestClient(create_app(reg, infos, models))


def body(**kw):
    base = {"model": "m", "reserve_output": 10, "per_message_overhead": 2,
            "messages": [{"role": "system", "text": "Be brief."},
                         {"role": "user", "text": TEXT * 2},
                         {"role": "assistant", "text": TEXT * 2},
                         {"role": "user", "text": "ok?"}]}
    return {**base, **kw}


def test_everything_fits_in_a_big_window(client):
    r = client.post("/api/simulate", json=body(context_window=100000)).json()
    assert r["fits"] and r["overflow_tokens"] == 0 and {m["status"] for m in r["messages"]} == {"kept"}
    assert r["budget"] == 100000 - 10 and r["used_tokens"] == r["total_tokens"]
    assert r["total_tokens"] == sum(m["tokens"] + 2 for m in r["messages"])


def test_drop_oldest_drops_old_messages_and_fits(client):
    r = client.post("/api/simulate", json=body(strategy="drop_oldest")).json()
    assert r["total_tokens"] > r["budget"] and r["overflow_tokens"] > 0
    st = [m["status"] for m in r["messages"]]
    assert st[0] == "kept" and st[-1] == "kept" and "dropped" in st and r["fits"] and r["used_tokens"] <= r["budget"]


def test_error_strategy_reports_overflow_without_changing_anything(client):
    r = client.post("/api/simulate", json=body(strategy="error")).json()
    assert not r["fits"] and {m["status"] for m in r["messages"]} == {"kept"}


@pytest.mark.parametrize("strategy,side", [("truncate_start", "end"), ("truncate_end", "start")])
def test_truncation_returns_the_character_range_that_survives(client, strategy, side):
    r = client.post("/api/simulate", json=body(strategy=strategy, context_window=100, reserve_output=0)).json()
    part = [m for m in r["messages"] if m["status"] == "partial"]
    assert len(part) == 1 and r["fits"]
    a, b = part[0]["kept_chars"]
    assert 0 <= a < b <= part[0]["chars"]
    assert (a == 0) if side == "start" else (b == part[0]["chars"])
    # the surviving text must really be that many tokens
    tok_count = client.post("/api/tokenize", json={"text": (TEXT * 2)[a:b], "tokenizer": "bpe"}).json()["count"]
    assert abs(tok_count - part[0]["kept_tokens"]) <= 2    # boundaries of a cut can merge differently


def test_window_override_and_reserve(client):
    r = client.post("/api/simulate", json=body(context_window=500, reserve_output=100)).json()
    assert r["context_window"] == 500 and r["budget"] == 400


def test_system_too_big(client):
    msgs = [{"role": "system", "text": TEXT}, {"role": "user", "text": "hi"}]
    r = client.post("/api/simulate", json=body(messages=msgs, context_window=20, reserve_output=0)).json()
    assert r["cannot_fit"] and not r["fits"]


def test_errors(client):
    assert client.post("/api/simulate", json=body(model="nope")).status_code == 404
    assert client.post("/api/simulate", json=body(model="x")).status_code == 503
    assert client.post("/api/simulate", json=body(reserve_output=100)).status_code == 400   # reserve >= window
    assert client.post("/api/simulate", json=body(strategy="magic")).status_code == 422
    assert client.post("/api/simulate", json=body(messages=[])).status_code == 422
    assert client.post("/api/simulate", json=body(messages=[{"role": "robot", "text": "x"}])).status_code == 422
    many = [{"role": "user", "text": "x"}] * (MAX_MESSAGES + 1)
    assert client.post("/api/simulate", json=body(messages=many)).status_code == 422


def test_estimate_tokenizer_counts_but_cannot_truncate(client):
    assert client.post("/api/simulate", json=body(model="e", strategy="drop_oldest")).status_code == 200
    r = client.post("/api/simulate", json=body(model="e", strategy="truncate_end"))
    assert r.status_code == 400 and "estimate" in r.json()["detail"]


def test_validation_errors_do_not_echo_the_text(client):
    secret = "SECRET-TEXT"
    r = client.post("/api/simulate", json=body(messages=[{"role": "robot", "text": secret}]))
    assert r.status_code == 422 and secret not in r.text
