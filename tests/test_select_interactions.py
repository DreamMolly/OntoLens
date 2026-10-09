"""Select interaction regressions against a disposable, offline synthetic workspace.

No production database, credentials, external model, or live service is used.
"""

import hashlib
import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
pytest.importorskip("uvicorn")

import uvicorn
from playwright.sync_api import expect, sync_playwright

from peiwu.web import create_app

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".runtime" / "select-final-qa"


@pytest.fixture
def page(monkeypatch, request):
    for name in tuple(os.environ):
        if (name in {"PEIWU_AUTH_FILE", "PEIWU_SESSION_DB", "PEIWU_MCP_TOKEN"}
                or name.startswith(("PEIWU_NEXENT_", "PEIWU_MODEL", "TYPESAFE"))):
            monkeypatch.delenv(name, raising=False)
    cache = ROOT / ".runtime" / "playwright-browsers"
    if cache.is_dir():
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(cache))
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    errors, external, api_requests = [], [], []
    with tempfile.TemporaryDirectory(prefix="isolated-", dir=ARTIFACTS) as directory:
        app = create_app(ROOT, Path(directory) / "workspace.sqlite3", seed_demo=True)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
            worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            worker.start()
            try:
                deadline = time.monotonic() + 10
                while not server.started and worker.is_alive() and time.monotonic() < deadline:
                    time.sleep(0.01)
                assert server.started
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    context = browser.new_context(base_url=f"http://127.0.0.1:{port}", viewport={"width": 1440, "height": 1000})
                    def local_only(route):
                        if route.request.url.startswith(f"http://127.0.0.1:{port}/"):
                            route.continue_()
                        else:
                            external.append(route.request.url)
                            route.abort()
                    context.route("**/*", local_only)
                    tab = context.new_page()
                    tab.on("pageerror", lambda error: errors.append(str(error)))
                    tab.on("request", lambda req: api_requests.append({"method": req.method, "url": req.url}) if "/api/" in req.url else None)
                    tab.goto("/", wait_until="networkidle")
                    expect(tab.locator("#active-version")).to_have_text("demo-initial")
                    tab.select_api_requests = api_requests
                    try:
                        yield tab
                        assert not errors, errors
                        assert not external, external
                    finally:
                        (ARTIFACTS / (request.node.name + ".json")).write_text(json.dumps({
                            "scope": "isolated synthetic fixture; no live business or model validation",
                            "page_errors": errors, "external_browser_requests": external,
                            "api_requests": api_requests,
                            "static_sha256": {name: hashlib.sha256((ROOT / "src/peiwu/static" / name).read_bytes()).hexdigest()
                                              for name in ("app.js", "style.css", "index.html")},
                        }, ensure_ascii=False, indent=2), encoding="utf-8")
                        browser.close()
            finally:
                server.should_exit = True
                worker.join(timeout=10)
                assert not worker.is_alive()


def trigger(page, name="requester"):
    return page.locator(f"#{name}-trigger")


def menu(page):
    return page.locator("#enhanced-select-menu")


def current_label(page, name):
    return page.locator(f"#{name}").evaluate("s => s.selectedOptions[0]?.textContent || '请选择…'")


def assert_synced(page, name):
    expect(trigger(page, name).locator(".select-value")).to_have_text(current_label(page, name))


def test_native_values_labels_and_presets_stay_synchronized(page):
    expect(page.locator("#requester")).to_be_visible()
    page.locator("#requester").select_option("stu03")
    assert_synced(page, "requester")
    expect(trigger(page)).to_have_attribute("aria-label", "申请人：" + current_label(page, "requester"))
    page.locator('[data-preset="missing"]').click()
    expect(page.locator("#requester")).to_have_value("unknown_demo_person")
    assert_synced(page, "requester")
    page.locator('[data-preset="allow"]').click()
    expect(page.locator('#requester option[value="unknown_demo_person"]')).to_have_count(0)
    for name in ("requester", "lot", "cabinet"):
        assert_synced(page, name)
    page.locator("#check-form").evaluate("form => form.reset()")
    for name in ("requester", "lot", "cabinet"):
        assert_synced(page, name)
    page.locator('[data-view="sources"]').click()
    page.locator("#source-kind").select_option("private")
    assert_synced(page, "source-kind")
    expect(page.locator("#source-external")).to_be_disabled()


def test_pointer_keyboard_commit_escape_tab_and_aria(page):
    initial = page.locator("#requester").input_value()
    trigger(page).click()
    expect(menu(page)).to_be_visible()
    expect(trigger(page)).to_have_attribute("aria-expanded", "true")
    expect(menu(page).locator('[aria-selected="true"]')).to_have_text(current_label(page, "requester"))
    page.wait_for_function("() => document.querySelector('#enhanced-select-menu').getAnimations().length === 0")
    assert all(height >= 44 for height in menu(page).locator(".select-option").evaluate_all("nodes => nodes.map(n => n.getBoundingClientRect().height)"))
    selected_id = trigger(page).get_attribute("aria-activedescendant")
    expect(page.locator("#" + selected_id)).to_have_attribute("data-active", "true")
    trigger(page).press("End")
    final_value = page.locator("#requester option").last.get_attribute("value")
    trigger(page).press("Escape")
    expect(menu(page)).to_be_hidden()
    expect(page.locator("#requester")).to_have_value(initial)
    expect(trigger(page)).to_be_focused()
    trigger(page).press("Enter")
    trigger(page).press("End")
    trigger(page).press("Enter")
    expect(page.locator("#requester")).to_have_value(final_value)
    assert_synced(page, "requester")
    trigger(page).click()
    trigger(page).press("Tab")
    expect(menu(page)).to_be_hidden()
    expect(trigger(page, "lot")).to_be_focused()
    trigger(page).click()
    first_value = page.locator("#requester option").first.get_attribute("value")
    menu(page).locator(".select-option").first.click()
    expect(page.locator("#requester")).to_have_value(first_value)
    expect(trigger(page)).not_to_have_attribute("aria-activedescendant", ".+")


def test_typeahead_and_disabled_options_do_not_commit_until_enter(page):
    initial = page.locator("#requester").input_value()
    trigger(page).press("s")
    trigger(page).press("t")
    trigger(page).press("u")
    trigger(page).press("0")
    trigger(page).press("3")
    expect(page.locator("#" + trigger(page).get_attribute("aria-activedescendant"))).to_contain_text(current_label_for_value(page, "requester", "stu03"))
    expect(page.locator("#requester")).to_have_value(initial)
    trigger(page).press("Enter")
    expect(page.locator("#requester")).to_have_value("stu03")
    page.locator('#requester option[value="stu03"]').evaluate("o => o.disabled = true")
    trigger(page).click()
    expect(menu(page).locator('[aria-disabled="true"]')).to_have_count(1)
    trigger(page).press("End")
    expect(page.locator("#" + trigger(page).get_attribute("aria-activedescendant"))).to_have_attribute("aria-disabled", "false")
    trigger(page).press("Enter")
    assert page.locator("#requester").input_value() != "stu03"


def current_label_for_value(page, name, value):
    return page.locator(f'#{name} option[value="{value}"]').text_content()


def test_async_sources_loading_failure_refresh_and_required_focus(page):
    token = page.request.get("/api/status").json()["csrf_token"]
    response = page.request.post("/api/documents", headers={"X-Peiwu-Token": token}, multipart={
        "kind": "synthetic", "file": {"name": "select-refresh.md", "mimeType": "text/plain", "buffer": b"select refreshed fragment\nstu01 ACID"},
    })
    assert response.status == 201
    source = response.json()
    page.locator('[data-view="versions"]').click()
    expect(page.locator(f'#candidate-source option[value="{source["id"]}"]')).to_have_count(1)
    pending = []
    page.route(f'**/api/documents/{source["id"]}', lambda route: pending.append(route))
    page.locator("#candidate-source").select_option(source["id"])
    expect(trigger(page, "candidate-locator")).to_be_disabled()
    expect(trigger(page, "candidate-locator")).to_contain_text("正在读取")
    assert len(pending) == 1
    pending.pop().fulfill(status=503, json={"detail": "offline fixture unavailable"})
    expect(trigger(page, "candidate-locator")).to_be_disabled()
    expect(trigger(page, "candidate-locator")).to_contain_text("来源读取失败")
    alternatives = page.locator("#candidate-source option").evaluate_all("nodes => nodes.map(n => n.value)")
    page.locator("#candidate-source").select_option(next(value for value in alternatives if value != source["id"]))
    expect(trigger(page, "candidate-locator")).to_be_enabled()
    assert_synced(page, "candidate-source")
    assert_synced(page, "candidate-locator")
    expect(trigger(page, "candidate-locator")).to_have_attribute("aria-describedby", "candidate-source-status")
    page.locator('[data-view="check"]').click()
    page.locator("#requester").evaluate("s => { s.value = ''; s.setAttribute('aria-invalid', 'true'); s.dispatchEvent(new Event('change', {bubbles:true})); }")
    expect(trigger(page)).to_have_attribute("aria-required", "true")
    expect(trigger(page)).to_have_attribute("aria-invalid", "true")
    page.locator('#check-form button[type="submit"]').click()
    expect(trigger(page)).to_be_focused()
    trigger(page).press("Enter")
    trigger(page).press("Home")
    trigger(page).press("Enter")
    assert page.locator("#requester").input_value()


def test_dismissals_sidebar_and_resize_preserve_values_without_api_writes(page):
    before = len(page.select_api_requests)
    initial = page.locator("#requester").input_value()
    trigger(page).click()
    page.locator(".request-panel h2").click()
    expect(menu(page)).to_be_hidden()
    trigger(page).click()
    page.set_viewport_size({"width": 1300, "height": 900})
    expect(menu(page)).to_be_hidden()
    trigger(page).click()
    page.mouse.move(1200, 800)
    page.mouse.wheel(0, 180)
    expect(menu(page)).to_be_hidden()
    trigger(page).click()
    page.locator("#sidebar-toggle").click()
    expect(menu(page)).to_be_hidden()
    expect(page.locator("#requester")).to_have_value(initial)
    assert_synced(page, "requester")
    page.wait_for_load_state("networkidle")
    assert len(page.select_api_requests) == before


def test_mobile_flip_motion_reduced_motion_and_fast_reopen(page):
    page.add_init_script("window.__selectMotion = [];")
    page.evaluate("""() => {
        window.__selectMotion = [];
        const animate = Element.prototype.animate;
        Element.prototype.animate = function(frames, options) {
            const result = animate.call(this, frames, options);
            if (this.id === 'enhanced-select-menu') window.__selectMotion.push({duration: options.duration, frames});
            return result;
        };
    }""")
    trigger(page).click()
    assert page.evaluate("window.__selectMotion[0].duration") == 160
    page.wait_for_function("() => document.querySelector('#enhanced-select-menu').getAnimations().length === 0")
    page.screenshot(path=str(ARTIFACTS / "desktop-1440-menu.png"))
    trigger(page).press("Escape")
    for width in (320, 390):
        page.set_viewport_size({"width": width, "height": 680})
        trigger(page, "cabinet").scroll_into_view_if_needed()
        page.evaluate("window.scrollTo(0, Math.max(0, document.querySelector('#cabinet-trigger').getBoundingClientRect().bottom + scrollY - innerHeight + 65))")
        trigger(page, "cabinet").click()
        expect(menu(page)).to_have_attribute("data-side", "top")
        page.wait_for_timeout(170)
        bounds = menu(page).bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width
        assert bounds["y"] >= 0 and bounds["y"] + bounds["height"] <= 680
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(ARTIFACTS / f"mobile-{width}-menu.png"))
        trigger(page, "cabinet").press("Escape")
    page.emulate_media(reduced_motion="reduce")
    trigger(page, "cabinet").click()
    assert menu(page).evaluate("n => n.getAnimations().length") == 0
    trigger(page, "cabinet").press("Escape")
    expect(menu(page)).to_be_hidden()
    page.emulate_media(reduced_motion="no-preference")
    page.evaluate("""() => { const button = document.querySelector('#cabinet-trigger');
        button.click(); button.click(); button.click(); }
    """)
    page.wait_for_timeout(200)
    expect(menu(page)).to_be_visible()
    expect(trigger(page, "cabinet")).to_have_attribute("aria-expanded", "true")
    trigger(page, "cabinet").press("Escape")
    page.wait_for_timeout(130)
    expect(menu(page)).to_be_hidden()
    assert menu(page).evaluate("n => !n.matches(':popover-open') && n.inert && n.getAnimations().length === 0")
    # Probe an existing enhanced control inside a modal in this disposable DOM.
    # A top-layer popover outside the modal remains inert, so real pointer input matters.
    page.locator('[data-view="sources"]').click()
    page.evaluate("""() => { const dialog = document.querySelector('#source-dialog');
        dialog.append(document.querySelector('#source-kind').closest('.select-shell'));
        dialog.showModal(); }
    """)
    trigger(page, "source-kind").click()
    menu(page).locator(".select-option").nth(1).click()
    expect(page.locator("#source-kind")).to_have_value("public")
    expect(trigger(page, "source-kind")).to_be_focused()
