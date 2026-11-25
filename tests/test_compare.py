"""Tests for the estimate-only tokenizer, the parallel-safe registry and /api/compare."""
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.schemas import COMPARE_MAX_TOKENS, MAX_COMPARE, TokenizerInfo
from src.bpe import BPETokenizer
from src.config import build_registry, load_config
from src.tokenizers import (
    CustomBPEAdapter,
    HeuristicAdapter,
    TokenizationNotSupported,
    TokenizerLoadError,
    TokenizerRegistry,
)

CONFIG = Path(__file__).parent.parent / "config" / "models.json"


# ---------- HeuristicAdapter ----------
def test_heuristic_counts_characters_not_bytes():
    h = HeuristicAdapter("est", 4)
    assert h.count("abcd") == 1 and h.count("abcde") == 2        # rounds up
    assert h.count("😊😊😊😊") == 1                               # 4 characters, 16 bytes
    assert h.count("") == 0


def test_heuristic_is_marked_as_an_estimate_without_tokens():
    h = HeuristicAdapter("est")
    assert h.exact is False and h.provides_tokens is False and "÷" in h.algorithm
    with pytest.raises(TokenizationNotSupported):
        h.encode("hello")


def test_heuristic_rejects_a_bad_ratio():
    with pytest.raises(ValueError):
        HeuristicAdapter("est", 0)


def test_config_builds_the_estimate_tokenizer():
    specs, _ = load_config(CONFIG)
    est = build_registry(specs).get("rule-of-thumb-4")
    assert est.exact is False and est.count("a" * 40) == 10


# ---------- registry: one lock per name ----------
def test_same_model_requested_by_many_threads_loads_once():
    calls = []

    def slow_factory():
        calls.append(1)
        time.sleep(0.05)
        return HeuristicAdapter("slow")

    reg = TokenizerRegistry()
    reg.register_factory("slow", slow_factory)
    threads = [threading.Thread(target=reg.get, args=("slow",)) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(calls) == 1


def test_different_models_load_in_parallel():
    reg = TokenizerRegistry()
    both_inside = threading.Barrier(2, timeout=2)     # only passes if BOTH factories run at once

    def factory(name):
        def build():
            both_inside.wait()
            return HeuristicAdapter(name)
        return build

    reg.register_factory("a", factory("a"))
    reg.register_factory("b", factory("b"))
    threads = [threading.Thread(target=reg.get, args=(n,)) for n in "ab"]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not both_inside.broken and len(reg._instances) == 2


# ---------- /api/compare ----------
@pytest.fixture
def client(my_bpe):
    registry = TokenizerRegistry()
    small = BPETokenizer().train("low lower lowest newest widest " * 20, vocab_size=270)
    registry.register(CustomBPEAdapter(my_bpe, name="bpe-big"))
    registry.register(CustomBPEAdapter(small, name="bpe-small"))
    registry.register(HeuristicAdapter("rule-of-thumb-4", 4))
    registry.register_factory("broken", lambda: (_ for _ in ()).throw(TokenizerLoadError("broken: offline")))
    infos = [TokenizerInfo(name="bpe-big", family="custom", algorithm="", exact=True),
             TokenizerInfo(name="bpe-small", family="custom", algorithm="", exact=True),
             TokenizerInfo(name="rule-of-thumb-4", family="estimate", algorithm="", exact=False, has_tokens=False),
             TokenizerInfo(name="broken", family="test", algorithm="", exact=True)]
    return TestClient(create_app(registry, infos, models={}))


def compare(client, text="low lowest 😊 مرحبا", names=None):
    body = {"text": text} | ({"tokenizers": names} if names is not None else {})
    return client.post("/api/compare", json=body)


def test_compare_returns_one_row_per_tokenizer_in_request_order(client):
    r = compare(client, names=["bpe-small", "bpe-big"])
    assert r.status_code == 200
    assert [x["name"] for x in r.json()["results"]] == ["bpe-small", "bpe-big"]


def test_compare_counts_match_the_single_tokenize_endpoint(client):
    rows = {x["name"]: x for x in compare(client, names=["bpe-small", "bpe-big"]).json()["results"]}
    for name, row in rows.items():
        single = client.post("/api/tokenize", json={"text": "low lowest 😊 مرحبا", "tokenizer": name}).json()
        assert row["count"] == single["count"] and len(row["tokens"]) == single["count"]


def test_a_failing_tokenizer_is_an_error_row_not_a_failed_request(client):
    r = compare(client, names=["bpe-big", "broken"])
    assert r.status_code == 200
    ok, bad = r.json()["results"]
    assert ok["error"] is None and ok["count"] > 0
    assert bad["count"] is None and "offline" in bad["error"] and bad["tokens"] == []


def test_estimate_has_a_count_but_no_tokens_and_is_not_exact(client):
    row = compare(client, text="a" * 40, names=["rule-of-thumb-4"]).json()["results"][0]
    assert (row["count"], row["exact"], row["has_tokens"], row["tokens"]) == (10, False, False, [])
    assert row["truncated"] is False


def test_long_text_returns_the_full_count_but_only_the_first_tokens(client):
    row = compare(client, text="low " * 2000, names=["bpe-big"]).json()["results"][0]
    assert row["count"] > COMPARE_MAX_TOKENS
    assert len(row["tokens"]) == COMPARE_MAX_TOKENS and row["truncated"] is True


def test_no_list_means_all_tokenizers(client):
    assert len(compare(client).json()["results"]) == 4


def test_duplicate_names_are_run_once(client):
    assert len(compare(client, names=["bpe-big", "bpe-big"]).json()["results"]) == 1


def test_unknown_tokenizer_is_404(client):
    assert compare(client, names=["nope"]).status_code == 404


def test_bad_lists_are_422(client):
    assert compare(client, names=[]).status_code == 422
    assert compare(client, names=[f"t{i}" for i in range(MAX_COMPARE + 1)]).status_code == 422


def test_reports_character_and_byte_counts(client):
    body = compare(client, text="a😊", names=["bpe-big"]).json()
    assert (body["chars"], body["bytes"]) == (2, 5)


def test_tokenize_endpoint_refuses_an_estimate_with_400(client):
    r = client.post("/api/tokenize", json={"text": "hi", "tokenizer": "rule-of-thumb-4"})
    assert r.status_code == 400 and "estimate" in r.json()["detail"]


def test_listing_tells_the_front_end_which_tokenizers_are_estimates(client):
    info = {t["name"]: t for t in client.get("/api/tokenizers").json()}
    assert info["rule-of-thumb-4"]["exact"] is False and info["rule-of-thumb-4"]["has_tokens"] is False
    assert info["bpe-big"]["exact"] is True and info["bpe-big"]["has_tokens"] is True


def test_the_default_app_lists_the_estimate_and_the_demo_app_builds_offline():
    from api.demo import app as demo
    from api.server import app as default
    assert "rule-of-thumb-4" in [t["name"] for t in TestClient(default).get("/api/tokenizers").json()]
    rows = TestClient(demo).post("/api/compare", json={"text": "low lowest newest"}).json()["results"]
    assert all(r["error"] is None for r in rows)
