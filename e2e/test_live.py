"""Smoke test of a running site (the deployed Space, or the Docker container on your machine).

    LIVE_URL=https://your-space.hf.space pytest e2e/test_live.py

Uses only what needs no downloads (`my-bpe` and the estimate), so it passes even if Llama or Gemma cannot load.
"""
import json
import os
import urllib.error
import urllib.request

import pytest

BASE = os.getenv("LIVE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not BASE, reason="set LIVE_URL to the address of the running site")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.status, r.read().decode("utf-8")


def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read())


def test_the_page_and_its_assets_are_served():
    status, html = get("/")
    assert status == 200 and '<div id="root">' in html
    script = next(part.split('"')[0] for part in html.split('src="/')[1:])      # the main JavaScript file
    assert get("/" + script)[0] == 200


def test_the_api_answers_on_the_same_address():
    assert json.loads(get("/api/health")[1]) == {"status": "ok"}
    names = [t["name"] for t in json.loads(get("/api/tokenizers")[1])]
    assert "my-bpe" in names and "rule-of-thumb-4" in names


def test_tokenizing_works():
    status, body = post("/api/tokenize", {"text": "Hello 😊", "tokenizer": "my-bpe"})
    assert status == 200 and body["count"] > 0 and body["tokens"]


def test_compare_isolates_failures_and_labels_the_estimate():
    status, body = post("/api/compare", {"text": "Hello world", "tokenizers": ["my-bpe", "rule-of-thumb-4"]})
    rows = {r["name"]: r for r in body["results"]}
    assert status == 200 and rows["my-bpe"]["count"] > 0 and rows["rule-of-thumb-4"]["exact"] is False


def test_the_context_simulator_answers_cleanly():
    """Works, or says clearly that the model's tokenizer could not be loaded (503). Never a crash (500)."""
    models = json.loads(get("/api/models")[1])
    assert models, "no models configured"
    body = {"model": models[0]["id"], "messages": [{"role": "user", "text": "hi"}], "context_window": 100,
            "reserve_output": 10}
    try:
        status, result = post("/api/simulate", body)
        assert status == 200 and result["fits"]
    except urllib.error.HTTPError as err:
        assert err.code == 503


def test_bad_input_gets_a_clean_error_and_does_not_echo_it_back():
    with pytest.raises(urllib.error.HTTPError) as err:
        post("/api/tokenize", {"text": "SECRET-TEXT", "tokenizer": 5})
    assert err.value.code == 422 and b"SECRET-TEXT" not in err.value.read()
