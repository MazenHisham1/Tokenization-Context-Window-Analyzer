"""Public-site features: rate limit, proxy addresses, serving the web app, warm-up."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.hardening import RateLimiter, add_rate_limit, warm_up
from api.main import create_app
from api.schemas import TokenizerInfo
from src.bpe import BPETokenizer
from src.config import ModelSpec
from src.tokenizers import CustomBPEAdapter, TokenizerRegistry


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_app(static_dir=None):
    reg = TokenizerRegistry()
    reg.register(CustomBPEAdapter(BPETokenizer().train("hello world " * 20, vocab_size=280), name="bpe"))
    infos = [TokenizerInfo(name="bpe", family="custom", algorithm="bpe", exact=True)]
    models = {"m": ModelSpec("m", "M", "bpe", 100, "test", date(2026, 1, 1))}
    return create_app(reg, infos, models, static_dir=static_dir)


# ---- RateLimiter ----
def test_limiter_allows_up_to_the_limit_then_says_how_long_to_wait():
    clock = Clock()
    rl = RateLimiter(3, 60, clock)
    assert [rl.check("a") for _ in range(3)] == [0, 0, 0]
    clock.now += 10
    assert rl.check("a") == pytest.approx(50)          # the oldest call leaves the window in 50 s


def test_limiter_window_slides_and_keys_are_independent():
    clock = Clock()
    rl = RateLimiter(2, 60, clock)
    rl.check("a")
    rl.check("a")
    assert rl.check("b") == 0                           # someone else is not affected
    clock.now += 61
    assert rl.check("a") == 0                           # the window has passed


def test_limiter_rejects_nonsense_settings():
    with pytest.raises(ValueError):
        RateLimiter(0)


def test_limiter_forgets_idle_keys():
    clock = Clock()
    rl = RateLimiter(1, 1, clock)
    for i in range(10_005):
        rl.check(f"ip{i}")
    clock.now += 5
    rl.check("fresh")
    assert len(rl._hits) < 10_005


# ---- middleware ----
def test_api_is_limited_but_health_and_the_page_are_not():
    app = make_app()
    add_rate_limit(app, 2, clock=Clock())
    c = TestClient(app)
    body = {"text": "hi", "tokenizer": "bpe"}
    assert c.post("/api/tokenize", json=body).status_code == 200
    assert c.post("/api/tokenize", json=body).status_code == 200
    r = c.post("/api/tokenize", json=body)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1 and "wait" in r.json()["detail"]
    assert c.get("/api/health").status_code == 200       # a health check must keep working


def test_forwarded_header_is_ignored_unless_proxies_are_trusted():
    app = make_app()
    add_rate_limit(app, 1, proxy_hops=0, clock=Clock())
    c = TestClient(app)
    assert c.get("/api/tokenizers", headers={"x-forwarded-for": "1.1.1.1"}).status_code == 200
    # a faked address does not give a second allowance
    assert c.get("/api/tokenizers", headers={"x-forwarded-for": "2.2.2.2"}).status_code == 429


def test_with_a_trusted_proxy_each_real_client_gets_its_own_allowance():
    app = make_app()
    add_rate_limit(app, 1, proxy_hops=1, clock=Clock())
    c = TestClient(app)
    # the proxy appends the address it saw; whatever the client put in front is ignored
    assert c.get("/api/tokenizers", headers={"x-forwarded-for": "faked, 10.0.0.1"}).status_code == 200
    assert c.get("/api/tokenizers", headers={"x-forwarded-for": "other-fake, 10.0.0.1"}).status_code == 429
    assert c.get("/api/tokenizers", headers={"x-forwarded-for": "10.0.0.2"}).status_code == 200


# ---- serving the web app ----
def test_the_built_web_app_is_served_and_the_api_still_wins(tmp_path):
    (tmp_path / "index.html").write_text("<html>app</html>")
    c = TestClient(make_app(tmp_path))
    assert "app" in c.get("/").text
    assert c.get("/api/health").json() == {"status": "ok"}
    assert c.get("/api/tokenizers").status_code == 200
    assert c.get("/docs").status_code == 200


def test_without_a_build_the_api_runs_alone(tmp_path):
    c = TestClient(make_app(tmp_path))                  # a folder with no index.html
    assert c.get("/").status_code == 404
    assert c.get("/api/health").status_code == 200


# ---- warm-up ----
def test_warm_up_loads_in_the_background_and_survives_a_failing_tokenizer():
    reg = TokenizerRegistry()
    loaded = []

    def good():
        loaded.append("good")
        return CustomBPEAdapter(BPETokenizer().train("hello " * 20, vocab_size=280), name="good")

    def bad():
        raise RuntimeError("gated: no token")

    reg.register_factory("bad", bad)
    reg.register_factory("good", good)
    warm_up(reg, ["bad", "good"]).join(timeout=10)
    assert loaded == ["good"]                              # the failure did not stop the next one
