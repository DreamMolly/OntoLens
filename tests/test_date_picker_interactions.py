"""Offline browser QA for the custom ISO date controls.

The fixture starts a disposable FastAPI/SQLite demo workspace and blocks every
browser request outside localhost.  These checks cover the custom control's
rendered calendar; native browser date-panel styling is intentionally out of
scope because Chromium owns that UI.
"""

from __future__ import annotations

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

from ontolens.web import create_app

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / ".runtime" / "date-picker-qa"
DATE_IDS = ("as-of", "ledger-recorded-at", "valid-from", "valid-until")


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
    errors: list[str] = []
    external: list[str] = []
    requests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="date-picker-isolated-", dir=ARTIFACTS) as directory:
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
                    context = browser.new_context(
                        base_url=f"http://127.0.0.1:{port}",
                        viewport={"width": 1440, "height": 1000},
                    )

                    def local_only(route):
                        if route.request.url.startswith(f"http://127.0.0.1:{port}/"):
                            route.continue_()
                        else:
                            external.append(route.request.url)
                            route.abort()

                    context.route("**/*", local_only)
                    tab = context.new_page()
                    tab.on("pageerror", lambda error: errors.append(str(error)))
                    tab.on(
                        "request",
                        lambda req: requests.append({"method": req.method, "url": req.url})
                        if "/api/" in req.url
                        else None,
                    )
                    tab.goto("/", wait_until="networkidle")
                    expect(tab.locator("#active-version")).to_have_text("demo-initial")
                    tab.date_api_requests = requests
                    try:
                        yield tab
                    finally:
                        summary = {
                            "scope": "isolated synthetic fixture; no live business, model, or DB validation",
                            "page_errors": errors,
                            "external_browser_requests": external,
                            "api_requests": requests,
                            "api_write_requests": [item for item in requests if item["method"] not in {"GET", "HEAD"}],
                            "static_sha256": {
                                name: hashlib.sha256((ROOT / "src/ontolens/static" / name).read_bytes()).hexdigest()
                                for name in ("app.js", "style.css", "index.html", "date-controls.js")
                            },
                        }
                        (ARTIFACTS / f"{request.node.name}.json").write_text(
                            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        (ARTIFACTS / "summary.json").write_text(
                            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                        assert not errors, errors
                        assert not external, external
                        assert not summary["api_write_requests"], summary["api_write_requests"]
                    browser.close()
            finally:
                server.should_exit = True
                worker.join(timeout=10)
                assert not worker.is_alive()


def shell(page, field_id: str):
    return page.locator(f"#{field_id}").locator("..")


def text_input(page, field_id: str):
    return shell(page, field_id).locator(".date-text")


def trigger(page, field_id: str):
    return shell(page, field_id).locator(".date-trigger")


def panel(page, field_id: str):
    return shell(page, field_id).locator(".date-panel")


def show_version_dates(page):
    page.locator('[data-view="versions"]').click()
    page.locator("#ledger-import-details").evaluate("el => { el.open = true; }")
    expect(text_input(page, "valid-from")).to_be_visible()


def test_native_iso_authority_and_all_date_fields(page):
    for field_id in DATE_IDS:
        native = page.locator(f"#{field_id}")
        expect(native).to_have_class("date-native")
        expect(trigger(page, field_id)).to_have_attribute("aria-haspopup", "dialog")

    as_of = text_input(page, "as-of")
    as_of.fill("2024-02-29")
    expect(page.locator("#as-of")).to_have_value("2024-02-29")
    expect(as_of).to_have_attribute("aria-invalid", "false")
    as_of.fill("2023-02-29")
    expect(page.locator("#as-of")).to_have_value("")
    expect(as_of).to_have_attribute("aria-invalid", "true")

    # ISO civil dates stay day-stable when inspected in UTC and local time.
    as_of.fill("2024-03-01")
    assert page.locator("#as-of").evaluate("el => ({value: el.value, utc: new Date(el.value + 'T00:00:00Z').getUTCDate()})") == {
        "value": "2024-03-01",
        "utc": 1,
    }
    show_version_dates(page)
    text_input(page, "ledger-recorded-at").fill("2030-01-02")
    text_input(page, "valid-from").fill("2025-01-03")
    text_input(page, "valid-until").fill("2025-12-31")
    expect(page.locator("#ledger-recorded-at")).to_have_value("2030-01-02")
    expect(page.locator("#valid-from")).to_have_value("2025-01-03")
    expect(page.locator("#valid-until")).to_have_value("2025-12-31")


def test_panel_dialog_grid_header_navigation_and_keyboard(page):
    show_version_dates(page)
    field = "valid-from"
    text_input(page, field).fill("2024-02-29")
    trigger(page, field).click()
    cal = panel(page, field)
    expect(cal).to_be_visible()
    expect(cal).to_have_attribute("role", "dialog")
    expect(cal.locator(".date-grid")).to_be_visible()
    expect(cal.locator(".date-weekday")).to_have_count(7)
    expect(cal.locator(".date-day")).to_have_count(42)
    expect(cal.locator(".date-month")).to_be_visible()
    expect(cal.locator(".date-year")).to_have_value("2024")
    expect(cal.locator("[aria-pressed=true]")).to_have_attribute("data-day", "29")

    month_before = cal.locator(".date-month").input_value()
    cal.get_by_role("button", name="下个月").click()
    assert cal.locator(".date-month").input_value() != month_before
    cal.get_by_role("button", name="上个月").click()
    expect(cal.locator(".date-month")).to_have_value(month_before)

    active = cal.locator(".date-day[tabindex='0']")
    active.press("ArrowRight")
    active = cal.locator(".date-day[tabindex='0']")
    active.press("ArrowDown")
    active.press("Home")
    active.press("End")
    active.press("PageUp")
    active.press("PageDown")
    active.press("Escape")
    expect(cal).to_be_hidden()
    expect(text_input(page, field)).to_be_focused()

    trigger(page, field).click()
    cal.locator(".date-day:not(:disabled)").first.press("Enter")
    expect(cal).to_be_hidden()
    assert page.locator("#valid-from").input_value()


def test_bounds_required_invalid_input_and_focus_recovery(page):
    show_version_dates(page)
    field = page.locator("#valid-from")
    field.evaluate("el => { el.min = '2024-01-01'; el.max = '2024-12-31'; }")
    text = text_input(page, "valid-from")
    text.fill("2023-12-31")
    expect(field).to_have_value("")
    expect(text).to_have_attribute("aria-invalid", "true")
    text.fill("2024-06-30")
    expect(field).to_have_value("2024-06-30")
    trigger(page, "valid-from").click()
    assert panel(page, "valid-from").locator("[data-day]").evaluate_all("nodes => nodes.filter(n => !n.disabled).length") > 0
    panel(page, "valid-from").press("Escape")

    with page.expect_response(lambda response: response.request.method == "GET" and response.url.endswith("/api/runs")):
        page.locator('[data-view="check"]').click()
    required = text_input(page, "as-of")
    required.fill("")
    expect(page.locator("#as-of")).to_have_value("")
    expect(required).to_have_attribute("aria-invalid", "true")
    submit = page.locator("#check-form button[type=submit]")
    expect(submit).to_be_enabled()
    submit.click()
    expect(required).to_be_focused()
    expect(required).to_have_attribute("aria-invalid", "true")


def test_leap_year_month_year_and_timezone_safe_calendar_value(page):
    show_version_dates(page)
    field = "valid-until"
    text_input(page, field).fill("2024-02-29")
    trigger(page, field).click()
    cal = panel(page, field)
    expect(cal.locator(".date-year")).to_have_value("2024")
    expect(cal.locator(".date-month")).to_have_value("2")
    expect(cal.locator("[data-day='29']")).to_be_enabled()
    cal.locator(".date-year").fill("2025")
    cal.locator(".date-year").press("Enter")
    cal.locator(".date-month").select_option("2")
    expect(cal.locator("[data-day='29']")).to_have_count(0)
    cal.locator(".date-year").fill("2024")
    cal.locator(".date-year").press("Enter")
    expect(cal.locator("[data-day='29']")).to_be_enabled()
    cal.locator("[data-day='29']").click(force=True)
    expect(page.locator("#valid-until")).to_have_value("2024-02-29")
    assert page.locator("#valid-until").evaluate("el => ({value: el.value, utc: new Date(el.value + 'T00:00:00Z').toISOString().slice(0, 10)})") == {
        "value": "2024-02-29",
        "utc": "2024-02-29",
    }


def test_mobile_dismissal_resize_scroll_screenshots_and_motion(page):
    text_input(page, "as-of").fill("2024-02-29")
    trigger(page, "as-of").click()
    motion = panel(page, "as-of").locator("xpath=.").evaluate("el => el.getAnimations()[0]?.effect?.getTiming()?.duration")
    assert motion == 160
    page.screenshot(path=str(ARTIFACTS / "desktop-date-picker.png"), full_page=False)
    page.mouse.click(4, 4)
    expect(panel(page, "as-of")).to_be_hidden()
    value = page.locator("#as-of").input_value()
    dismissal_failures = []

    for width in (320, 390):
        page.set_viewport_size({"width": width, "height": 680})
        trigger(page, "as-of").click()
        cal = panel(page, "as-of")
        bounds = cal.bounding_box()
        assert bounds and bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(ARTIFACTS / f"mobile-{width}-date-picker.png"), full_page=False)
        page.set_viewport_size({"width": width - 1, "height": 679})
        expect(cal).to_be_hidden()
        assert page.locator("#as-of").input_value() == value
        trigger(page, "as-of").click()
        page.mouse.wheel(0, 220)
        expect(cal).to_be_hidden()
        assert page.locator("#as-of").input_value() == value

    page.emulate_media(reduced_motion="reduce")
    trigger(page, "as-of").click()
    assert panel(page, "as-of").evaluate("el => el.getAnimations().length") == 0
    panel(page, "as-of").press("Escape")
    assert dismissal_failures == [], dismissal_failures


def test_date_interactions_make_no_api_writes(page):
    for field_id, value in (("as-of", "2024-02-29"),):
        text_input(page, field_id).fill(value)
        trigger(page, field_id).click()
        panel(page, field_id).press("Escape")
    show_version_dates(page)
    for field_id, value in (("ledger-recorded-at", "2024-03-01"), ("valid-from", "2024-04-01"),
                            ("valid-until", "2024-04-30")):
        text_input(page, field_id).fill(value)
        trigger(page, field_id).click()
        panel(page, field_id).press("Escape")
    assert [item for item in page.date_api_requests if item["method"] not in {"GET", "HEAD"}] == []
