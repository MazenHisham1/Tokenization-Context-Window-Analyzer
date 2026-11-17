from datetime import date
from pathlib import Path

import pytest

from src.config import ConfigError, build_registry, load_config, stale_models
from src.tokenizers import (CustomBPEAdapter, Token, Tokenizer, TokenizerRegistry,
                            compare_counts, char_spans)

CONFIG = Path(__file__).parent.parent / "config" / "models.json"


class Dummy(Tokenizer):
    def encode(self, text):
        return [Token(0, c, i, i + 1) for i, c in enumerate(text)]


def test_token_is_immutable_and_validates_span():
    t = Token(1, "a", 0, 1)
    with pytest.raises(Exception):
        t.id = 2
    with pytest.raises(ValueError):
        Token(1, "a", 5, 2)


def test_tokenizer_is_abstract_and_needs_name():
    with pytest.raises(TypeError):
        Tokenizer("x")
    with pytest.raises(ValueError):
        Dummy("")


def test_char_spans_multibyte():
    toks = Dummy("x").encode("x")
    assert char_spans("é", [Token(1, "é", 0, 2)]) == [(0, 1)]
    assert char_spans("x", toks) == [(0, 1)]


def test_registry_basics_and_errors():
    r = TokenizerRegistry()
    d = Dummy("d")
    r.register(d)
    assert r.get("d") is d and "d" in r and len(r) == 1 and r.names() == ["d"]
    with pytest.raises(ValueError):
        r.register(Dummy("d"))
    r.register(Dummy("d"), replace=True)
    with pytest.raises(KeyError, match="available"):
        r.get("nope")


def test_registry_factories_are_lazy_and_cached():
    calls = []
    r = TokenizerRegistry()
    r.register_factory("lazy", lambda: calls.append(1) or Dummy("lazy"))
    assert calls == []
    r.get("lazy"); r.get("lazy")
    assert calls == [1]


def test_compare_counts_survives_a_failing_tokenizer(my_bpe):
    r = TokenizerRegistry()
    r.register(CustomBPEAdapter(my_bpe))
    r.register_factory("broken", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    rows = {row.name: row for row in compare_counts(r, "low lowest")}
    assert rows["my-bpe"].tokens > 0 and rows["my-bpe"].error is None
    assert rows["broken"].tokens is None and "offline" in rows["broken"].error


def test_real_config_loads_and_every_model_has_a_source():
    tokenizers, models = load_config(CONFIG)
    assert models and all(m.source_url.startswith("http") for m in models.values())
    assert set(build_registry(tokenizers).names()) == set(tokenizers)   # lazy: no downloads


def test_stale_detection():
    _, models = load_config(CONFIG)
    assert stale_models(models, date(2026, 11, 20)) == []
    assert set(stale_models(models, date(2027, 6, 1))) == set(models)


@pytest.mark.parametrize("patch,msg", [
    ({"context_window": -5}, "positive integer"),
    ({"context_window": "128k"}, "positive integer"),
    ({"tokenizer": "ghost"}, "unknown tokenizer"),
    ({"last_verified": "yesterday"}, "YYYY-MM-DD"),
    ({"source_url": "n/a"}, "URL"),
])
def test_bad_config_is_rejected(tmp_path, patch, msg):
    import json
    model = {"id": "m", "display_name": "M", "tokenizer": "t", "context_window": 1000,
             "source_url": "https://example.com", "last_verified": "2026-01-01"}
    model.update(patch)
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"tokenizers": {"t": {"adapter": "tiktoken", "encoding": "x"}},
                             "models": [model]}))
    with pytest.raises(ConfigError, match=msg):
        load_config(p)
