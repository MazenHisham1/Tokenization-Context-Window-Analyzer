"""End-to-end tests: a real browser against the real front-end build and the offline demo API.

Run (from the project root):
    pip install -r requirements-dev.txt && playwright install chromium
    cd frontend && npm ci && npm run build && cd ..
    pytest e2e                       # E2E_BROWSER=firefox|webkit to try another browser

The servers are started and stopped by the fixtures below. Ports: API 8000, front end 4173.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="pip install playwright && playwright install chromium")

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
AXE = FRONTEND / "node_modules" / "axe-core" / "axe.min.js"
API_URL, APP_URL = "http://127.0.0.1:8000", "http://127.0.0.1:4173"
BROWSER = os.getenv("E2E_BROWSER", "chromium")

pytestmark = pytest.mark.skipif(
    not (FRONTEND / "dist" / "index.html").exists() or not AXE.exists(),
    reason="run `npm ci && npm run build` in frontend/ first",
)


def _wait(url: str, log: Path, seconds: float = 60) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except OSError:
            time.sleep(0.3)
    # Show what the server itself said, otherwise a CI failure is a mystery.
    output = log.read_text(errors="replace")[-2000:]
    raise RuntimeError(f"{url} did not start within {seconds} s. Server output:\n{output}")


@pytest.fixture(scope="session")
def servers():
    logs = Path(tempfile.mkdtemp())
    api_log, app_log = logs / "api.log", logs / "app.log"
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.demo:app", "--host", "127.0.0.1", "--port", "8000"],
                           cwd=ROOT, stdout=api_log.open("w"), stderr=subprocess.STDOUT)
    # --host 127.0.0.1: without it Vite listens on "localhost", which on some machines (GitHub's runners)
    # means IPv6 only, and then http://127.0.0.1:4173 is never reachable.
    app = subprocess.Popen(["npx", "vite", "preview", "--host", "127.0.0.1", "--port", "4173", "--strictPort"],
                           cwd=FRONTEND, stdout=app_log.open("w"), stderr=subprocess.STDOUT)
    try:
        _wait(f"{API_URL}/api/health", api_log)
        _wait(APP_URL, app_log)
        yield
    finally:
        for proc in (app, api):
            proc.terminate()
            proc.wait(timeout=10)


@pytest.fixture(scope="session")
def browser(servers):
    with sync_api.sync_playwright() as p:
        b = getattr(p, BROWSER).launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    pg = browser.new_page(viewport={"width": 1100, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(APP_URL)
    pg.wait_for_selector(".chips")
    yield pg
    assert errors == [], f"the browser reported errors: {errors}"   # every test also checks for console errors
    pg.close()


def set_text(page, text: str) -> None:
    """Set the text box directly. (Playwright's fill() simulates typing, which costs Chrome ~1 s for 50,000
    characters, and that would measure the browser, not our app.)"""
    page.evaluate(
        """(t) => { const ta = document.querySelector('textarea');
                   Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(ta, t);
                   ta.dispatchEvent(new Event('input', { bubbles: true })); }""", text)


def open_mode(page, name: str, ready: str) -> None:
    page.click(f"text={name}")
    page.wait_for_selector(ready, timeout=20000)


MODES = [("One tokenizer", ".chips"), ("Compare tokenizers", ".compare-table"), ("Context window", ".ctx-messages")]


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("mode,ready", MODES)
def test_no_accessibility_violations(browser, servers, mode, ready, scheme):
    """axe-core with the WCAG 2.0/2.1 A and AA rules plus best practices, in light and dark mode."""
    pg = browser.new_page(viewport={"width": 1100, "height": 900}, color_scheme=scheme)
    pg.goto(APP_URL)
    pg.wait_for_selector(".chips")
    open_mode(pg, mode, ready)
    pg.evaluate(AXE.read_text(encoding="utf-8"))
    result = pg.evaluate("axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice'] })")
    pg.close()
    found = [f'{v["id"]}: {v["help"]} ({v["nodes"][0]["target"]})' for v in result["violations"]]
    assert found == []


def test_keyboard_moves_between_tokens_and_announces_them(page):
    page.focus(".chips")
    page.keyboard.press("ArrowRight")
    first = page.locator("p.sr-only[role=status]").first.text_content()
    assert first.startswith("Token 1:") and "ID" in first
    page.keyboard.press("ArrowRight")
    assert page.locator("p.sr-only[role=status]").first.text_content().startswith("Token 2:")
    assert page.locator(".tooltip").count() == 1            # sighted keyboard users see the tooltip too
    page.keyboard.press("End")
    assert page.locator("p.sr-only[role=status]").first.text_content().startswith("Token 60:")
    page.keyboard.press("Escape")
    assert page.locator(".tooltip").count() == 0


def test_compare_labels_the_estimate_and_never_calls_it_fewest(page):
    open_mode(page, "Compare tokenizers", ".compare-table")
    row = page.locator("tr", has_text="rule-of-thumb-4")
    assert "estimate" in row.inner_text()
    assert "fewest" not in row.inner_text()
    assert page.locator(".panel", has_text="Estimate only").count() == 1
    assert page.locator(".panel").count() == 4


def test_context_simulator_drops_old_messages_and_keeps_system(page):
    open_mode(page, "Context window", ".ctx-messages")
    classes = [page.locator(".ctx-msg").nth(i).get_attribute("class") for i in range(page.locator(".ctx-msg").count())]
    assert "kept" in classes[0] and "kept" in classes[-1] and any("dropped" in c for c in classes)
    page.select_option(".ctx-settings .wide select", "error")
    page.wait_for_function("document.querySelector('.banner')?.textContent.includes('reject')")


def test_context_simulator_explains_an_invalid_setting(page):
    open_mode(page, "Context window", ".ctx-messages")
    page.fill("input >> nth=1", "5000")                    # reserved space larger than the window
    page.wait_for_selector(".error-text")
    assert "smaller than the context window" in page.inner_text(".error-text")


def test_maximum_input_stays_fast_and_the_payload_stays_small(page):
    text = ("Tokenization turns text into tokens. مرحبا 😊 The price is 1234567.89\n" * 800)[:50000]
    started = time.time()
    set_text(page, text)
    page.wait_for_selector(".notice", timeout=10000)        # "Coloured view shows the first 2,000 of N tokens"
    assert time.time() - started < 5
    assert page.locator(".chip").count() <= 2000
    body = page.request.post(f"{API_URL}/api/tokenize", data=json.dumps({"text": text, "tokenizer": "bpe-280"}),
                             headers={"Content-Type": "application/json"}).body()
    assert len(body) < 300_000                              # was 2.7 MB before the server capped the token list
    assert json.loads(body)["count"] > 2000
