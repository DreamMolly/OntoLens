"""Browser regressions for source-bound editing and decision-bound responses.

Every test runs against a new local database. Model responses are browser stubs;
the application is never configured to contact an external model.
"""

import json
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


@pytest.fixture
def page(monkeypatch):
    for name in ("PEIWU_MODEL_BASE_URL", "PEIWU_MODEL_NAME", "PEIWU_MODEL_API_KEY",
                 "PEIWU_MCP_TOKEN", "TYPESAFE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    browser_cache = ROOT / ".runtime" / "playwright-browsers"
    if browser_cache.is_dir():
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(browser_cache))
    runtime = ROOT / ".runtime"
    runtime.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="workbench-flow-", dir=runtime) as directory:
        app = create_app(ROOT, Path(directory) / "workbench.sqlite3", seed_demo=True)
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
                assert server.started, "isolated workbench did not start"
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(headless=True)
                    context = browser.new_context(base_url=f"http://127.0.0.1:{port}")
                    tab = context.new_page()
                    tab.goto("/")
                    tab.wait_for_load_state("networkidle")
                    expect(tab.locator("#active-version")).to_have_text("demo-initial")
                    try:
                        yield tab
                    finally:
                        browser.close()
            finally:
                server.should_exit = True
                worker.join(timeout=10)
                assert not worker.is_alive(), "isolated workbench did not stop"


def import_source(page, name, content):
    token = page.request.get("/api/status").json()["csrf_token"]
    response = page.request.post("/api/documents", headers={"X-Peiwu-Token": token}, multipart={
        "kind": "synthetic", "file": {"name": name, "mimeType": "text/plain", "buffer": content.encode()},
    })
    assert response.status == 201, response.text()
    return response.json()


def edit_request(page):
    """Use the visible edit action when a result has collapsed the draft."""
    if not page.locator("#request-editor").is_visible():
        page.locator("#toggle-request").click()
    expect(page.locator("#request-editor")).to_be_visible()


def test_late_source_response_cannot_replace_selected_source_locators(page):
    first = import_source(page, "first.md", "first header\nstu01 授权仅保留 ACID。")
    second = import_source(page, "second.md", "second selected source\nstu01 授权仅保留 BASE。")
    page.locator('[data-view="versions"]').click()
    expect(page.locator("#candidate-source option", has_text="second.md")).to_have_count(1)
    page.locator("#candidate-source").select_option(second["id"])
    expect(page.locator("#candidate-locator")).to_contain_text("second selected source")
    pending = []
    page.route(f"**/api/documents/{first['id']}", lambda route: pending.append(route))
    page.locator("#candidate-source").select_option(first["id"])
    expect(page.locator("#candidate-source")).to_have_value(first["id"])
    expect(page.locator("#candidate-locator")).to_be_disabled()
    expect(page.locator("#candidate-submit")).to_be_disabled()
    page.locator("#candidate-source").select_option(second["id"])
    expect(page.locator("#candidate-locator")).to_contain_text("second selected source")
    expect(page.locator("#candidate-submit")).to_be_enabled()
    assert len(pending) == 1
    pending[0].fulfill(status=200, json=first)
    page.wait_for_load_state("networkidle")
    expect(page.locator("#candidate-locator")).not_to_contain_text("first header")
    expect(page.locator("#candidate-locator")).to_contain_text("second selected source")


def test_source_loading_and_failure_cannot_submit_unrelated_fragment(page):
    source = import_source(page, "unavailable.md", "stu01 授权仅保留 ACID。")
    page.locator('[data-view="versions"]').click()
    expect(page.locator("#candidate-source option", has_text="unavailable.md")).to_have_count(1)
    available = page.locator("#candidate-source option").first.get_attribute("value")
    if available == source["id"]:
        available = page.locator("#candidate-source option").nth(1).get_attribute("value")
    page.locator("#candidate-source").select_option(available)
    expect(page.locator("#candidate-submit")).to_be_enabled()
    pending = []
    page.route(f"**/api/documents/{source['id']}", lambda route: pending.append(route))
    page.locator("#candidate-source").select_option(source["id"])
    page.locator("#candidate-note").fill("source must be loaded before editing")
    page.locator("#candidate-form").evaluate("form => form.requestSubmit()")
    expect(page.locator("#notice")).to_contain_text("所选来源片段尚未准备好")
    assert page.request.get("/api/versions").json()["candidates"] == []
    assert len(pending) == 1
    pending[0].fulfill(status=503, json={"detail": "来源暂时不可用"})
    expect(page.locator("#candidate-source-status")).to_contain_text("读取失败")
    expect(page.locator("#candidate-submit")).to_be_disabled()
    expect(page.locator("#candidate-locator")).to_have_value("")
    page.locator("#candidate-source").select_option(available)
    expect(page.locator("#candidate-submit")).to_be_enabled()


@pytest.mark.parametrize("status,payload", [
    (200, {"notice": "模拟响应", "text": "旧申请允许领用"}),
    (502, {"detail": "旧申请的模型服务失败"}),
])
def test_model_reply_for_previous_run_never_labels_new_decision(page, status, payload):
    def configured_status(route):
        response = route.fetch()
        payload = response.json()
        payload["model_configured"] = True
        route.fulfill(response=response, json=payload)

    page.route("**/api/status", configured_status)
    page.reload(wait_until="networkidle")
    page.locator("#as-of").fill("2026-09-23")
    page.locator('#check-form button[type="submit"]').click()
    expect(page.locator("#decision-action")).to_have_text("允许领用")
    first_run_id = json.loads(page.locator("#decision-json").text_content())["run_id"]
    pending = []
    page.route("**/api/runs/*/explain", lambda route: pending.append(route))
    page.locator("#explain-button").click()
    edit_request(page)
    page.locator('[data-preset="conflict"]').click()
    page.locator('#check-form button[type="submit"]').click()
    expect(page.locator("#decision-action")).to_have_text("本次打回")
    expect(page.locator("#notice")).to_contain_text("本次记录已保存")
    successor_notice = page.locator("#notice").text_content()
    assert len(pending) == 1
    second_run_id = json.loads(page.locator("#decision-json").text_content())["run_id"]
    expect(page.locator("#explain-button")).to_be_enabled()
    page.locator("#explain-button").click()
    expect(page.locator("#explain-button")).to_be_disabled()
    assert len(pending) == 2
    assert pending[0].request.url.endswith(f"/api/runs/{first_run_id}/explain")
    assert pending[1].request.url.endswith(f"/api/runs/{second_run_id}/explain")
    pending[0].fulfill(status=status, json=payload)
    page.wait_for_function("runId => !pendingModels.has(runId)", arg=first_run_id)
    expect(page.locator("#explain-button")).to_be_disabled()
    expect(page.locator("#model-output")).to_be_hidden()
    expect(page.locator("#notice")).to_have_text(successor_notice)
    expect(page.locator("#notice")).to_have_attribute("role", "status")
    pending[1].fulfill(status=200, json={"notice": "模拟响应", "text": "当前申请因冲突被打回"})
    expect(page.locator("#model-output")).to_have_text("模拟响应\n\n当前申请因冲突被打回")
    expect(page.locator("#explain-button")).to_be_enabled()


def test_needs_review_ui_shows_gap_and_records_human_follow_up(page):
    expect(page.locator('#requester option[value="unknown_demo_person"]')).to_have_count(0)
    result = create_review_run(page)
    expect(page.locator("#missing-demo-note")).to_be_visible()
    expect(page.locator('#requester option[value="unknown_demo_person"]')).to_have_text("未登记合成人员 · unknown_demo_person（资料缺失演示）")
    assert "unknown_demo_person" not in page.request.get("/api/catalog").json()["catalog"]["people"]
    expect(page.locator("#review-panel")).to_be_visible()
    expect(page.locator("#review-guidance")).to_contain_text("MISSING_REFERENCE")
    expect(page.locator("#review-guidance")).to_contain_text("补充带来源定位")
    expect(page.locator("#review-references input:checked")).to_have_count(0)
    page.locator("#reviewer").fill("演示审核员")
    page.locator("#review-note").fill("已请求人员授权原文")
    page.locator("#review-form").evaluate("form => form.requestSubmit()")
    expect(page.locator("#review-history")).to_contain_text("演示审核员")
    expect(page.locator("#review-history")).to_contain_text("未选择来源引用")
    expect(page.locator("#decision-action")).to_have_text("需要人工复核")
    saved = next(run for run in page.request.get("/api/runs").json() if run["id"] == result["run_id"])["result"]
    assert saved["decision"] is None
    assert saved["review_records"][0]["evidence_references"] == []
    assert saved["review_records"][0]["evidence_ids"] == []
    page.locator('[data-preset="missing"]').click()
    expect(page.locator('#requester option[value="unknown_demo_person"]')).to_have_count(1)
    create_review_run(page, requester_id="stu01")
    expect(page.locator('#requester option[value="unknown_demo_person"]')).to_have_count(0)
    expect(page.locator("#missing-demo-note")).to_be_hidden()
    expect(page.locator("#decision-action")).to_have_text("允许领用")
    expect(page.locator("#review-panel")).to_be_hidden()


def create_review_run(page, requester_id="unknown_demo_person"):
    edit_request(page)
    page.locator('[data-preset="missing"]' if requester_id == "unknown_demo_person" else '[data-preset="allow"]').click()
    page.locator("#as-of").fill("2026-09-23")
    with page.expect_response("**/api/check") as checked:
        page.locator('#check-form button[type="submit"]').click()
    response = checked.value
    assert response.status == 200, response.text()
    assert response.request.post_data_json["requester_id"] == requester_id
    result = response.json()
    expect(page.locator("#decision-json")).to_contain_text(result["run_id"])
    return result


@pytest.mark.parametrize("unresolved", [False, True])
def test_human_review_saves_only_explicit_current_reference(page, unresolved):
    result = create_review_run(page)
    choices = page.locator("#review-references input")
    assert choices.count() > 1
    expect(page.locator("#review-references input:checked")).to_have_count(0)
    references = [json.loads(choices.nth(index).get_attribute("value")) for index in range(choices.count())]
    index = next(index for index, reference in enumerate(references) if reference["unresolved"] is unresolved)
    chosen = references[index]
    card = page.locator(".review-reference").nth(index)
    expect(card).to_contain_text("缺失原文 · 待补件" if unresolved else "已定位原文")
    if unresolved:
        assert chosen["quote"] is None
    else:
        expect(card.locator("blockquote")).to_have_text(chosen["quote"])
    choices.nth(index).check()
    requests = []

    def capture_review(route):
        requests.append(route.request.post_data_json)
        route.continue_()

    page.route("**/api/runs/*/review", capture_review)
    page.locator("#reviewer").fill("逐引用审核员")
    page.locator("#review-status").select_option("evidence_requested" if unresolved else "in_review")
    page.locator("#review-note").fill("仅记录所选引用")
    page.locator("#review-submit").click()
    expect(page.locator("#review-history")).to_contain_text("逐引用审核员")
    assert len(requests) == 1
    assert "evidence_ids" not in requests[0]
    assert requests[0]["evidence_references"] == [chosen]
    displayed = json.loads(page.locator("#decision-json").text_content())
    record = displayed["review_records"][0]
    assert record["evidence_references"] == [chosen]
    assert displayed["decision"] is None
    assert record["decision_written"] is False
    expect(page.locator("#review-history")).to_contain_text(chosen["locator"])
    expect(page.locator("#review-history")).to_contain_text(chosen["sha256"])
    expect(page.locator("#review-history")).to_contain_text("缺失原文 · 待补件" if unresolved else "已定位原文")
    saved = next(run for run in page.request.get("/api/runs").json() if run["id"] == result["run_id"])
    assert saved["result"]["review_records"] == displayed["review_records"]
    exported = page.request.get(f"/api/runs/{result['run_id']}/export").json()
    assert exported["run"]["result"]["review_records"] == displayed["review_records"]
    page.locator('[data-view="history"]').click()
    page.locator("#run-list .list-card", has=page.locator(f'a[href="/api/runs/{result["run_id"]}/export"]')).get_by_role("button", name="打开历史证据").click()
    expect(page.locator("#review-history")).to_contain_text("逐引用审核员")
    assert json.loads(page.locator("#decision-json").text_content())["review_records"] == displayed["review_records"]


@pytest.mark.parametrize("old_status", [201, 503])
@pytest.mark.parametrize("new_needs_review", [False, True])
def test_review_response_cannot_change_another_run_form_or_pending_button(page, old_status, new_needs_review):
    first = create_review_run(page)
    page.locator("#reviewer").fill("旧申请审核员")
    page.locator("#review-status").select_option("evidence_requested")
    page.locator("#review-note").fill("旧申请跟进")
    page.locator("#review-references input").first.check()
    pending = []
    page.route("**/api/runs/*/review", lambda route: pending.append(route))
    page.locator("#review-submit").click()
    expect(page.locator("#review-submit")).to_be_disabled()
    second = create_review_run(page, requester_id="unknown_demo_person" if new_needs_review else "stu01")
    expect(page.locator("#notice")).to_contain_text("本次记录已保存")
    successor_notice = page.locator("#notice").text_content()
    expect(page.locator("#reviewer")).to_have_value("")
    expect(page.locator("#review-note")).to_have_value("")
    expect(page.locator("#review-status")).to_have_value("queued")
    expect(page.locator("#review-references input:checked")).to_have_count(0)
    expect(page.locator("#review-submit")).to_be_enabled()
    assert len(pending) == 1
    if new_needs_review:
        page.locator("#reviewer").fill("新申请审核员")
        page.locator("#review-note").fill("新申请跟进")
        page.locator("#review-references input").last.check()
        page.locator("#review-submit").click()
        expect(page.locator("#review-submit")).to_be_disabled()
    if old_status == 201:
        response = pending[0].fetch()
        assert response.status == 201
        pending[0].fulfill(response=response)
    else:
        pending[0].fulfill(status=503, json={"detail": "旧申请复核失败"})
    page.wait_for_function("runId => !pendingReviews.has(runId)", arg=first["run_id"])
    assert json.loads(page.locator("#decision-json").text_content())["run_id"] == second["run_id"]
    assert json.loads(page.locator("#decision-json").text_content())["review_records"] == []
    expect(page.locator("#review-history")).not_to_contain_text("旧申请审核员")
    expect(page.locator("#notice")).to_have_text(successor_notice)
    expect(page.locator("#notice")).to_have_attribute("role", "status")
    if new_needs_review:
        expect(page.locator("#review-submit")).to_be_disabled()
        expect(page.locator("#reviewer")).to_have_value("新申请审核员")
        expect(page.locator("#review-note")).to_have_value("新申请跟进")
        expect(page.locator("#review-references input:checked")).to_have_count(1)
        assert len(pending) == 2
        response = pending[1].fetch()
        assert response.status == 201
        pending[1].fulfill(response=response)
        expect(page.locator("#review-history")).to_contain_text("新申请审核员")
        expect(page.locator("#review-submit")).to_be_enabled()
    else:
        expect(page.locator("#review-panel")).to_be_hidden()
        expect(page.locator("#decision-action")).to_have_text("允许领用")
    saved = {run["id"]: run["result"] for run in page.request.get("/api/runs").json()}
    assert len(saved[first["run_id"]]["review_records"]) == (1 if old_status == 201 else 0)
    assert len(saved[second["run_id"]]["review_records"]) == (1 if new_needs_review else 0)


def test_review_unknown_preserves_draft_and_recovers_without_duplicate_write(page):
    first = create_review_run(page)
    page.locator("#reviewer").fill("重试审核员")
    page.locator("#review-note").fill("待重试记录")
    page.locator("#review-references input").first.check()
    requests = []

    def unavailable(route):
        requests.append(route.request.post_data_json)
        route.fulfill(status=503, json={"detail": "复核暂时不可用"})

    page.route("**/api/runs/*/review", unavailable)
    page.locator("#review-submit").click()
    expect(page.locator("#notice")).to_contain_text("复核暂时不可用")
    expect(page.locator("#notice")).to_contain_text("写入状态未确认")
    expect(page.locator("#review-submit")).to_be_disabled()
    expect(page.locator("#reviewer")).to_have_value("重试审核员")
    expect(page.locator("#review-note")).to_have_value("待重试记录")
    expect(page.locator("#review-references input:checked")).to_have_count(1)
    assert json.loads(page.locator("#decision-json").text_content())["review_records"] == []
    page.locator("#review-form").evaluate("form => form.requestSubmit()")
    assert len(requests) == 1, "unknown write was blindly repeated"
    page.get_by_role("button", name="查看复核保存状态").click()
    expect(page.locator("#notice")).to_contain_text("无法确认")
    expect(page.locator("#notice")).to_contain_text("needs_support")
    expect(page.locator("#review-submit")).to_be_disabled()
    expect(page.locator("#review-note")).to_have_value("待重试记录")
    expect(page.locator("#review-references input:checked")).to_have_count(1)
    page.locator("#review-form").evaluate("form => form.requestSubmit()")
    assert len(requests) == 1
    saved = next(run for run in page.request.get("/api/runs").json() if run["id"] == first["run_id"])
    assert saved["result"]["review_records"] == []
    page.unroute("**/api/runs/*/review")

    pending_lookup = []

    def delayed_lookup(route):
        if not pending_lookup:
            pending_lookup.append(route)
        else:
            route.continue_()

    page.route("**/api/runs", delayed_lookup)
    page.get_by_role("button", name="查看复核保存状态").click()
    assert len(pending_lookup) == 1
    lookup_response = pending_lookup[0].fetch()
    assert lookup_response.status == 200

    # A gateway failure may happen after the server commits. Recover the real
    # persisted record through the visible query action, without repeating POST.
    second = create_review_run(page)
    expect(page.locator("#notice")).to_contain_text("本次记录已保存")
    successor_notice = page.locator("#notice").text_content()
    pending_lookup[0].fulfill(response=lookup_response)
    page.wait_for_load_state("networkidle")
    expect(page.locator("#notice")).to_have_text(successor_notice)
    expect(page.locator("#notice")).to_have_attribute("role", "status")
    expect(page.locator("#review-submit")).to_be_enabled()
    expect(page.locator("#review-note")).to_have_value("")
    page.unroute("**/api/runs")
    page.locator("#reviewer").fill("恢复审核员")
    page.locator("#review-note").fill("已写入但确认响应丢失")
    page.locator("#review-references input").first.check()
    chosen = json.loads(page.locator("#review-references input").first.get_attribute("value"))

    def saved_without_acknowledgement(route):
        requests.append(route.request.post_data_json)
        response = route.fetch()
        assert response.status == 201
        route.fulfill(status=503, json={"detail": "保存确认暂时不可用"})

    page.route("**/api/runs/*/review", saved_without_acknowledgement)
    page.locator("#review-submit").click()
    expect(page.locator("#notice")).to_contain_text("保存确认暂时不可用")
    expect(page.locator("#review-submit")).to_be_disabled()
    expect(page.locator("#review-note")).to_have_value("已写入但确认响应丢失")
    expect(page.locator("#review-references input:checked")).to_have_count(1)
    page.locator("#review-note").fill("确认失败后另写的核对草稿")
    page.get_by_role("button", name="查看复核保存状态").click()
    expect(page.locator("#notice")).to_contain_text("已确认这条复核记录存在")
    expect(page.locator("#review-submit")).to_be_enabled()
    expect(page.locator("#review-history .list-card")).to_have_count(1)
    expect(page.locator("#review-history")).to_contain_text("恢复审核员")
    expect(page.locator("#review-note")).to_have_value("确认失败后另写的核对草稿")
    expect(page.locator("#review-references input:checked")).to_have_count(1)
    assert len(requests) == 2, "recovery repeated the write instead of finding it"
    saved = next(run for run in page.request.get("/api/runs").json() if run["id"] == second["run_id"])
    assert len(saved["result"]["review_records"]) == 1
    assert saved["result"]["review_records"][0]["evidence_references"] == [chosen]
    assert saved["result"]["review_records"][0]["note"] == "已写入但确认响应丢失"
    assert saved["result"]["decision"] is None


def test_reopening_pending_run_does_not_duplicate_saved_review_or_clear_new_draft(page):
    first = create_review_run(page)
    page.locator("#reviewer").fill("返回审核员")
    page.locator("#review-note").fill("已经保存的记录")
    pending = []
    page.route("**/api/runs/*/review", lambda route: pending.append(route))
    page.locator("#review-submit").click()
    create_review_run(page)
    assert len(pending) == 1
    response = pending[0].fetch()
    assert response.status == 201
    page.locator('[data-view="history"]').click()
    page.locator("#run-list .list-card", has=page.locator(f'a[href="/api/runs/{first["run_id"]}/export"]')).get_by_role("button", name="打开历史证据").click()
    expect(page.locator("#review-submit")).to_be_disabled()
    expect(page.locator("#review-history .list-card")).to_have_count(1)
    page.locator("#review-note").fill("返回后另写的草稿")
    pending[0].fulfill(response=response)
    expect(page.locator("#review-submit")).to_be_enabled()
    expect(page.locator("#review-history .list-card")).to_have_count(1)
    expect(page.locator("#review-note")).to_have_value("返回后另写的草稿")
    result = json.loads(page.locator("#decision-json").text_content())
    assert result["run_id"] == first["run_id"]
    assert len(result["review_records"]) == 1
