import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def checked_allow(page):
    page.locator('[data-view="check"]').click()
    page.locator('[data-preset="allow"]').click()
    page.locator("#as-of").fill("2026-09-28")
    with page.expect_response("**/api/check") as checked:
        page.get_by_role("button", name="核验并记录证据").click()
    assert checked.value.status == 200
    result = checked.value.json()
    expect(page.locator("#decision-action")).to_have_text("允许领用")
    expect(page.locator("#result-context")).to_have_attribute("data-context", "current")
    assert result["decision"]["approved_quantity"] == 100
    return result


def assert_draft_unapproved(page):
    expect(page.locator("#draft-status")).to_contain_text("尚未核验")
    expect(page.locator("#result-context")).to_have_attribute("data-context", "stale")
    expect(page.locator("#result-context-label")).to_contain_text("上次申请")


def acceptance_interactions(page, output):
    """Exercise result identity and interaction contracts, using real local runs."""
    page.set_viewport_size({"width": 1440, "height": 1050})
    observations = []
    before_presets = len(page.request.get(page.url.rstrip("/") + "/api/runs").json())
    for preset in ("allow", "conflict", "limit", "isolate", "missing"):
        page.locator('[data-preset="' + preset + '"]').click()
    assert len(page.request.get(page.url.rstrip("/") + "/api/runs").json()) == before_presets
    page.locator("#as-of").fill("2026-09-28")
    page.get_by_role("button", name="核验并记录证据").click()
    expect(page.locator("#decision-action")).to_have_text("需要人工复核")
    assert json.loads(page.locator("#decision-json").text_content())["decision"] is None
    expect(page.locator("#review-references input:checked")).to_have_count(0)
    observations.append("five presets only fill fields; missing person yields decision null and references default unchecked")
    for field, value in (("requester", "stu02"), ("lot", "lot_acid"),
                         ("cabinet", "cab_acid"), ("quantity", "101"),
                         ("as-of", "2026-09-29")):
        previous = checked_allow(page)
        control = page.locator("#" + field)
        # Read immediately after dispatch: stale safety semantics must not wait
        # for the visual transition or a second network response.
        snapshot = control.evaluate("""(input, value) => {
            input.value = value;
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            return {draft: document.querySelector('#draft-status').textContent,
                    context: document.querySelector('#result-context').dataset.context};
        }""", value)
        assert snapshot["context"] == "stale", (field, snapshot)
        assert "尚未核验" in snapshot["draft"], (field, snapshot)
        assert_draft_unapproved(page)
        assert json.loads(page.locator("#decision-json").text_content())["run_id"] == previous["run_id"]
    observations.append("requester/lot/cabinet/quantity/date edits invalidate ALLOW synchronously")

    checked_allow(page)
    pending = []
    page.route("**/api/check", lambda route: pending.append(route))
    page.get_by_role("button", name="核验并记录证据").click()
    expect(page.locator('#check-form button[type="submit"]')).to_be_disabled()
    page.locator("#check-form").evaluate("form => form.requestSubmit()")
    assert len(pending) == 1, "pending submit was duplicated"
    response = pending[0].fetch()
    assert response.status == 200
    delayed = response.json()
    page.locator('[data-preset="conflict"]').click()
    page.locator("#quantity").fill("123")
    pending[0].fulfill(response=response)
    page.wait_for_load_state("networkidle")
    assert_draft_unapproved(page)
    expect(page.locator("#requester")).to_have_value("stu03")
    expect(page.locator("#quantity")).to_have_value("123")
    assert json.loads(page.locator("#decision-json").text_content())["run_id"] != delayed["run_id"]
    page.unroute("**/api/check")
    page.get_by_role("button", name="核验并记录证据").click()
    expect(page.locator("#decision-action")).to_have_text("本次打回")
    expect(page.locator("#result-context")).to_have_attribute("data-context", "current")
    observations.append("pending submit prevents duplicates; late ALLOW never approves edited draft")

    previous = checked_allow(page)
    pending_version = []
    page.route("**/api/check", lambda route: pending_version.append(route))
    page.get_by_role("button", name="核验并记录证据").click()
    assert len(pending_version) == 1
    version_response = pending_version[0].fetch()
    assert version_response.status == 200
    page.locator('[data-view="versions"]').click()
    page.locator("#candidate-person").select_option("stu01")
    page.locator("#candidate-classes").select_option(["FLAMMABLE"])
    page.locator("#candidate-source").select_option(label="browser-synthetic-policy.md")
    page.locator("#candidate-locator").select_option("L2")
    page.locator("#candidate-note").fill("验证旧响应绑定原快照，仅合成浏览器测试")
    page.get_by_role("button", name="创建候选并预览").click()
    expect(page.get_by_role("button", name="发布演示版本")).to_be_visible()
    page.locator("#confirm-demo").check()
    page.get_by_role("button", name="发布演示版本").click()
    page.locator("#switch-confirm").click()
    expect(page.locator("#notice")).to_contain_text("演示版本已发布")
    page.locator('[data-view="check"]').click()
    pending_version[0].fulfill(response=version_response)
    page.wait_for_load_state("networkidle")
    assert_draft_unapproved(page)
    assert json.loads(page.locator("#decision-json").text_content())["run_id"] == previous["run_id"]
    expect(page.locator("#active-version")).not_to_have_text(previous["version_id"])
    page.unroute("**/api/check")
    observations.append("active version change invalidates current ALLOW and rejects old-version pending result")

    allow = checked_allow(page)
    page.locator("#quantity").fill("137")
    page.locator('[data-view="history"]').click()
    card = page.locator("#run-list .list-card", has=page.locator(f'a[href="/api/runs/{allow["run_id"]}/export"]'))
    card.get_by_role("button", name="打开历史证据").click()
    expect(page.locator("#result-context")).to_have_attribute("data-context", "history")
    expect(page.locator("#quantity")).to_have_value("137")
    expect(page.locator("#export-link")).to_have_attribute("href", f'/api/runs/{allow["run_id"]}/export')
    page.locator("#return-draft").click()
    expect(page.locator("#quantity")).to_have_value("137")
    assert_draft_unapproved(page)
    observations.append("history binds export to viewed run and preserves mutable draft on return")

    allow = checked_allow(page)
    links = page.locator("#evidence-chain .source-link")
    first = links.first
    first.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#source-dialog")).to_be_visible()
    expect(page.locator("#dialog-meta")).to_contain_text(allow["evidence"][0]["sha256"])
    expect(page.locator("#dialog-chunks")).to_contain_text(allow["evidence"][0]["quote"])
    expect(page.locator("#dialog-chunks .current-quote strong")).to_have_text(allow["evidence"][0]["locator"] + " · 当前引用")
    page.keyboard.press("Escape")
    expect(page.locator("#source-dialog")).not_to_be_visible()
    expect(first).to_be_focused()
    expect(page.locator('.relation-select[aria-pressed="true"]')).to_have_count(1)

    a = allow["evidence"][0]
    second_index = next(i for i, edge in enumerate(allow["evidence"]) if edge["source_id"] != a["source_id"])
    b = allow["evidence"][second_index]
    pending_sources = []
    page.route(f'**/api/documents/{a["source_id"]}', lambda route: pending_sources.append(route))
    first.click()
    # A mobile native modal blocks an outside pointer; dispatch a second actual
    # source control to exercise selection interruption independent of modality.
    links.nth(second_index).evaluate("button => button.click()")
    expect(page.locator("#dialog-meta")).to_contain_text(b["sha256"])
    expect(page.locator("#dialog-chunks")).to_contain_text(b["quote"])
    expect(page.locator("#dialog-chunks .current-quote strong")).to_have_text(b["locator"] + " · 当前引用")
    assert len(pending_sources) == 1
    response = pending_sources[0].fetch()
    assert response.status == 200
    pending_sources[0].fulfill(response=response)
    page.wait_for_load_state("networkidle")
    expect(page.locator("#dialog-meta")).to_contain_text(b["sha256"])
    expect(page.locator("#dialog-chunks")).to_contain_text(b["quote"])
    expect(page.locator("#dialog-chunks .current-quote strong")).to_have_text(b["locator"] + " · 当前引用")
    page.keyboard.press("Escape")
    expect(links.nth(second_index)).to_be_focused()
    page.unroute(f'**/api/documents/{a["source_id"]}')
    observations.append("keyboard source/Escape focus return and out-of-order source tuple stay correct")

    page.emulate_media(reduced_motion="reduce")
    first.click()
    expect(page.locator("#dialog-chunks")).to_contain_text(a["quote"])
    motion = page.locator("#source-dialog, #dialog-chunks, .relation-select").evaluate_all("""nodes => nodes.map(node => {
        const style = getComputedStyle(node);
        return {transform: style.transform, transition: style.transitionDuration,
                animation: style.animationDuration};
    })""")
    for style in motion:
        assert style["transform"] == "none", style
        assert all(float(value.strip().rstrip("s")) == 0 for value in style["transition"].split(",")), style
        assert all(float(value.strip().rstrip("s")) == 0 for value in style["animation"].split(",")), style
    page.keyboard.press("Escape")
    expect(first).to_be_focused()
    page.emulate_media(reduced_motion="no-preference")
    observations.append("reduced motion computed displacement/durations are zero; source and focus remain usable")

    page.locator('[data-view="sources"]').click()
    page.locator("#source-kind").select_option("synthetic")
    page.locator("#source-external").check()
    page.locator("#source-kind").select_option("private")
    expect(page.locator("#source-external")).not_to_be_checked()
    expect(page.locator("#source-external")).to_be_disabled()
    observations.append("private selection clears and disables external source permission")
    page.locator('[data-view="check"]').click()

    layout = []
    for width in (320, 390, 760, 1100, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        # ResizeObserver updates pane topology during the browser's layout frame.
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        if not page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"):
            offenders = page.evaluate("""() => [...document.querySelectorAll('body *')]
                .map(node => ({tag: node.tagName, id: node.id, cls: node.className,
                               right: Math.round(node.getBoundingClientRect().right),
                               left: Math.round(node.getBoundingClientRect().left),
                               width: Math.round(node.getBoundingClientRect().width)}))
                .filter(item => item.right > innerWidth + 1 || item.left < -1)
                .slice(0, 12)""")
            raise AssertionError({"width": width, "inner_width": page.evaluate("window.innerWidth"), "client_width": page.evaluate("document.documentElement.clientWidth"), "document_width": page.evaluate("document.documentElement.scrollWidth"), "body_width": page.evaluate("document.body.scrollWidth"), "offenders": offenders})
        if width in (320, 390):
            failures = page.evaluate("""() => [...document.querySelectorAll('button, input, select, textarea, summary, a')]
                .filter(node => node.getClientRects().length && !node.disabled)
                .map(node => {
                    const target = node.matches('input[type=checkbox], input[type=radio]') ? node.closest('label') : node;
                    const box = target.getBoundingClientRect();
                    return {name: node.id || node.textContent.trim().slice(0, 40), width: box.width, height: box.height};
                }).filter(box => box.width < 43.5 || box.height < 43.5)""")
            assert failures == [], {"width": width, "undersized_targets": failures}
            unlabeled = page.locator("#check-form input, #check-form select").evaluate_all("nodes => nodes.filter(node => !node.labels?.length && !node.getAttribute('aria-label')).map(node => node.id)")
            assert unlabeled == [], unlabeled
        page.screenshot(path=str(output / f"workbench-acceptance-{width}.png"), full_page=True)
        layout.append({"viewport_width": width, "whole_page_overflow": False})
    page.set_viewport_size({"width": 1440, "height": 1050})
    page.evaluate("document.documentElement.style.zoom = '2'")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    if not page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"):
        offenders = page.evaluate("""() => [...document.querySelectorAll('body *')]
            .map(node => ({tag:node.tagName,id:node.id,cls:node.className,right:Math.round(node.getBoundingClientRect().right),left:Math.round(node.getBoundingClientRect().left),width:Math.round(node.getBoundingClientRect().width)}))
            .filter(item => item.right > innerWidth + 1 || item.left < -1).slice(0,12)""")
        raise AssertionError({"zoom": "200% CSS", "document_width": page.evaluate("document.documentElement.scrollWidth"), "offenders": offenders})
    page.screenshot(path=str(output / "workbench-acceptance-css-zoom200.png"), full_page=True)
    page.evaluate("document.documentElement.style.zoom = ''")
    touch_context = page.context.browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    try:
        touch_page = touch_context.new_page()
        touch_page.goto(page.url, wait_until="networkidle")
        checked_allow(touch_page)
        touch_page.locator("#evidence-chain .source-link").first.tap()
        expect(touch_page.locator("#source-dialog")).to_be_visible()
        expect(touch_page.locator("#dialog-chunks")).to_contain_text(a["quote"])
        touch_page.get_by_role("button", name="关闭来源").tap()
        expect(touch_page.locator("#source-dialog")).not_to_be_visible()
        assert touch_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        touch_page.screenshot(path=str(output / "workbench-acceptance-touch390.png"), full_page=True)
    finally:
        touch_context.close()
    observations.append("320/390/760/1100/1440 layouts have no page overflow; 320/390 targets and form labels verified")
    report = {"observed_at": datetime.now(timezone.utc).isoformat(),
              "scope": "isolated synthetic browser interaction; no live model calls; simulated viewports, not real device or screen-reader validation",
              "observations": observations, "layout": layout, "reduced_motion": motion,
              "touch_emulation": {"width": 390, "source_open_close": True},
              "css_zoom_200_percent": {"whole_page_overflow": False, "browser_ui_zoom_verified": False}}
    root = Path(__file__).resolve().parents[1]
    report["static_sha256"] = {name: hashlib.sha256((root / "src" / "ontolens" / "static" / name).read_bytes()).hexdigest()
                               for name in ("index.html", "app.js", "style.css")}
    (output / "workbench-interaction-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    args = parser.parse_args()
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")
        status = page.request.get(args.url + "/api/status").json()
        assert not status["model_configured"] and not status["jev"]["key_present"], "browser smoke requires provider-free isolated service"
        expect(page.locator("#active-version")).to_have_text("demo-initial")
        for preset, expected in (("allow", "允许领用"), ("conflict", "本次打回"), ("limit", "限量领用"), ("isolate", "隔离批次")):
            page.locator('[data-preset="' + preset + '"]').click()
            page.get_by_role("button", name="核验并记录证据").click()
            expect(page.locator("#decision-action")).to_have_text(expected)
            expect(page.locator(".evidence-node")).to_have_count(6)
        page.locator('[data-preset="allow"]').click()
        page.get_by_role("button", name="核验并记录证据").click()
        expect(page.locator("#decision-action")).to_have_text("允许领用")
        original_decision = page.locator("#decision-json").text_content()
        page.locator("#citation-claim").fill("合成记录显示 stu01 具有 FLAMMABLE 类别授权。")
        page.get_by_role("button", name="核对这条解释的引用").click()
        expect(page.locator("#citation-result")).to_contain_text("引用字面匹配通过")
        expect(page.locator("#citation-result")).to_contain_text("JEV unavailable")
        expect(page.locator("#citation-result")).to_contain_text("不证明陈述语义正确")
        expect(page.locator("#decision-json")).to_have_text(original_decision)
        page.locator(".source-link").first.click()
        expect(page.get_by_role("dialog")).to_be_visible()
        expect(page.locator("#dialog-chunks")).to_contain_text("FLAMMABLE")
        page.get_by_role("button", name="关闭来源").click()
        with page.expect_download() as download:
            page.locator("#export-link").click()
        assert download.value.suggested_filename.endswith(".json")
        page.screenshot(path=str(output / "workbench-desktop.png"), full_page=True)

        page.locator('[data-view="sources"]').click()
        page.locator("#source-file").set_input_files({
            "name": "browser-synthetic-policy.md", "mimeType": "text/plain",
            "buffer": "# 浏览器合成演示\nstu01 授权仅保留 ACID，生效: 2026-10-01\n".encode(),
        })
        page.get_by_role("button", name="导入并保留来源").click()
        expect(page.locator("#notice")).to_contain_text("已导入 browser-synthetic-policy.md")
        page.locator("#search-input").fill("仅保留")
        page.get_by_role("button", name="检索", exact=True).click()
        expect(page.locator("#source-list")).to_contain_text("stu01 授权仅保留 ACID")
        page.get_by_role("button", name="识别资产").first.click()
        expect(page.get_by_role("dialog")).to_contain_text("资产识别")
        expect(page.locator("#dialog-chunks")).to_contain_text("待审核关系")
        expect(page.locator("#dialog-chunks")).to_contain_text("本体 schema 候选")
        page.get_by_role("button", name="关闭来源").click()
        page.get_by_role("button", name="JEV 重排").click()
        expect(page.locator("#jev-status")).to_contain_text("JEV unavailable")

        page.locator('[data-view="sources"]').click()
        page.locator("#source-file").set_input_files("data/demo/synthetic-asset-label.png")
        page.locator("#transcript").fill("批次 ID：lot_eth\n资产类别：FLAMMABLE\n来源：演示图片\n人工摘录，未使用 OCR。")
        page.get_by_role("button", name="导入并保留来源").click()
        expect(page.locator("#notice")).to_contain_text("已导入 synthetic-asset-label.png")
        image_card = page.locator("#source-list .list-card").filter(has_text="synthetic-asset-label.png")
        expect(image_card).to_contain_text("仅本地处理")
        image_card.get_by_role("button", name="识别资产").click()
        expect(page.get_by_role("dialog")).to_contain_text("lot_eth")
        expect(page.get_by_role("dialog")).to_contain_text("FLAMMABLE")
        page.get_by_role("button", name="关闭来源").click()

        page.locator('[data-view="versions"]').click()
        page.locator("#candidate-person").select_option("stu01")
        page.locator("#candidate-classes").select_option(["ACID"])
        page.locator("#candidate-source").select_option(label="browser-synthetic-policy.md")
        # Source chunks load asynchronously; the disabled state is an intentional
        # guard against submitting a locator from the previous source.
        expect(page.locator("#candidate-locator")).to_be_enabled(timeout=10000)
        page.locator("#candidate-locator").select_option("L2")
        page.locator("#candidate-note").fill("浏览器端到端演示，不是专业审核")
        page.get_by_role("button", name="创建候选并预览").click()
        expect(page.locator("#impact-result")).to_contain_text("CLASS_NOT_AUTHORIZED")
        page.get_by_role("button", name="发布演示版本").click()
        expect(page.locator("#notice")).to_contain_text("请先核对来源与影响")
        page.locator("#confirm-demo").check()
        page.get_by_role("button", name="发布演示版本").click()
        page.locator("#switch-confirm").click()
        expect(page.locator("#notice")).to_contain_text("演示版本已发布")
        page.locator('[data-view="check"]').click()
        expect(page.locator("#view-check")).to_be_visible()
        editor = page.locator("#request-editor")
        if not editor.is_visible():
            page.locator("#toggle-request").click()
        expect(editor).to_be_visible()
        page.locator('[data-preset="allow"]').click()
        page.get_by_role("button", name="核验并记录证据").click()
        expect(page.locator("#decision-action")).to_have_text("本次打回")

        page.locator('[data-view="versions"]').click()
        page.locator("#confirm-demo").check()
        page.get_by_role("button", name="回滚到此版本").click()
        page.locator("#switch-confirm").click()
        expect(page.locator("#notice")).to_contain_text("已回滚")
        page.locator('[data-view="check"]').click()
        page.get_by_role("button", name="核验并记录证据").click()
        expect(page.locator("#decision-action")).to_have_text("允许领用")

        page.locator('[data-view="evaluation"]').click()
        expect(page.locator("#evaluation-content")).to_contain_text("60 / 60")
        page.locator('[data-view="history"]').click()
        expect(page.locator("#run-list .list-card")).to_have_count(7)
        page.locator('[data-view="setup"]').click()
        expect(page.locator("#view-setup")).to_contain_text("尚未实现")
        expect(page.locator("#model-status")).to_contain_text("未配置")

        page.set_viewport_size({"width": 390, "height": 844})
        page.locator('[data-view="check"]').click()
        page.screenshot(path=str(output / "workbench-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        acceptance_interactions(page, output)
        assert not errors, errors
        browser.close()
    print("Browser smoke: PASS — decisions, evidence, export, upload, search, publish, rollback, metrics; draft/history/source identity, reduced motion, responsive touch targets; no page errors")


if __name__ == "__main__":
    main()
