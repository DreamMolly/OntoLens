"use strict";

const byId = (id) => document.getElementById(id);
const state = { token: "", status: null, catalog: null, active: null, sources: [], lastRun: null, lastResult: null, locatorRequest: 0, candidateSource: null };
const names = { ALLOW: "允许领用", DENY: "本次打回", LIMIT: "限量领用", ISOLATE: "隔离批次" };
const classNames = { FLAMMABLE: "易燃", OXIDIZER: "氧化剂", ACID: "酸", BASE: "碱", WATER_REACTIVE: "遇水反应", TOXIC: "有毒", COMPRESSED_GAS: "压缩气体", GENERAL: "一般" };
const personNames = { tea01: "教师 · tea01", stu01: "学生 · stu01", stu02: "学生 · stu02", stu03: "学生 · stu03", ban01: "停权人员 · ban01" };
const authState = { enabled: false, actor: null, booted: false };
const pendingNexent = new Map();
const nexentResults = new Map();
let nexentStatus = null;
const pendingReviews = new Set();
const pendingModels = new Map();
const modelResults = new Map();
const ui = { view: "check", revision: 0, sequence: 0, requestPending: false, current: null, inspected: null, context: "draft", sourceSequence: 0, sourceTrigger: null, sourceSelection: null, checkUnknown: null, reviewDrafts: new Map(), reviewUnknown: new Map(), historyScroll: 0 };
const sourceKinds = { synthetic: "合成资料", public: "公开资料", private: "私有资料" };

function element(tag, text, className) {
  const item = document.createElement(tag);
  if (text !== undefined && text !== null) item.textContent = text;
  if (className) item.className = className;
  return item;
}

function message(text, error = false) {
  const notice = byId("notice");
  notice.textContent = text;
  notice.className = "notice" + (error ? " error" : "");
  notice.setAttribute("role", error ? "alert" : "status");
  notice.hidden = false;
}

async function api(path, options = {}) {
  const capability = options.method === "POST" ? capabilityForPath(path) : null;
  if (capability && !can(capability)) throw new Error("当前账户没有执行此操作的权限。");
  let response;
  try { response = await fetch("/api" + path, { ...options, headers: { "X-OntoLens-Token": state.token, ...(options.headers || {}) } }); }
  catch (cause) { const error = new Error("连接中断，请查看保存状态后再决定是否重试。"); error.uncertain = options.method === "POST"; throw error; }
  if (response.status === 401) { showLogin("会话未登录或已失效，请登录后继续。"); throw new Error("需要登录业务工作区。"); }
  let payload;
  try { payload = await response.json(); }
  catch (cause) { const error = new Error("服务返回内容未能读取，请刷新保存状态。"); error.uncertain = options.method === "POST"; throw error; }
  if (!response.ok) {
    const detail = Array.isArray(payload.detail) ? payload.detail.map((item) => item.msg).join("；") : payload.detail;
    const error = new Error(detail || "请求失败，请检查输入后重试");
    error.httpStatus = response.status; error.uncertain = options.method === "POST" && response.status >= 500; throw error;
  }
  return payload;
}

const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

async function perform(button, operation) {
  if (button?.dataset.busy === "true") return;
  const originalLabel = button?.textContent;
  if (button) { button.disabled = true; button.dataset.busy = "true"; button.setAttribute("aria-busy", "true"); if (!button.matches(".nav-item")) button.textContent = "处理中…"; }
  try { await operation(); } catch (error) { message(error.message, true); }
  finally {
    if (button) {
      if (!button.matches(".nav-item")) button.textContent = originalLabel;
      button.removeAttribute("aria-busy");
      delete button.dataset.busy;
      if (button.id === "candidate-submit") updateCandidateSubmission();
      else button.disabled = false;
      applyRolePermissions();
    }
  }
}

function action(label, handler, className = "secondary") {
  const button = element("button", label, className);
  button.type = "button";
  button.addEventListener("click", () => perform(button, handler));
  return button;
}

function options(select, entries) {
  const previous = select.value;
  select.replaceChildren();
  for (const [value, title] of entries) {
    const option = element("option", title);
    option.value = value;
    select.append(option);
  }
  if (entries.some(([value]) => value === previous)) select.value = previous;
  syncEnhancedSelect(select);
}

async function refreshStatus() {
  state.status = await api("/status");
  state.token = state.status.csrf_token;
  state.mode = state.status.mode || "synthetic_demo";
  if (state.status.actor) authState.actor = state.status.actor;
  setActiveVersion(state.status.active_id);
  byId("active-version").textContent = state.active;
  byId("app-version").textContent = state.status.version ? "v" + state.status.version : "本地演示版";
  byId("connection-state").replaceChildren(element("span", null, "live-dot"), document.createTextNode("本地服务已连接"));
  byId("mcp-address").textContent = location.origin + state.status.mcp_path;
  byId("model-status").textContent = state.status.model_configured ? "已填写配置，尚需实际调用验证" : "未配置 · 离线功能可用";
  byId("jev-config-status").textContent = !state.status.jev.key_present ? "未配置密钥 · 普通检索可用" : !state.status.jev.sdk_installed ? "尚未安装 JEV SDK · 普通检索可用" : "配置齐全 · 尚未验证在线效果";
  byId("explain-button").disabled = !state.status.model_configured;
  byId("model-availability").textContent = state.status.model_configured ? "模型已配置；点击后发送本条合成证据，解释不改变程序决定。" : "模型未配置，核验、原文回查和导出仍可用。";
  byId("explain-button").title = state.status.model_configured ? "将本条合成演示证据发送给已配置模型" : "在服务环境变量中配置模型后启用";
  renderModelState();
  updateWorkspaceMode();
  renderActor();
}

async function refreshCatalog() {
  const data = await api("/catalog");
  state.catalog = data.catalog;
  if (data.mode) state.mode = data.mode;
  const people = Object.entries(state.catalog.people || {}).map(([name, person]) => [name, isSyntheticMode() ? (personNames[name] || name) : person.name ? person.name + " · " + name : name]);
  options(byId("requester"), people);
  options(byId("candidate-person"), people);
  options(byId("lot"), Object.entries(state.catalog.lots || {}).map(([key, value]) => [key, key + " · " + value.chemical_id]));
  options(byId("cabinet"), Object.entries(state.catalog.cabinets || {}).map(([key, value]) => [key, key + " · " + (value.allowed_classes || []).map((item) => classNames[item] || item).join("、")]));
  options(byId("candidate-classes"), state.status.classes.map((value) => [value, classNames[value] + " / " + value]));
  fillCandidateClasses();
  updateUnit();
  updateWorkspaceMode();
  applyRolePermissions();
}

function updateUnit() {
  const lot = state.catalog?.lots?.[byId("lot").value];
  byId("unit").value = lot ? state.catalog?.chemicals?.[lot.chemical_id]?.unit || "" : "";
}

function fillCandidateClasses() {
  const current = state.catalog?.people?.[byId("candidate-person").value]?.classes || [];
  for (const option of byId("candidate-classes").options) option.selected = current.includes(option.value);
  renderClassChoices();
}

function preset(mode) {
  if (!isSyntheticMode()) return;
  for (const button of document.querySelectorAll("[data-preset]")) {
    const selected = button.dataset.preset === mode;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  }
  const requester = byId("requester");
  for (const option of requester.querySelectorAll("option[data-demo-missing]")) option.remove();
  const missing = mode === "missing";
  if (missing) {
    const option = element("option", "未登记合成人员 · unknown_demo_person（资料缺失演示）");
    option.value = "unknown_demo_person";
    option.dataset.demoMissing = "true";
    requester.append(option);
  }
  requester.value = missing ? "unknown_demo_person" : mode === "conflict" ? "stu03" : "stu01";
  byId("missing-demo-note").hidden = !missing;
  byId("lot").value = mode === "isolate" ? "lot_eth_exp" : "lot_eth";
  byId("cabinet").value = "cab_flam";
  byId("quantity").value = mode === "limit" ? "300" : "100";
  updateUnit();
  syncAllEnhancedSelects();
  markDraftDirty();
}

function updateExternalSourcePermission() {
  const checkbox = byId("source-external");
  const privateSource = byId("source-kind").value === "private";
  checkbox.disabled = privateSource;
  if (privateSource) checkbox.checked = false;
  syncEnhancedSelect(byId("source-kind"));
}

async function showSource(sourceId, locator, edge = null, trigger = document.activeElement) {
  const sequence = ++ui.sourceSequence;
  ui.sourceTrigger = trigger; ui.sourceSelection = { sourceId, locator, edge, runId: state.lastRun, version: state.lastResult?.version_id };
  const dialog = byId("source-dialog");
  byId("dialog-title").textContent = edge?.title || "读取来源";
  byId("dialog-meta").textContent = "来源 " + sourceId + " · 定位 " + (locator || "全部片段");
  byId("dialog-relation").hidden = !edge;
  byId("dialog-relation").textContent = edge ? edge.relation + " · 快照 " + state.lastResult.version_id : "";
  byId("dialog-status").textContent = "正在读取原始资料…";
  byId("dialog-image").hidden = true; byId("dialog-chunks").replaceChildren();
  dialog.setAttribute("aria-busy", "true"); openSourceDialog(Boolean(edge));
  try {
    const source = await api("/documents/" + encodeURIComponent(sourceId));
    if (sequence !== ui.sourceSequence || ui.sourceSelection?.sourceId !== sourceId || ui.sourceSelection?.locator !== locator) return;
    if (edge && (state.lastRun !== ui.sourceSelection.runId || edge.sha256 !== source.sha256)) throw new Error("来源与本次引用的哈希或记录身份不匹配，暂不展示为支持证据。");
    byId("dialog-title").textContent = source.title;
    byId("dialog-meta").textContent = (sourceKinds[source.kind] || source.kind) + " · SHA256 " + source.sha256 + (edge ? " · 快照 " + ui.sourceSelection.version : "");
    const image = byId("dialog-image"); image.hidden = !source.media_type.startsWith("image/");
    if (!image.hidden) image.src = "/api/documents/" + encodeURIComponent(sourceId) + "/file";
    const chunks = byId("dialog-chunks");
    const sorted = [...source.chunks].sort((left, right) => Number(right.locator === locator) - Number(left.locator === locator));
    const found = sorted.some(chunk => chunk.locator === locator);
    byId("dialog-status").textContent = locator && !found ? "未找到本次定位，原文待补件。下方为来源中其他片段。" : "原始资料，仅供回查；不代表专业核验。";
    if (!sorted.length) chunks.append(element("p", "此文件没有可读取文本；请补充人工摘录。", "field-note"));
    for (const chunk of sorted) {
      const card = element("div", null, "list-card" + (chunk.locator === locator ? " current-quote" : ""));
      card.append(element("strong", chunk.locator + (chunk.locator === locator ? " · 当前引用" : "")), element("pre", chunk.text)); chunks.append(card);
    }
  } catch (error) {
    if (sequence !== ui.sourceSequence) return;
    byId("dialog-status").textContent = error.message;
    byId("dialog-chunks").append(action("重新读取来源", () => showSource(sourceId, locator, edge, trigger)));
  } finally { if (sequence === ui.sourceSequence) dialog.removeAttribute("aria-busy"); }
}

async function showAssets(sourceId) {
  closeSource(false);
  ui.sourceTrigger = document.activeElement;
  const sequence = ++ui.sourceSequence;
  const result = await api("/documents/" + encodeURIComponent(sourceId) + "/assets");
  if (sequence !== ui.sourceSequence) return;
  byId("dialog-relation").hidden = true; byId("dialog-status").textContent = "";
  byId("dialog-title").textContent = result.source_title + " · 资产识别";
  byId("dialog-meta").textContent = result.notice;
  byId("dialog-image").hidden = true;
  const chunks = byId("dialog-chunks");
  chunks.replaceChildren();
  const schema = element("div", null, "list-card");
  schema.append(element("h3", "本体草案 · " + result.schema.version), element("p", result.schema.alignment.notice, "field-note"));
  chunks.append(schema);
  const entities = element("div", null, "list-card");
  entities.append(element("h3", "已识别资产 · " + result.entities.length + " 项"));
  if (!result.entities.length) entities.append(element("p", "没有匹配到当前目录内的已知资产。", "field-note"));
  for (const item of result.entities) entities.append(element("p", item.type + " · " + item.id + " · " + item.locator + " · " + item.method, "field-note"));
  chunks.append(entities);
  const relations = element("div", null, "list-card");
  relations.append(element("h3", "待审核关系 · " + result.relations.length + " 项"));
  if (!result.relations.length) relations.append(element("p", "没有可提出的关系候选。", "field-note"));
  for (const item of result.relations) relations.append(element("p", item.subject + " — " + item.type + " → " + item.object + " · " + item.status + " · " + item.locator, "field-note"));
  chunks.append(relations);
  const schemaCandidates = element("div", null, "list-card");
  schemaCandidates.append(element("h3", "本体 schema 候选 · " + result.schema_candidates.length + " 项"));
  if (!result.schema_candidates.length) schemaCandidates.append(element("p", "当前片段没有识别到可扩展的关系属性。", "field-note"));
  for (const item of result.schema_candidates) schemaCandidates.append(element("p", item.relation + " + " + item.properties.join("、") + " · " + item.status + " · " + item.locator, "field-note"));
  chunks.append(schemaCandidates);
  byId("source-dialog").showModal();
}

function renderDecision(result, context = "current", request = null, binding = null) {
  saveReviewDraft();
  closeSource(false);
  ui.context = context; ui.inspected = { result, request, binding };
  if (state.lastRun !== result.run_id) byId("notice").hidden = true;
  state.lastRun = result.run_id;
  state.lastResult = result;
  byId("citation-result").hidden = true;
  byId("citation-claim").value = "";
  byId("empty-result").hidden = true;
  byId("decision-content").hidden = false;
  byId("result-version").textContent = result.version_id;
  const decision = result.decision;
  const actionName = decision ? decision.action : "needs_review";
  byId("decision-banner").className = "decision-banner" + (["DENY", "ISOLATE"].includes(actionName) ? " danger" : ["LIMIT", "needs_review"].includes(actionName) ? " warning" : "");
  byId("decision-label").textContent = decision ? decision.reason_code : result.status;
  byId("decision-action").textContent = decision ? names[actionName] : "需要人工复核";
  byId("approved-quantity").textContent = decision && decision.approved_quantity !== null ? decision.approved_quantity + " " + result.unit : "—";
  byId("decision-message").textContent = result.message;
  byId("approved-quantity").parentElement.querySelector("small").textContent = result.mode === "imported_workspace" ? "本次已发布规则允许数量" : "本次合成规则允许数量";
  renderReviewPanel(result);
  const chain = byId("evidence-chain");
  chain.replaceChildren();
  byId("evidence-count").textContent = result.evidence.length + " 条关系 · 点击来源回查";
  for (const [index, edge] of result.evidence.entries()) {
    const unresolved = edge.unresolved || !edge.quote;
    const node = element("div", null, "evidence-node" + (unresolved ? " unresolved" : ""));
    node.setAttribute("role", "listitem");
    const label = action(edge.relation, () => selectRelation(index, label), "relation-select");
    label.setAttribute("aria-pressed", "false"); label.setAttribute("aria-label", edge.relation + "，查看对应来源");
    node.append(label, element("div", edge.subject + " → " + edge.target, "edge-value"));
    node.append(element("p", unresolved ? "原文缺失，等待补件核对。" : edge.quote, "edge-quote"));
    node.append(action(edge.title + " · " + edge.locator, () => selectRelation(index, node.querySelector(".source-link")), "source-link"));
    chain.append(node);
  }
  byId("export-link").href = "/api/runs/" + encodeURIComponent(result.run_id) + "/export";
  byId("decision-json").textContent = JSON.stringify(result, null, 2);
  byId("model-output").hidden = true;
  restoreReviewDraft();
  renderModelState();
  renderNexentState();
  syncResultContext();
}

function renderReviewPanel(result) {
  const panel = byId("review-panel");
  if (!panel) return;
  if (panel.dataset.runId !== result.run_id) {
    panel.dataset.runId = result.run_id;
    byId("review-form").reset();
    renderReviewReferences(result);
  }
  updateReviewSubmission();
  const review = result.status === "needs_review" ? result.review : null;
  panel.hidden = !review;
  const history = byId("review-history");
  history.replaceChildren();
  if (!review) return;
  if (ui.reviewUnknown.has(result.run_id)) history.append(action("查看复核保存状态", () => recoverReview(result.run_id)));
  const fields = review.blocking_fields && review.blocking_fields.length ? review.blocking_fields.join("、") : "待核对字段";
  const evidence = review.requested_evidence && review.requested_evidence.length ? review.requested_evidence.join("；") : "请补充可定位来源";
  byId("review-guidance").textContent = "原因 " + review.reason_code + " · 阻塞字段：" + fields + "。补件建议：" + evidence + "。" + review.next_step + "。系统保持 needs_review，不会由人工记录生成业务决定。";
  for (const record of result.review_records || []) {
    const card = element("div", null, "list-card");
    card.append(element("p", new Date(record.created_at).toLocaleString() + " · " + record.reviewer + " · " + record.review_status + " · " + record.note, "field-note"));
    const references = record.evidence_references || [];
    if (!references.length) card.append(element("p", (record.evidence_ids || []).length ? "本条仅保存来源编号：" + record.evidence_ids.join("、") + "；未记录逐引用定位。" : "本条未选择来源引用。", "field-note"));
    for (const reference of references) {
      card.append(element("p", reference.source_id + " · " + reference.locator + " · " + (reference.unresolved ? "缺失原文 · 待补件" : "已定位原文") + " · SHA256 " + reference.sha256, "field-note"));
      if (reference.quote !== null && reference.quote !== undefined) card.append(element("blockquote", reference.quote));
    }
    history.append(card);
  }
}

function renderReviewReferences(result) {
  const choices = byId("review-references");
  choices.replaceChildren();
  const seen = new Set();
  for (const edge of result.evidence || []) {
    const key = JSON.stringify([edge.source_id, edge.locator, edge.sha256]);
    if (seen.has(key)) continue;
    seen.add(key);
    const unresolved = edge.unresolved === true || edge.quote === null || edge.quote === undefined;
    const complete = [edge.source_id, edge.locator, edge.sha256].every((value) => typeof value === "string" && value.length);
    const card = element("div", null, "review-reference");
    const label = element("label", null, "review-reference-choice");
    const checkbox = element("input");
    checkbox.type = "checkbox";
    checkbox.value = JSON.stringify({ source_id: edge.source_id, locator: edge.locator, sha256: edge.sha256, quote: edge.quote ?? null, unresolved });
    checkbox.disabled = !complete;
    label.append(checkbox, element("span", (edge.title || edge.source_id) + " · " + (edge.locator || "定位缺失") + " · " + (!complete ? "定位不完整 · 无法选择" : unresolved ? "缺失原文 · 待补件" : "已定位原文")));
    card.append(label, element("p", edge.source_id + " · SHA256 " + (edge.sha256 || "缺失"), "field-note"));
    if (!unresolved) card.append(element("blockquote", edge.quote));
    if (edge.source_id && edge.locator) card.append(action("查看此引用原文", () => showSource(edge.source_id, edge.locator)));
    choices.append(card);
  }
  if (!seen.size) choices.append(element("p", "当前记录没有可选择的来源引用，可直接记录补件要求。", "field-note"));
}

function updateReviewSubmission() {
  const pending = pendingReviews.has(state.lastRun);
  byId("review-submit").disabled = pending || ui.reviewUnknown.has(state.lastRun) || !can("review");
  byId("review-submit").setAttribute("aria-busy", String(pending));
  byId("review-submit").textContent = pending ? "正在追加复核记录…" : "追加人工复核记录";
}

function appendReviewRecord(result, record) {
  const records = result.review_records || [];
  if (!records.some((item) => record.id ? item.id === record.id : JSON.stringify(item) === JSON.stringify(record))) {
    result.review_records = [...records, record];
  }
}

async function submitReview() {
  const inspected = state.lastResult;
  if (!inspected || inspected.status !== "needs_review") {
    message("只有 needs_review 记录可以追加人工复核", true);
    return;
  }
  const runId = inspected.run_id;
  if (pendingReviews.has(runId) || ui.reviewUnknown.has(runId)) return;
  const note = byId("review-note").value;
  const selected = [...byId("review-references").querySelectorAll("input:checked:not(:disabled)")];
  const body = {
    reviewer: byId("reviewer").value, review_status: byId("review-status").value, note,
    evidence_references: selected.map((input) => JSON.parse(input.value)),
  };
  const previousIds = new Set((inspected.review_records || []).map(item => item.id));
  pendingReviews.add(runId);
  updateReviewSubmission();
  try {
    const record = await post("/runs/" + encodeURIComponent(runId) + "/review", body);
    appendReviewRecord(inspected, record);
    clearSubmittedReviewDraft(runId, body);
    if (state.lastRun !== runId) return;
    if (state.lastResult !== inspected) appendReviewRecord(state.lastResult, record);
    renderReviewPanel(state.lastResult);
    byId("decision-json").textContent = JSON.stringify(state.lastResult, null, 2);
    saveReviewDraft();
    byId("review-history").lastElementChild?.classList.add("review-saved");
    message("已追加人工复核记录；原始 needs_review 与业务决定保持不变。");
  } catch (error) {
    if (error.uncertain) {
      ui.reviewUnknown.set(runId, { body, previousIds, inspected, reason: error.message });
      if (state.lastRun === runId) {
        message(error.message + "。复核写入状态未确认，草稿已保留。先查看保存状态，不能直接重复追加。", true);
        const recovery = action("查看复核保存状态", () => recoverReview(runId));
        byId("review-history").prepend(recovery);
      }
    } else if (state.lastRun === runId) message(error.message, true);
  } finally {
    pendingReviews.delete(runId);
    if (state.lastRun === runId) updateReviewSubmission();
  }
}

async function reviewCitations() {
  const inspected = state.lastResult;
  const query = byId("citation-claim").value.trim();
  if (!inspected || !query) throw new Error("先核验申请，再填写需要复核的事实性陈述");
  if (inspected.evidence.some((edge) => typeof edge.quote !== "string" || !edge.quote.trim())) {
    throw new Error("当前记录有缺失原文，先人工复核来源，不能跳过坏引用");
  }
  const citations = inspected.evidence.map((edge) => ({
    source_id: edge.source_id, locator: edge.locator, quote: edge.quote, sha256: edge.sha256,
  }));
  const result = await post("/evidence/jev", { query, version_id: inspected.version_id, limit: citations.length, citations });
  if (state.lastResult !== inspected) return;
  const target = byId("citation-result");
  target.hidden = false;
  target.replaceChildren(
    element("h3", result.citation_check.status === "passed" ? "引用字面匹配通过" : "引用字面匹配失败"),
    element("p", "JEV " + result.status + " · " + result.reason, "field-note"),
    element("p", "这里只核对原文与定位，不证明陈述语义正确。网页不会请求在线 JEV，程序决定未改变。", "field-note"),
  );
  for (const reference of result.citation_check.references) {
    target.append(element("p", reference.locator + " · " + reference.code, "field-note"));
  }
}

byId("citation-form").addEventListener("submit", (event) => {
  event.preventDefault();
  perform(event.submitter, reviewCitations);
});

async function refreshSources(query = "") {
  state.sources = await api("/documents");
  byId("source-count").textContent = state.sources.length + " 份来源";
  updateSourceOverview(state.sources);
  const list = byId("source-list");
  list.replaceChildren();
  const entries = query ? await api("/evidence?query=" + encodeURIComponent(query)) : state.sources;
  byId("jev-status").textContent = "普通检索覆盖资料库；JEV 只重排当前已发布合成快照内的片段，尚未调用。";
  if (!entries.length) list.append(element("p", "没有找到匹配片段，可以换编号或关键词。", "field-note"));
  for (const source of entries) {
    const card = element("div", null, "list-card source-card " + source.kind);
    const external = source.external_model_allowed ? "可选模型外发已允许" : "仅本地处理";
    const head = element("div", null, "source-card-head");
    const fileType = (source.media_type || "document").split("/").pop().replace("plain", "TXT").toUpperCase();
    head.append(element("span", fileType.slice(0, 4), "source-file-icon"), element("h3", source.title), element("span", sourceKinds[source.kind] || source.kind, "source-type " + source.kind));
    const meta = element("div", null, "source-meta");
    meta.append(element("span", source.media_type), element("span", "SHA256 · " + source.sha256.slice(0, 12)));
    card.append(head, meta, element("p", external, "source-permission"));
    if (source.text) card.append(element("p", source.locator + " · " + source.text.slice(0, 160), "field-note"));
    card.append(action("查看原文", () => showSource(source.id, source.locator)));
    card.append(action("识别资产", () => showAssets(source.id)));
    list.append(card);
  }
  options(byId("candidate-source"), state.sources.filter((source) => source.kind === "synthetic").map((source) => [source.id, source.title]));
  await loadCandidateLocators();
}

async function refreshJev(query = "") {
  if (!query.trim()) throw new Error("先输入要查找的证据问题");
  byId("jev-status").textContent = "正在重排当前快照证据…";
  const result = await api("/evidence/jev", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, limit: 12, live: true }) });
  const scope = "快照 " + result.version_id + "；未发布的上传资料不在重排范围。";
  byId("jev-status").textContent = result.status === "ready" ? "JEV 已完成重排，只显示支持关系概率，不代表专业审核。" + scope : "JEV " + result.status + "：" + result.reason + "。" + scope;
  const list = byId("source-list");
  list.replaceChildren();
  if (!result.candidates.length) list.append(element("p", "当前快照中没有匹配片段；可用普通检索查找上传资料。", "field-note"));
  for (const source of result.candidates || []) {
    const card = element("div", null, "list-card");
    const score = source.jev_probability === undefined ? "普通检索" : "支持关系概率 " + source.jev_probability.toFixed(3) + " · " + (source.jev_review_priority === "high" ? "高优先级复核" : "常规复核");
    card.append(element("h3", source.title), element("p", score + " · " + source.kind + " · " + source.locator, "field-note"), element("p", source.text || source.quote || "", "field-note"));
    card.append(action("查看原文", () => showSource(source.id, source.locator)));
    card.append(action("识别资产", () => showAssets(source.id)));
    list.append(card);
  }
}

function updateCandidateSubmission() {
  const button = byId("candidate-submit");
  button.disabled = !can("import") || !isSyntheticMode() || button.dataset.busy === "true" || state.candidateSource !== byId("candidate-source").value || !byId("candidate-locator").value;
}

async function loadCandidateLocators() {
  const request = ++state.locatorRequest;
  const sourceId = byId("candidate-source").value;
  const locator = byId("candidate-locator");
  const status = byId("candidate-source-status");
  state.candidateSource = null;
  locator.disabled = true;
  options(locator, [["", sourceId ? "正在读取所选来源…" : "请选择合成来源"]]);
  status.textContent = sourceId ? "正在读取所选来源，请稍候。" : "导入合成资料后可选择来源片段。";
  updateCandidateSubmission();
  if (!sourceId) return;
  try {
    const source = await api("/documents/" + encodeURIComponent(sourceId));
    if (request !== state.locatorRequest || sourceId !== byId("candidate-source").value) return;
    const chunks = source.chunks.filter((chunk) => chunk.text.trim());
    options(locator, chunks.map((chunk) => [chunk.locator, chunk.locator + " · " + chunk.text.slice(0, 50)]));
    state.candidateSource = sourceId;
    locator.disabled = !chunks.length;
    status.textContent = chunks.length ? "片段来自：" + source.title : "这份来源没有可用文本片段；请补充摘录或选择其他来源。";
  } catch (error) {
    if (request !== state.locatorRequest || sourceId !== byId("candidate-source").value) return;
    options(locator, [["", "来源读取失败"]]);
    status.textContent = "来源读取失败，请重新选择来源后重试。";
    throw error;
  } finally {
    if (request === state.locatorRequest) updateCandidateSubmission();
  }
}

function confirmed() {
  if (!byId("confirm-demo").checked) throw new Error("请先核对来源与影响，并勾选版本变更确认。");
}

async function previewCandidate(candidateId) {
  const report = await api("/candidates/" + encodeURIComponent(candidateId) + "/preview");
  const target = byId("impact-result");
  target.hidden = false;
  target.replaceChildren(element("h3", "影响预览 · " + report.changes.length + " 条已记录申请变化"), element("p", report.compared_scope, "field-note"), element("p", report.semantic_review, "field-note"));
  const parent = element("p", "父版本快照：" + report.parent_id, "field-note"); parent.id = "impact-parent-version";
  const candidate = element("p", "候选编号：" + report.candidate_id, "field-note"); candidate.id = "impact-candidate-id";
  target.insertBefore(parent, target.children[1]); target.insertBefore(candidate, parent.nextSibling);
  if (!report.changes.length) target.append(element("p", "尚无受影响记录。可先在父版本核验目标人员的申请，再查看候选。", "field-note"));
  for (const change of report.changes) {
    const card = element("article", null, "change-card");
    card.append(element("h3", change.request_id));
    const comparison = element("div", null, "change-comparison");
    for (const [key, label] of [["before", "变更之前"], ["after", "候选生效后"]]) {
      const raw = change[key];
      const value = raw && typeof raw === "object" ? (raw.decision || raw) : raw;
      const side = element("div", null, "change-side " + key);
      side.append(element("small", label));
      if (value && typeof value === "object") {
        side.append(element("strong", names[value.action] || value.action || value.status || "待复核"));
        if (value.approved_quantity !== undefined) side.append(element("p", "批准数量：" + (value.approved_quantity ?? "—")));
        if (value.reason_code) side.append(element("p", value.reason_code));
      } else side.append(element("strong", String(value ?? "—")));
      comparison.append(side);
    }
    const detail = element("details");
    detail.append(element("summary", "查看完整变更字段"), element("pre", JSON.stringify({ before: change.before, after: change.after }, null, 2)));
    card.append(comparison, detail);
    target.append(card);
  }
}

async function refreshVersions() {
  const data = await api("/versions");
  setActiveVersion(data.active_id);
  byId("active-version").textContent = state.active;
  const candidates = byId("candidate-list");
  candidates.replaceChildren();
  if (!data.candidates.length) candidates.append(element("p", isSyntheticMode() ? "还没有候选。可选择合成来源提出授权变更，或导入业务台账包。" : "还没有候选。请先导入六份获授权的业务台账。", "field-note"));
  const businessCandidates = data.candidates.some(item => item.patch?.type === "ledger_bundle");
  byId("confirm-demo").parentElement.lastChild.textContent = businessCandidates || !isSyntheticMode() ? "我已核对来源与影响，确认本次资料版本变更；不代表专业批准。" : "我确认这里只改变合成演示，不是专家批准";
  for (const candidate of data.candidates) {
    const card = element("div", null, "list-card");
    const ledger = candidate.patch.type === "ledger_bundle";
    const candidateTitle = ledger ? candidate.patch.label : candidate.patch.requester_id;
    const candidateNote = ledger ? "六类原始台账候选 · 本地操作者 " + candidate.patch.operator + " · 未自动发布" : candidate.patch.note;
    card.append(element("h3", candidateTitle + " · " + candidate.status), element("p", candidateNote, "field-note"));
    card.append(action("预览影响", () => previewCandidate(candidate.id)));
    if (candidate.status === "proposed") card.append(action(ledger ? "发布业务资料版本" : "发布演示版本", async () => {
      confirmed();
      if (!await confirmSwitch(ledger ? "发布业务资料版本" : "发布演示版本", candidate.id, ledger || !isSyntheticMode())) return;
      await switchWrite("/candidates/" + candidate.id + "/publish", { expected_active: state.active, note: ledger ? "发布业务台账：" + candidate.patch.label : candidate.patch.note, ...(ledger || !isSyntheticMode() ? { confirm_publish: true } : { confirm_demo: true }) });
      byId("confirm-demo").checked = false;
      await Promise.all([refreshVersions(), refreshCatalog()]);
      message(ledger ? "业务资料版本已发布；请依据实际来源重新核验。发布不等于专业批准，旧记录保留原快照。" : "演示版本已发布。专业审核人仍为空；旧记录保持原快照。");
    }));
    candidates.append(card);
  }
  const versions = byId("version-list");
  versions.replaceChildren();
  for (const version of data.versions) {
    const card = element("div", null, "list-card");
    card.append(element("h3", version.label + (version.id === state.active ? " · 当前" : "")), element("p", version.id, "muted"), element("p", "SHA256 " + version.sha256.slice(0, 20), "field-note"));
    if (version.id !== state.active) card.append(action("回滚到此版本", async () => {
      confirmed();
      const business = version.mode ? version.mode !== "synthetic_demo" : !isSyntheticMode() || version.id === "operational-initial";
      if (!await confirmSwitch("回滚到此版本", version.id, business)) return;
      await switchWrite("/versions/" + version.id + "/rollback", { expected_active: state.active, note: business ? "操作者确认回滚到指定资料快照" : "操作者在合成空间进行回滚演示", ...(business ? { confirm_publish: true } : { confirm_demo: true }) });
      byId("confirm-demo").checked = false;
      await Promise.all([refreshVersions(), refreshCatalog()]);
      message("已回滚；历史记录与候选仍保留。");
    }));
    versions.append(card);
  }
  for (const button of [...candidates.querySelectorAll("button"), ...versions.querySelectorAll("button")]) { if (["发布演示版本", "发布业务资料版本", "回滚到此版本"].includes(button.textContent)) { button.dataset.capability = "publish"; } }
  applyRolePermissions();
}

async function refreshEvaluation() {
  const report = await api("/evaluation");
  const content = byId("evaluation-content");
  content.replaceChildren(element("p", report.label, "field-note"));
  const metrics = element("div", null, "metric-grid");
  for (const version of ["v1", "v2"]) {
    const card = element("div", null, "metric");
    card.append(
      element("span", version + " · 决定与预期一致"),
      element("strong", report[version].exact_match + " / " + report[version].total),
      element("small", "不安全放行 " + report[version].unsafe_release + " 条 · 超量批准 " + report[version].over_issue + " 条 · 误拒绝 " + report[version].over_block + " 条 · 合成样本"),
    );
    metrics.append(card);
  }
  content.append(metrics);
  for (const name of ["v2_gate", "v3_gate"]) {
    const detail = element("details");
    detail.append(element("summary", report[name].candidate + " 候选门禁：" + (report[name].accepted ? "通过" : "拒绝（预期）")), element("pre", JSON.stringify(report[name], null, 2)));
    content.append(detail);
  }
  content.append(element("p", "此基准没有验证上传资料的语义、本体算法或真实行业有效性。", "field-note"));
}

async function refreshHistory() {
  const runs = await api("/runs");
  updateRunOverview(runs);
  const list = byId("run-list");
  list.replaceChildren();
  if (!runs.length) list.append(element("p", "还没有核验记录。先到申请页运行一条申请。", "field-note"));
  for (const run of runs) {
    const card = element("div", null, "list-card");
    card.append(element("h3", run.request.request_id + " · " + (run.result.decision ? names[run.result.decision.action] : "待复核")), element("p", run.request.requester_id + " / " + run.version_id + " / " + new Date(run.created_at).toLocaleString(), "field-note"));
    card.append(action("打开历史证据", async () => { ui.historyScroll = window.scrollY; await switchView("check"); renderDecision(run.result, "history", run.request); }));
    const download = element("a", "导出", "secondary");
    download.href = "/api/runs/" + run.id + "/export";
    card.append(download);
    list.append(card);
  }
  byId("audit-log").textContent = JSON.stringify(await api("/audit"), null, 2);
}

async function switchView(name) {
  closeEnhancedSelect(false, true);
  saveReviewDraft();
  closeSource(false);
  ui.view = name;
  for (const section of document.querySelectorAll(".view")) section.hidden = section.id !== "view-" + name;
  for (const button of document.querySelectorAll(".nav-item")) {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    if (active) { button.setAttribute("aria-current", "page"); byId("breadcrumb").textContent = button.querySelector(".nav-label").textContent; }
    else button.removeAttribute("aria-current");
  }
  document.querySelector(".skip-link").href = "#view-" + name;
  byId("view-" + name).tabIndex = -1;
  if (name === "check") { await refreshOverview(); syncResultContext(); }
  if (name === "sources") await refreshSources();
  if (name === "versions") { await refreshSources(); await refreshVersions(); }
  if (name === "evaluation") await refreshEvaluation();
  if (name === "history") await refreshHistory();
  if (name === "setup") { await refreshStatus(); await refreshNexentStatus(); }
}

for (const button of document.querySelectorAll(".nav-item")) button.addEventListener("click", () => perform(button, () => switchView(button.dataset.view)));
for (const button of document.querySelectorAll("[data-preset]")) button.addEventListener("click", () => preset(button.dataset.preset));
byId("lot").addEventListener("change", updateUnit);
byId("candidate-person").addEventListener("change", fillCandidateClasses);
byId("candidate-source").addEventListener("change", () => perform(null, loadCandidateLocators));
byId("source-kind").addEventListener("change", updateExternalSourcePermission);
byId("close-dialog").addEventListener("click", () => closeSource());
byId("check-form").addEventListener("submit", (event) => { event.preventDefault(); submitCheck(event.submitter); });
byId("review-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submitReview();
});
byId("upload-form").addEventListener("submit", (event) => {
  event.preventDefault();
  perform(event.submitter, async () => {
    const file = byId("source-file").files[0];
    if (!file || file.size > 4 * 1024 * 1024) throw new Error("请选择不超过 4 MiB 的来源文件");
    const form = new FormData();
    form.append("file", file); form.append("kind", byId("source-kind").value); form.append("transcript", byId("transcript").value); form.append("allow_external_model", byId("source-external").checked ? "true" : "false");
    form.append("ocr", byId("source-ocr").checked ? "true" : "false");
    const result = await api("/documents", { method: "POST", body: form });
    await refreshSources();
    message("已导入 " + result.title + "。" + result.notice);
    byId("upload-form").reset();
    updateExternalSourcePermission();
  });
});
byId("search-form").addEventListener("submit", (event) => { event.preventDefault(); perform(event.submitter, () => refreshSources(byId("search-input").value)); });
byId("jev-search-button").addEventListener("click", (event) => perform(event.currentTarget, () => refreshJev(byId("search-input").value)));
byId("candidate-form").addEventListener("submit", (event) => {
  event.preventDefault();
  perform(event.submitter, async () => {
    if (byId("valid-from").value && byId("valid-until").value && byId("valid-from").value > byId("valid-until").value) throw new Error("生效日期不能晚于有效至日期。");
    if (state.candidateSource !== byId("candidate-source").value || byId("candidate-locator").disabled || !byId("candidate-locator").value) {
      throw new Error("所选来源片段尚未准备好，请等待读取完成后创建候选");
    }
    const candidate = await post("/candidates", { parent_id: state.active, requester_id: byId("candidate-person").value, classes: [...byId("candidate-classes").selectedOptions].map((option) => option.value), source_id: byId("candidate-source").value, locator: byId("candidate-locator").value, valid_from: byId("valid-from").value || null, valid_until: byId("valid-until").value || null, note: byId("candidate-note").value });
    await refreshVersions();
    await previewCandidate(candidate.id);
    message("候选已保存，尚未发布。");
  });
});
byId("evaluate-button").addEventListener("click", (event) => perform(event.currentTarget, refreshEvaluation));
byId("explain-button").addEventListener("click", requestExplanation);

function updateSourceOverview(sources) {
  byId("overview-sources").textContent = sources.length;
  byId("overview-sources").nextElementSibling.textContent = "已保存的原始文件";
  byId("overview-public").nextElementSibling.textContent = "与合成来源分别标记";
  byId("overview-public").textContent = sources.filter((source) => source.kind === "public").length;
}

function updateRunOverview(runs) {
  byId("overview-runs").textContent = runs.length;
  byId("overview-runs").nextElementSibling.textContent = "最近 50 条内的保存记录";
  byId("overview-review").nextElementSibling.textContent = "近期记录中的 needs_review";
  byId("overview-review").textContent = runs.filter((run) => run.result.status === "needs_review").length;
}

async function refreshOverview() {
  const results = await Promise.allSettled([api("/documents"), api("/runs")]);
  if (results[0].status === "fulfilled") updateSourceOverview(results[0].value);
  else { byId("overview-sources").textContent = "—"; byId("overview-public").textContent = "—"; byId("overview-sources").nextElementSibling.textContent = byId("overview-public").nextElementSibling.textContent = "读取失败，未取得数量"; }
  if (results[1].status === "fulfilled") updateRunOverview(results[1].value);
  else { byId("overview-runs").textContent = "—"; byId("overview-review").textContent = "—"; byId("overview-runs").nextElementSibling.textContent = byId("overview-review").nextElementSibling.textContent = "读取失败，未取得数量"; }
}

perform(null, bootWorkspace);

// D1.0: draft, inspected record and asynchronous operations have separate identities.
function requestFields() {
  return { requester_id: byId("requester").value, lot_id: byId("lot").value, destination_cabinet_id: byId("cabinet").value, quantity: Number(byId("quantity").value), unit: byId("unit").value, as_of: byId("as-of").value, version_id: state.active };
}
function fingerprint(value = requestFields()) { return JSON.stringify(value); }
function requestSummary(request) {
  if (!request) return "此记录的完整申请与来源保留在导出中。";
  return [request.requester_id, request.lot_id, request.destination_cabinet_id, request.quantity + " " + request.unit, request.as_of].join(" / ");
}
function setActiveVersion(version) {
  const changed = state.active && state.active !== version;
  state.active = version;
  if (changed) markDraftDirty();
}
function markDraftDirty() {
  ui.revision++;
  byId("draft-status").dataset.state = ui.requestPending ? "pending" : "dirty";
  byId("draft-status").textContent = ui.requestPending ? "申请已修改；正在保存的是提交时的旧输入。新草稿尚未核验。" : "当前草稿尚未核验。";
  if (ui.context === "current") ui.context = "stale";
  byId("request-summary").textContent = requestSummary(requestFields());
  syncResultContext();
}
function syncResultContext() {
  const inspected = ui.inspected;
  if (inspected && ui.context === "current" && inspected.binding && (inspected.binding.fingerprint !== fingerprint() || inspected.binding.version !== state.active)) ui.context = "stale";
  byId("result-panel").dataset.context = ui.context;
  const box = byId("result-context"); box.hidden = !inspected; box.dataset.context = ui.context;
  if (!inspected) return;
  byId("result-context-label").textContent = ui.context === "history" ? "历史记录 · 不代表当前草稿" : ui.context === "stale" ? "上次申请的结果 · 当前草稿尚未核验" : "本次核验记录";
  byId("result-request-summary").textContent = requestSummary(inspected.request) + " · 快照 " + inspected.result.version_id;
  byId("return-draft").hidden = ui.context !== "history";
  byId("return-history").hidden = ui.context !== "history";
  if (ui.context === "current" && !ui.requestPending) { byId("draft-status").textContent = "当前输入与本次核验一致。"; byId("draft-status").dataset.state = "ready"; }
}
function validateCheck(focusError = true) {
  let first = null;
  for (const field of byId("check-form").querySelectorAll("input:not(.date-text):not(.date-year),select:not(.date-month)")) {
    const id = field.id + "-error"; byId(id)?.remove(); field.removeAttribute("aria-invalid"); field.removeAttribute("aria-describedby"); window.OntoLensDates?.clear?.(field);
    let error = "";
    if (!field.validity.valid) error = field.validity.valueMissing ? "请填写此项。" : "请按字段要求填写有效值。";
    if (field.id === "quantity" && (!Number.isFinite(Number(field.value)) || Number(field.value) <= 0 || Number(field.value) > 1e9)) error = "数量须为大于 0 且不超过 1000000000 的有限数值。";
    if (error) { const text = element("p", error, "field-error"); text.id = id; const anchor = window.OntoLensDates?.errorTarget?.(field) || enhancedSelects.get(field)?.button || field; anchor.after(text); field.setAttribute("aria-invalid", "true"); field.setAttribute("aria-describedby", id); window.OntoLensDates?.describe?.(field, id); first ||= field; }
  }
  if (first && focusError) { if (!window.OntoLensDates?.focus?.(first)) first.focus(); }
  return !first;
}
async function submitCheck(button) {
  if (ui.requestPending || ui.checkUnknown || !can("check")) return;
  if (!validateCheck()) return;
  if (!catalogReady()) { message("目录仍在读取，请稍后再核验。", true); return; }
  const payload = { request_id: "WEB-" + Date.now(), ...requestFields() };
  const binding = { revision: ui.revision, sequence: ++ui.sequence, version: state.active, fingerprint: fingerprint() };
  ui.requestPending = true; byId("check-pending").hidden = false; byId("check-form").setAttribute("aria-busy", "true");
  byId("draft-status").dataset.state = "pending"; byId("draft-status").textContent = "正在核验并保存提交时的申请…";
  await perform(button, async () => {
    try {
      const result = await post("/check", payload);
      if (!result.run_id || result.version_id !== binding.version) throw new Error("返回记录身份与提交快照不一致，请从运行记录核对。");
      const same = binding.revision === ui.revision && binding.sequence === ui.sequence && binding.version === state.active && binding.fingerprint === fingerprint();
      const saved = { result, request: payload, binding };
      ui.current = saved;
      if (same && ui.context !== "history") {
        renderDecision(result, "current", payload, binding);
        message((result.decision ? names[result.decision.action] + "，数量 " + (result.decision.approved_quantity ?? "—") + " " + result.unit : "需要人工复核，请查看缺件要求") + "。本次记录已保存。");
      } else message("提交时的申请已保存为历史记录；当前草稿已变化或正在查看历史，未覆盖当前内容。");
      await refreshOverview();
    } catch (error) {
      if (error.uncertain) {
        ui.checkUnknown = { payload, binding };
        byId("check-recovery").hidden = false; byId("check-recovery-text").textContent = "写入状态未确认。当前草稿保留；先按申请编号查看近期保存记录，避免重复核验。";
        byId("draft-status").dataset.state = "unknown";
      }
      message(error.message, true);
    } finally {
      ui.requestPending = false; byId("check-pending").hidden = true; byId("check-form").removeAttribute("aria-busy");
      if (ui.checkUnknown) { byId("draft-status").textContent = "保存状态未确认，请查看保存状态。"; }
      else { byId("draft-status").dataset.state = "dirty"; byId("draft-status").textContent = "当前草稿尚未核验。"; syncResultContext(); }
    }
  });
  if (ui.checkUnknown) button.disabled = true;
}
async function recoverCheck() {
  if (!ui.checkUnknown) return;
  const unknown = ui.checkUnknown;
  const runs = await api("/runs");
  const saved = runs.find(run => run.request.request_id === unknown.payload.request_id);
  if (!saved) { byId("check-recovery-text").textContent = "近期记录中未找到这次申请，仍无法排除已保存（needs_support）。请检查服务与完整记录；当前不自动重试。"; return; }
  ui.checkUnknown = null; byId("check-recovery").hidden = true; byId("check-form").querySelector("button[type=submit]").disabled = false;
  ui.current = { result: saved.result, request: saved.request, binding: unknown.binding };
  if (unknown.binding.fingerprint === fingerprint() && ui.context !== "history") renderDecision(saved.result, "current", saved.request, unknown.binding);
  message("已在运行记录中找到这次保存，未重复提交。");
}
function saveReviewDraft() {
  if (!state.lastRun || !byId("review-form")) return;
  ui.reviewDrafts.set(state.lastRun, { reviewer: byId("reviewer").value, status: byId("review-status").value, note: byId("review-note").value, selected: [...byId("review-references").querySelectorAll("input:checked")].map(input => input.value) });
}
function restoreReviewDraft() {
  const draft = ui.reviewDrafts.get(state.lastRun); if (!draft) return;
  byId("reviewer").value = draft.reviewer; byId("review-status").value = draft.status; byId("review-note").value = draft.note;
  for (const input of byId("review-references").querySelectorAll("input")) input.checked = draft.selected.includes(input.value);
  syncEnhancedSelect(byId("review-status"));
}
function referenceIdentity(references) {
  return JSON.stringify(references.map(reference => [reference.source_id, reference.locator, reference.sha256, reference.quote ?? null, reference.unresolved === true]).sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))));
}
function reviewDraftMatches(draft, body) {
  if (!draft || draft.reviewer !== body.reviewer || draft.status !== body.review_status || draft.note !== body.note) return false;
  return referenceIdentity(draft.selected.map(value => JSON.parse(value))) === referenceIdentity(body.evidence_references);
}
function clearSubmittedReviewDraft(runId, body) {
  if (state.lastRun === runId) saveReviewDraft();
  const draft = ui.reviewDrafts.get(runId);
  if (!reviewDraftMatches(draft, body)) return;
  ui.reviewDrafts.set(runId, { ...draft, note: "", selected: [] });
  if (state.lastRun === runId) {
    byId("review-note").value = "";
    for (const input of byId("review-references").querySelectorAll("input")) input.checked = false;
  }
}
async function recoverReview(runId) {
  const unknown = ui.reviewUnknown.get(runId); if (!unknown) return;
  try {
    const runs = await api("/runs");
    if (ui.reviewUnknown.get(runId) !== unknown) return;
    const run = runs.find(item => item.id === runId);
    const record = run?.result.review_records?.find(item => !unknown.previousIds.has(item.id) && item.reviewer === unknown.body.reviewer && item.note === unknown.body.note && item.review_status === unknown.body.review_status && referenceIdentity(item.evidence_references || []) === referenceIdentity(unknown.body.evidence_references));
    if (!record) {
      if (state.lastRun === runId && ui.view === "check") message(unknown.reason + "。近期记录无法确认这次复核是否已保存（needs_support）；保留草稿，不自动重复追加。", true);
      return;
    }
    ui.reviewUnknown.delete(runId); appendReviewRecord(unknown.inspected, record);
    clearSubmittedReviewDraft(runId, unknown.body);
    if (state.lastRun === runId) {
      appendReviewRecord(state.lastResult, record); renderReviewPanel(state.lastResult); updateReviewSubmission();
      byId("decision-json").textContent = JSON.stringify(state.lastResult, null, 2);
      if (ui.view === "check") message("已确认这条复核记录存在，未重复追加。与提交完全一致的草稿已清理；之后修改的内容保留。");
    }
  } catch (error) {
    if (ui.reviewUnknown.get(runId) === unknown && state.lastRun === runId && ui.view === "check") message(unknown.reason + "。保存状态查询失败：" + error.message + "；写入仍未确认，草稿保留。", true);
  }
}
function renderModelState() {
  const button = byId("explain-button");
  const runId = state.lastRun;
  const pending = pendingModels.has(runId);
  const result = modelResults.get(runId);
  const modelScope = state.lastResult?.mode === "imported_workspace" ? "仅发送去标识的决定摘要，不发送私有原文、身份、数量或定位。" : "点击后发送本条合成证据，解释不改变程序决定。";
  button.disabled = !state.status?.model_configured || pending || !can("model");
  button.textContent = pending ? "正在请求辅助解释…" : "模型辅助解释";
  button.setAttribute("aria-busy", String(pending));
  byId("model-output").hidden = !result?.response;
  if (result?.response) byId("model-output").textContent = result.response.notice + "\n\n" + result.response.text;
  byId("model-availability").textContent = pending ? "正在请求这条记录的辅助解释，程序决定不变…" : result?.error ? "解释请求失败：" + result.error + "。可重试，程序决定与证据保留。" : result?.response ? "已收到这条记录的模型响应；它不改变程序决定。" : !can("model") ? "当前角色只能读取，不能调用辅助模型。" : state.status?.model_configured ? "模型已配置；" + modelScope : "模型未配置，核验、原文回查和导出仍可用。";
}
async function requestExplanation() {
  const inspected = state.lastResult;
  if (!inspected || !state.status?.model_configured || pendingModels.has(inspected.run_id)) return;
  const runId = inspected.run_id;
  const operation = { version: inspected.version_id };
  pendingModels.set(runId, operation); modelResults.delete(runId); renderModelState();
  try {
    const response = await post("/runs/" + encodeURIComponent(runId) + "/explain", {});
    if (pendingModels.get(runId) === operation) modelResults.set(runId, { response });
  } catch (error) {
    if (pendingModels.get(runId) === operation) modelResults.set(runId, { error: error.message });
    if (state.lastRun === runId && state.lastResult?.version_id === operation.version && ui.view === "check") message(error.message, true);
  } finally {
    if (pendingModels.get(runId) === operation) pendingModels.delete(runId);
    if (state.lastRun === runId && state.lastResult?.version_id === operation.version) renderModelState();
  }
}

function selectRelation(index, trigger) {
  const edge = state.lastResult?.evidence[index]; if (!edge) return;
  for (const [i, node] of [...byId("evidence-chain").children].entries()) { node.dataset.selected = String(i === index); node.querySelector(".relation-select").setAttribute("aria-pressed", String(i === index)); }
  return showSource(edge.source_id, edge.locator, edge, trigger);
}
function openSourceDialog(dock, moveFocus = true) {
  const dialog = byId("source-dialog");
  const previousFocus = document.activeElement;
  const useDock = dock && ui.view === "check" && sourceInspectorDockAllowed();
  if (useDock && workspaceSizing.width < 1240 && !byId("request-editor").contains(previousFocus)) setRequestFold(true);
  if (dialog.open) dialog.close();
  dialog.classList.toggle("inspector-docked", useDock);
  byId("check-workspace").classList.toggle("inspecting", useDock);
  if (useDock) { byId("check-workspace").append(dialog); dialog.show(); }
  else { document.body.append(dialog); dialog.showModal(); }
  dialog.classList.remove("inspector-enter");
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches) dialog.classList.add("inspector-enter");
  if (moveFocus) byId("close-dialog").focus({ preventScroll: true });
  else if (previousFocus?.isConnected && previousFocus.getClientRects().length) previousFocus.focus({ preventScroll: true });
}
function closeSource(restore = true) {
  if (selectUI.owner?.button.closest("#source-dialog")) closeEnhancedSelect(false, true);
  const dialog = byId("source-dialog");
  ++ui.sourceSequence; ui.sourceSelection = null;
  if (dialog.open) dialog.close();
  dialog.classList.remove("inspector-docked", "inspector-enter"); byId("check-workspace").classList.remove("inspecting");
  document.body.append(dialog);
  if (restore) {
    const target = ui.sourceTrigger;
    if (target?.isConnected && target.getClientRects().length) target.focus({ preventScroll: true });
    else { const heading = byId("view-" + ui.view)?.querySelector("h1"); if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); } }
  }
}
function renderClassChoices() {
  const container = byId("candidate-class-choices"); container.replaceChildren();
  for (const option of byId("candidate-classes").options) {
    const label = element("label"); const checkbox = element("input"); checkbox.type = "checkbox"; checkbox.value = option.value; checkbox.checked = option.selected;
    checkbox.addEventListener("change", () => { option.selected = checkbox.checked; }); label.append(checkbox, document.createTextNode(classNames[option.value] || option.value)); container.append(label);
  }
}
async function confirmSwitch(label, target, business = false) {
  const dialog = byId("switch-dialog"); byId("switch-title").textContent = label;
  byId("switch-description").textContent = "当前快照：" + state.active + "。目标：" + target + (business ? "。这会改变当前生效的业务资料快照；不代表专业批准或真实出库许可，旧记录仍保留原快照。" : "。这里只改变合成演示；不是专业批准，旧记录仍保留原快照。");
  byId("switch-confirm").textContent = "确认" + label;
  return new Promise(resolve => {
    const finish = value => { dialog.close(); byId("switch-confirm").onclick = null; byId("switch-cancel").onclick = null; dialog.oncancel = null; resolve(value); };
    byId("switch-confirm").onclick = () => finish(true); byId("switch-cancel").onclick = () => finish(false); dialog.oncancel = event => { event.preventDefault(); finish(false); }; dialog.showModal(); byId("switch-cancel").focus();
  });
}
let unknownSwitch = false;
async function switchWrite(path, body) {
  if (unknownSwitch) throw new Error("之前的版本写入仍未确认，请先查看版本与操作日志（needs_support），不能重复提交。");
  try { return await post(path, body); }
  catch (error) {
    if (error.uncertain) {
      unknownSwitch = true;
      const checks = await Promise.allSettled([api("/versions"), api("/audit")]);
      if (checks[0].status === "fulfilled") setActiveVersion(checks[0].value.active_id);
      if (checks[1].status === "fulfilled") byId("audit-log").textContent = JSON.stringify(checks[1].value, null, 2);
      throw new Error("版本写入状态未确认，已尝试读取版本与操作日志。请核对当前快照；在无法排除已生效前不重复提交（needs_support）。");
    }
    throw error;
  }
}
byId("check-form").addEventListener("input", markDraftDirty);
byId("check-form").addEventListener("change", markDraftDirty);
byId("check-form").addEventListener("focusout", event => {
  if (event.relatedTarget?.closest("#check-form button[type=submit]")) return;
  if (event.target.matches("input,select") && event.target.getAttribute("aria-invalid") === "true") validateCheck(false);
});
byId("review-form").addEventListener("input", saveReviewDraft);
byId("review-form").addEventListener("change", saveReviewDraft);
byId("candidate-classes").addEventListener("change", renderClassChoices);
byId("toggle-request").addEventListener("click", () => {
  const closed = !byId("request-editor").hidden;
  byId("request-editor").hidden = closed; byId("request-summary").hidden = !closed;
  byId("request-summary").textContent = requestSummary(requestFields()); byId("toggle-request").textContent = closed ? "修改申请" : "收起申请"; byId("toggle-request").setAttribute("aria-expanded", String(!closed));
});
byId("return-draft").addEventListener("click", () => {
  saveReviewDraft(); closeSource(false);
  if (ui.current) renderDecision(ui.current.result, "current", ui.current.request, ui.current.binding);
  else { state.lastRun = null; state.lastResult = null; ui.inspected = null; ui.context = "draft"; byId("decision-content").hidden = true; byId("empty-result").hidden = false; syncResultContext(); }
});
byId("return-history").addEventListener("click", () => perform(null, async () => { await switchView("history"); window.scrollTo(0, ui.historyScroll); }));
byId("check-recovery-button").addEventListener("click", event => perform(event.currentTarget, recoverCheck));
byId("source-dialog").addEventListener("cancel", event => { event.preventDefault(); closeSource(); });
document.addEventListener("keydown", event => { if (event.key === "Escape" && byId("source-dialog").open) { event.preventDefault(); closeSource(); } });
window.addEventListener("resize", updateWorkspaceLayout);
window.addEventListener("beforeunload", event => { if (ui.loggingOut) return; saveReviewDraft(); if ([...ui.reviewDrafts.values()].some(draft => draft.note.trim()) || byId("candidate-note").value.trim()) { event.preventDefault(); event.returnValue = ""; } });
for (const field of document.querySelectorAll("input,textarea,select")) { if (!field.name) field.name = field.id || "reference"; if (field.type !== "file") field.autocomplete = "off"; }
byId("quantity").inputMode = "decimal";

// D1.1 local layout preference. No request, source, note or credential is persisted.
const sidebarPreferenceKey = "ontolens.layout.v1";
const sidebarLayout = { width: 240, collapsed: false, drag: null, frame: 0, nextWidth: 240, keyboardStart: null };
const workspaceSizing = { width: 0, mode: "single" };
function clampSidebarWidth(value) { return Math.min(360, Math.max(208, Math.round(value))); }
function saveSidebarPreference() {
  try { localStorage.setItem(sidebarPreferenceKey, JSON.stringify({ width: sidebarLayout.width, collapsed: sidebarLayout.collapsed })); } catch (_) { /* Layout remains usable when storage is unavailable. */ }
}
function renderSidebarLayout() {
  document.documentElement.style.setProperty("--sidebar-width", (sidebarLayout.collapsed ? 72 : sidebarLayout.width) + "px");
  document.documentElement.classList.toggle("sidebar-collapsed", sidebarLayout.collapsed);
  const toggle = byId("sidebar-toggle");
  toggle.setAttribute("aria-expanded", String(!sidebarLayout.collapsed));
  toggle.setAttribute("aria-label", sidebarLayout.collapsed ? "展开导航" : "折叠导航");
  toggle.title = sidebarLayout.collapsed ? "展开导航" : "折叠导航";
  const handle = byId("sidebar-resizer");
  handle.setAttribute("aria-valuenow", String(sidebarLayout.width));
  handle.setAttribute("aria-valuetext", sidebarLayout.width + " 像素");

  byId("sidebar-tooltip").hidden = true;
}
function setRequestFold(closed) {
  byId("request-editor").hidden = closed;
  byId("request-summary").hidden = !closed;
  byId("request-summary").textContent = requestSummary(requestFields());
  byId("toggle-request").textContent = closed ? "修改申请" : "收起申请";
  byId("toggle-request").setAttribute("aria-expanded", String(!closed));
}
function sourceInspectorDockAllowed() { return innerWidth > 760 && workspaceSizing.width >= 860; }
function updateWorkspaceLayout(entryWidth) {
  const main = byId("main-workspace");
  const width = typeof entryWidth === "number" ? entryWidth : main.clientWidth - parseFloat(getComputedStyle(main).paddingLeft) - parseFloat(getComputedStyle(main).paddingRight);
  const mode = width >= 1240 ? "wide" : width >= 820 ? "double" : "single";
  workspaceSizing.width = width;
  if (mode !== workspaceSizing.mode || !main.dataset.workLayout) { workspaceSizing.mode = mode; main.dataset.workLayout = mode; }
  const dialog = byId("source-dialog");
  if (dialog.open && ui.sourceSelection?.edge) {
    const dock = ui.view === "check" && sourceInspectorDockAllowed();
    if (dock !== dialog.classList.contains("inspector-docked")) openSourceDialog(true, false);
    else if (dock && width < 1240 && !byId("request-editor").contains(document.activeElement)) setRequestFold(true);
  }
}
function finishSidebarDrag(commit) {
  const drag = sidebarLayout.drag; if (!drag) return;
  if (sidebarLayout.frame) { cancelAnimationFrame(sidebarLayout.frame); sidebarLayout.frame = 0; }
  sidebarLayout.width = commit ? clampSidebarWidth(sidebarLayout.nextWidth) : drag.startWidth;
  sidebarLayout.drag = null;
  document.documentElement.classList.remove("sidebar-resizing");
  const handle = byId("sidebar-resizer");
  if (handle.hasPointerCapture(drag.pointerId)) handle.releasePointerCapture(drag.pointerId);
  renderSidebarLayout();
  if (commit) saveSidebarPreference();
}
function changeSidebarWidth(value) {
  if (sidebarLayout.drag) finishSidebarDrag(false);
  sidebarLayout.width = clampSidebarWidth(value); sidebarLayout.collapsed = false; renderSidebarLayout(); saveSidebarPreference();
}
try {
  const stored = JSON.parse(localStorage.getItem(sidebarPreferenceKey) || "null");
  if (stored && typeof stored.width === "number" && Number.isFinite(stored.width)) sidebarLayout.width = clampSidebarWidth(stored.width);
  if (stored && typeof stored.collapsed === "boolean") sidebarLayout.collapsed = stored.collapsed;
} catch (_) { /* Invalid or inaccessible local preferences use the documented default. */ }
renderSidebarLayout(); updateWorkspaceLayout();
if (typeof ResizeObserver === "function") new ResizeObserver(entries => updateWorkspaceLayout(entries[0].contentRect.width)).observe(byId("main-workspace"));
byId("sidebar-toggle").addEventListener("click", () => { if (sidebarLayout.drag) finishSidebarDrag(false); sidebarLayout.collapsed = !sidebarLayout.collapsed; renderSidebarLayout(); saveSidebarPreference(); });
const sidebarHandle = byId("sidebar-resizer");
sidebarHandle.addEventListener("pointerdown", event => {
  if (event.button !== 0 || sidebarLayout.collapsed || innerWidth <= 760) return;
  sidebarLayout.drag = { pointerId: event.pointerId, startWidth: sidebarLayout.width, startX: event.clientX };
  sidebarLayout.nextWidth = sidebarLayout.width;
  sidebarHandle.setPointerCapture(event.pointerId); document.documentElement.classList.add("sidebar-resizing"); event.preventDefault();
});
sidebarHandle.addEventListener("pointermove", event => {
  const drag = sidebarLayout.drag; if (!drag || drag.pointerId !== event.pointerId) return;
  sidebarLayout.nextWidth = clampSidebarWidth(drag.startWidth + event.clientX - drag.startX);
  if (!sidebarLayout.frame) sidebarLayout.frame = requestAnimationFrame(() => { sidebarLayout.frame = 0; if (!sidebarLayout.drag) return; sidebarLayout.width = sidebarLayout.nextWidth; renderSidebarLayout(); });
});
sidebarHandle.addEventListener("pointerup", event => { if (sidebarLayout.drag?.pointerId === event.pointerId) finishSidebarDrag(true); });
sidebarHandle.addEventListener("pointercancel", event => { if (sidebarLayout.drag?.pointerId === event.pointerId) finishSidebarDrag(false); });
sidebarHandle.addEventListener("lostpointercapture", event => { if (sidebarLayout.drag?.pointerId === event.pointerId) finishSidebarDrag(false); });
sidebarHandle.addEventListener("dblclick", () => changeSidebarWidth(240));
sidebarHandle.addEventListener("keydown", event => {
  if (event.key === "Enter" || event.key.toLowerCase() === "r") { event.preventDefault(); changeSidebarWidth(240); return; }
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  if (sidebarLayout.keyboardStart === null) sidebarLayout.keyboardStart = sidebarLayout.width;
  const value = event.key === "Home" ? 208 : event.key === "End" ? 360 : sidebarLayout.width + (event.key === "ArrowRight" ? 8 : -8);
  sidebarLayout.width = clampSidebarWidth(value); renderSidebarLayout();
});
sidebarHandle.addEventListener("keyup", event => { if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key) && sidebarLayout.keyboardStart !== null) { sidebarLayout.keyboardStart = null; saveSidebarPreference(); } });
sidebarHandle.addEventListener("blur", () => { if (sidebarLayout.keyboardStart !== null) { sidebarLayout.keyboardStart = null; saveSidebarPreference(); } });
document.addEventListener("keydown", event => {
  if (event.key !== "Escape") return;
  if (sidebarLayout.drag) { event.preventDefault(); event.stopImmediatePropagation(); finishSidebarDrag(false); }
  else if (sidebarLayout.keyboardStart !== null) { event.preventDefault(); event.stopImmediatePropagation(); sidebarLayout.width = sidebarLayout.keyboardStart; sidebarLayout.keyboardStart = null; renderSidebarLayout(); }
}, true);
window.addEventListener("blur", () => { if (sidebarLayout.drag) finishSidebarDrag(false); });
for (const item of byId("sidebar-nav").querySelectorAll(".nav-item")) {
  const label = item.querySelector(".nav-label").textContent;
  item.setAttribute("aria-label", label); item.title = label;
  const showTooltip = () => { if (!sidebarLayout.collapsed || innerWidth <= 760) return; const tooltip = byId("sidebar-tooltip"); tooltip.textContent = label; tooltip.style.top = item.getBoundingClientRect().top + "px"; tooltip.hidden = false; };
  item.addEventListener("mouseenter", showTooltip); item.addEventListener("focus", showTooltip);
  item.addEventListener("mouseleave", () => { byId("sidebar-tooltip").hidden = true; }); item.addEventListener("blur", () => { byId("sidebar-tooltip").hidden = true; });
}

// Operational workspaces and authentication never seed business facts in the client.
function isSyntheticMode() { return (state.mode || "synthetic_demo") === "synthetic_demo"; }
function catalogReady() { return Boolean(state.catalog && Object.keys(state.catalog.people || {}).length && Object.keys(state.catalog.lots || {}).length && Object.keys(state.catalog.cabinets || {}).length); }
function can(capability) {
  if (!authState.enabled) return true;
  const role = authState.actor?.role;
  if (role === "admin") return true;
  return role === "operator" ? ["check", "import", "model"].includes(capability) : role === "reviewer" ? ["check", "review", "model"].includes(capability) : false;
}
function capabilityForPath(path) {
  if (path.endsWith("/publish") || path.endsWith("/rollback")) return "publish";
  if (path.endsWith("/review")) return "review";
  if (path === "/check") return "check";
  if (["/documents", "/candidates", "/ledger-bundles"].includes(path)) return "import";
  if (path.endsWith("/explain") || path.endsWith("/orchestrate") || path === "/evidence/jev") return "model";
  return null;
}
function updateWorkspaceMode() {
  const synthetic = isSyntheticMode();
  const scope = byId("workspace-scope");
  scope.querySelector("strong").textContent = synthetic ? "合成演示空间" : "业务资料工作区";
  scope.querySelector("p>span").textContent = synthetic ? "业务决定使用合成快照；公开资料用于证据展示。专业审核未完成，不执行真实出库。" : "按已发布资料与规则核验。来源真实性与专业适用需另行确认，不自动执行真实出库。";
  byId("view-check").querySelector(".presets").hidden = !synthetic;
  byId("candidate-form").hidden = !synthetic;
  byId("business-candidate-guide").hidden = synthetic;
  byId("authorization-change-panel").querySelector("h2").lastChild.textContent = synthetic ? "提出授权变更" : "业务台账更新";
  byId("view-versions").querySelector(".subtitle").textContent = synthetic ? "合成候选或业务台账先预览再发布；操作者确认不等于专业审核。" : "导入完整来源台账，预览影响并由有权限的账户发布。旧记录保留原始快照。";
  if (!synthetic) byId("missing-demo-note").hidden = true;
  byId("empty-catalog-guide").hidden = synthetic || catalogReady();
  byId("empty-result").querySelector("p").textContent = synthetic ? "运行核验，查看程序决定、关联关系与可定位的原文片段。" : catalogReady() ? "填写本次人员、物料与柜位，核验后逐条回查已发布资料。" : "先导入并发布获授权台账，再填写业务申请。这里尚未形成实际核验结果。";
  if (!synthetic && !catalogReady()) { byId("draft-status").textContent = "先导入并发布获授权台账，当前目录为空。"; byId("draft-status").dataset.state = "draft"; }
  if (!synthetic && catalogReady() && !ui.inspected && !ui.requestPending) { byId("draft-status").textContent = "当前业务申请尚未核验。"; byId("draft-status").dataset.state = "draft"; }
  syncCheckAvailability();
}
function syncCheckAvailability() {
  const button = byId("check-form").querySelector("button[type=submit]");
  button.disabled = !catalogReady() || !can("check") || ui.requestPending || Boolean(ui.checkUnknown);
  button.title = !can("check") ? "当前角色没有核验权限" : !catalogReady() ? "先导入并发布人员、批次与柜位台账" : "";
}
function applyRolePermissions() {
  const mappings = [["#upload-form button[type=submit]", "import"], ["#ledger-import-submit", "import"], ["#jev-search-button", "model"]];
  for (const [selector, capability] of mappings) { const button = document.querySelector(selector); if (button) button.dataset.capability = capability; }
  for (const button of document.querySelectorAll("button[data-capability]")) {
    const allowed = can(button.dataset.capability);
    button.disabled = !allowed || button.dataset.busy === "true" || button.dataset.unknown === "true";
    button.title = allowed ? "" : "当前角色没有此操作权限";
  }
  for (const [id, capability] of [["check-form", "check"], ["upload-form", "import"], ["ledger-import-form", "import"], ["candidate-form", "import"], ["review-form", "review"]]) {
    const form = byId(id); if (!form) continue;
    const noteId = id + "-permission"; let note = byId(noteId);
    if (!can(capability)) { if (!note) { note = element("p", "当前角色可以查看，但没有执行这项写入操作的权限。", "permission-note"); note.id = noteId; form.prepend(note); } }
    else note?.remove();
  }
  syncCheckAvailability(); updateReviewSubmission();
  if (state.status && state.catalog) updateCandidateSubmission();
  renderModelState(); renderNexentState();
}
function renderActor() {
  byId("session-actor").hidden = !authState.enabled || !authState.actor;
  const roles = { admin: "管理员", operator: "操作者", reviewer: "复核员", viewer: "只读" };
  byId("session-actor-name").textContent = authState.actor ? (authState.actor.name || authState.actor.username || "当前账户") + " · " + (roles[authState.actor.role] || authState.actor.role) : "";
  if (authState.enabled && authState.actor) { byId("ledger-operator").value = authState.actor.username || authState.actor.name || ""; byId("ledger-operator").readOnly = true; }
}
function showLogin(reason = "使用已配置的工作区账户登录。") {
  authState.enabled = true;
  const dialog = byId("login-dialog");
  byId("login-description").textContent = reason;
  byId("login-password").value = "";
  if (!dialog.open) dialog.showModal();
  byId("login-username").focus({ preventScroll: true });
}
async function loadWorkspace() {
  await refreshStatus(); await refreshCatalog(); updateExternalSourcePermission();
  if (!authState.booted) {
    const today = new Date();
    byId("as-of").value = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, "0"), String(today.getDate()).padStart(2, "0")].join("-"); window.OntoLensDates?.sync?.();
    if (isSyntheticMode()) preset("allow");
    else { byId("quantity").value = ""; byId("source-kind").value = "private"; updateExternalSourcePermission(); }
    authState.booted = true;
  }
  await refreshOverview(); updateWorkspaceMode(); applyRolePermissions();
  await refreshNexentStatus();
}
async function bootWorkspace() {
  let response;
  try { response = await fetch("/api/auth/session", { credentials: "same-origin" }); }
  catch (_) { throw new Error("无法连接本地工作区，请检查服务后刷新。"); }
  // Older loopback-only runtimes may lack the session endpoint; protected status still enforces 401.
  if (response.status !== 404) {
    if (!response.ok) throw new Error("登录状态读取失败，请检查服务后刷新。");
    const session = await response.json();
    authState.enabled = session.enabled === true; authState.actor = session.actor || null;
    if (session.csrf_token) state.token = session.csrf_token;
    if (authState.enabled && !session.authenticated) { showLogin(); return; }
  }
  await loadWorkspace();
}
byId("login-dialog").addEventListener("cancel", event => event.preventDefault());
byId("login-form").addEventListener("submit", async event => {
  event.preventDefault(); const button = byId("login-submit"); if (button.disabled) return;
  button.disabled = true; button.setAttribute("aria-busy", "true"); button.textContent = "正在登录…"; byId("login-error").hidden = true;
  const username = byId("login-username").value; const password = byId("login-password").value;
  try {
    const response = await fetch("/api/auth/login", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
    const result = await response.json(); if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "登录失败，请检查账户信息。");
    const changedActor = authState.actor && (authState.actor.name || authState.actor.username) !== (result.actor?.name || result.actor?.username);
    if (changedActor) {
      for (const form of document.querySelectorAll("form")) if (form.id !== "login-form") form.reset();
      ui.reviewDrafts.clear(); ui.reviewUnknown.clear(); ui.current = null; ui.inspected = null; ui.context = "draft"; state.lastRun = null; state.lastResult = null; authState.booted = false;
      modelResults.clear(); nexentResults.clear(); pendingModels.clear(); pendingNexent.clear(); ui.sequence++; ui.revision++; ui.checkUnknown = null; ui.requestPending = false; byId("decision-content").hidden = true; byId("empty-result").hidden = false; byId("result-context").hidden = true;
    }
    authState.enabled = true; authState.actor = result.actor; state.token = result.csrf_token;
    byId("login-dialog").close(); await loadWorkspace(); renderActor();
    message("已登录工作区，权限按当前账户角色生效。");
  } catch (error) { byId("login-error").textContent = error.message; byId("login-error").hidden = false; if (!byId("login-dialog").open) showLogin("登录后的工作区读取未完成，请重试或检查服务。"); }
  finally { byId("login-password").value = ""; button.disabled = false; button.removeAttribute("aria-busy"); button.textContent = "登录工作区"; }
});
byId("logout-button").addEventListener("click", event => perform(event.currentTarget, async () => {
  saveReviewDraft();
  const dirty = [...ui.reviewDrafts.values()].some(draft => draft.note.trim()) || byId("candidate-note").value.trim() || byId("ledger-basis").value.trim();
  if (dirty && !window.confirm("退出会清除当前页面未保存的说明与选择，已保存记录不变。确定退出？")) return;
  await post("/auth/logout", {}); ui.loggingOut = true; location.reload();
}));
byId("login-username").autocomplete = "username"; byId("login-password").autocomplete = "current-password";
for (const button of document.querySelectorAll("[data-open-ledger]")) button.addEventListener("click", () => perform(button, async () => { await switchView("versions"); byId("ledger-import-details").open = true; byId("ledger-label").focus(); }));
let ledgerTemplateUrls = [];
byId("ledger-template-button").addEventListener("click", event => perform(event.currentTarget, async () => {
  const template = await api("/ledger-bundles/template");
  for (const url of ledgerTemplateUrls) URL.revokeObjectURL(url); ledgerTemplateUrls = [];
  const links = byId("ledger-template-links"); links.replaceChildren();
  const labels = { people: "人员授权", chemicals: "物料属性", lots: "批次库存", cabinets: "柜位约束", issues: "既往领用", rules: "规则" };
  for (const [group, source] of Object.entries(template.sources || {})) {
    const text = typeof source.content === "string" ? source.content : JSON.stringify(source.content, null, 2);
    const url = URL.createObjectURL(new Blob([text], { type: source.media_type || "application/json" })); ledgerTemplateUrls.push(url);
    const link = element("a", "下载" + (labels[group] || group) + "模板"); link.href = url; link.download = source.filename; links.append(link);
    if (source.fields) { const detail = element("details"); detail.append(element("summary", (labels[group] || group) + "字段说明"), element("pre", typeof source.fields === "string" ? source.fields : JSON.stringify(source.fields, null, 2))); links.append(detail); }
  }
  byId("ledger-template-note").textContent = template.notice || "模板只提供空结构，请填写真实、获授权的资料，不是可直接使用的演示事实。";
  if (template.constraints) { const detail = element("details"); detail.append(element("summary", "台账约束"), element("pre", JSON.stringify(template.constraints, null, 2))); links.append(detail); }
}));
let ledgerImportUnknown = false;
byId("ledger-import-form").addEventListener("submit", event => {
  event.preventDefault(); if (ledgerImportUnknown || !can("import")) return;
  perform(event.submitter, async () => {
    const form = new FormData();
    const fields = { label: "ledger-label", operator: "ledger-operator", basis: "ledger-basis", purpose: "ledger-purpose", authorized_by: "ledger-authorized-by", recorded_at: "ledger-recorded-at", kind: "ledger-kind" };
    for (const [name, id] of Object.entries(fields)) form.append(name, byId(id).value);
    form.append("local_operation_authorized", byId("ledger-authorized").checked ? "true" : "false");
    for (const group of ["people", "chemicals", "lots", "cabinets", "issues", "rules"]) { const file = byId("ledger-" + group).files[0]; if (!file) throw new Error("请选择完整的六份原始台账。"); if (!file.size || file.size > 2000000) throw new Error(group + " 文件应为 1–2,000,000 字节。"); if (group === "rules" && /\.csv$/i.test(file.name)) throw new Error("规则文件请使用 JSON 或 YAML。"); form.append(group, file); }
    byId("ledger-import-status").textContent = "正在保留原始文件并创建候选…";
    try {
      const candidate = await api("/ledger-bundles", { method: "POST", body: form });
      await refreshSources(); await refreshVersions(); await previewCandidate(candidate.id);
      byId("ledger-import-status").textContent = "候选已保存，尚未发布。请核对下方影响预览。";
      message(candidate.notice || "业务台账已形成候选，尚未改变当前生效资料。");
    } catch (error) {
      if (error.uncertain) { ledgerImportUnknown = true; await Promise.allSettled([refreshVersions(), api("/audit")]); byId("ledger-import-status").textContent = error.message + "。导入保存状态未确认，请核对候选与日志；不能自动重复导入（needs_support）。"; }
      else byId("ledger-import-status").textContent = error.message;
      throw error;
    } finally { if (ledgerImportUnknown) { byId("ledger-import-submit").dataset.capability = "import"; byId("ledger-import-submit").dataset.unknown = "true"; } }
  });
});
async function refreshNexentStatus() {
  try {
    nexentStatus = await api("/integrations/nexent");
    byId("nexent-connection-status").textContent = (nexentStatus.connected ? "平台已连接" : "平台未连接") + "；" + (nexentStatus.model_ready ? "专用模型已就绪" : "模型未就绪") + (nexentStatus.observed_at ? "；观测 " + nexentStatus.observed_at : "") + "。" + (nexentStatus.notice || "");
  } catch (_) { nexentStatus = null; byId("nexent-connection-status").textContent = "未取得当前连接状态，核心核验仍可用。"; }
  renderNexentState();
}
function renderNexentState() {
  const button = byId("nexent-report-button"); if (!button) return;
  const pending = pendingNexent.has(state.lastRun); const saved = nexentResults.get(state.lastRun);
  button.disabled = pending || !can("model") || !nexentStatus?.connected || !nexentStatus?.model_ready;
  button.textContent = pending ? "正在请求 Nexent 报告…" : "Nexent 辅助报告"; button.setAttribute("aria-busy", String(pending));
  byId("nexent-report-output").hidden = !saved?.response;
  if (saved?.response) byId("nexent-report-output").textContent = (saved.response.notice || "") + "\n\n" + saved.response.text;
  byId("nexent-report-status").textContent = pending ? "正在请求当前记录的独立辅助报告，不改变程序决定…" : saved?.error ? "Nexent 报告失败：" + saved.error : saved?.response ? "已收到当前记录的辅助报告；只发送去标识决定摘要，没有发送私有原文。" : !can("model") ? "当前角色无辅助报告调用权限。" : !nexentStatus?.connected || !nexentStatus?.model_ready ? "Nexent 专用服务未就绪；核心核验、原文和导出仍可用。" : "仅发送状态、动作、原因代码与证据数量；不发送人员、数量、日期或原文定位。";
}
byId("nexent-report-button").addEventListener("click", async () => {
  const inspected = state.lastResult; if (!inspected || pendingNexent.has(inspected.run_id) || !can("model") || !nexentStatus?.connected || !nexentStatus?.model_ready) return;
  const runId = inspected.run_id; const operation = {}; pendingNexent.set(runId, operation); nexentResults.delete(runId); renderNexentState();
  try { const response = await post("/runs/" + encodeURIComponent(runId) + "/orchestrate", {}); if (pendingNexent.get(runId) === operation) nexentResults.set(runId, { response }); }
  catch (error) { if (pendingNexent.get(runId) === operation) nexentResults.set(runId, { error: error.message }); }
  finally { if (pendingNexent.get(runId) === operation) pendingNexent.delete(runId); if (state.lastRun === runId) renderNexentState(); }
});

// Accessible select-only comboboxes. Native selects keep the canonical form values.
const enhancedSelects = new Map();
const selectMenu = element("div", null, "select-menu");
selectMenu.id = "enhanced-select-menu"; selectMenu.setAttribute("role", "listbox"); selectMenu.setAttribute("popover", "manual"); selectMenu.hidden = true;
document.body.append(selectMenu);
const selectUI = { owner: null, activeIndex: -1, epoch: 0, motion: null, typeBuffer: "", typeAt: 0, optionNodes: new Map() };
const selectReducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
function optionEnabled(option) { return !option.disabled && !(option.parentElement?.tagName === "OPTGROUP" && option.parentElement.disabled); }
function syncEnhancedSelect(select) {
  const entry = enhancedSelects.get(select); if (!entry) return;
  const label = select.selectedOptions[0]?.textContent || "请选择…";
  entry.value.textContent = label; entry.button.title = label;
  entry.button.setAttribute("aria-label", entry.label + "：" + label);
  entry.button.disabled = select.disabled || ![...select.options].some(optionEnabled);
  entry.button.setAttribute("aria-required", String(select.required));
  for (const attribute of ["aria-invalid", "aria-describedby"]) {
    if (select.hasAttribute(attribute)) entry.button.setAttribute(attribute, select.getAttribute(attribute)); else entry.button.removeAttribute(attribute);
  }
  if (selectUI.owner === entry) {
    if (entry.button.disabled) closeEnhancedSelect(true, true);
    else renderSelectOptions(entry);
  }
}
function syncAllEnhancedSelects() { for (const select of enhancedSelects.keys()) syncEnhancedSelect(select); }
function setSelectActive(index, ensureVisible = true) {
  const entry = selectUI.owner; if (!entry) return;
  const option = entry.select.options[index]; if (!option || !optionEnabled(option)) return;
  selectUI.activeIndex = index;
  for (const [key, node] of selectUI.optionNodes) node.dataset.active = String(key === index);
  const node = selectUI.optionNodes.get(index);
  if (node) {
    entry.button.setAttribute("aria-activedescendant", node.id);
    if (ensureVisible) {
      const top = node.offsetTop; const bottom = top + node.offsetHeight;
      if (top < selectMenu.scrollTop) selectMenu.scrollTop = top;
      else if (bottom > selectMenu.scrollTop + selectMenu.clientHeight) selectMenu.scrollTop = bottom - selectMenu.clientHeight;
    }
  }
}
function renderSelectOptions(entry) {
  selectUI.optionNodes.clear(); selectMenu.replaceChildren();
  selectMenu.setAttribute("aria-label", entry.label);
  let group = null;
  for (const [index, option] of [...entry.select.options].entries()) {
    const parent = option.parentElement;
    if (parent?.tagName === "OPTGROUP" && parent !== group) { group = parent; const heading = element("div", parent.label, "select-group"); heading.setAttribute("role", "presentation"); selectMenu.append(heading); }
    const item = element("div", null, "select-option");
    item.id = "select-option-" + entry.select.id + "-" + index; item.setAttribute("role", "option"); item.setAttribute("aria-selected", String(option.selected));
    item.setAttribute("aria-disabled", String(!optionEnabled(option))); item.dataset.index = String(index);
    const check = element("span", null, "select-check"); check.setAttribute("aria-hidden", "true");
    item.append(element("span", option.textContent, "select-option-text"), check);
    item.addEventListener("pointermove", event => { if (event.pointerType !== "touch" && optionEnabled(option)) setSelectActive(index, false); });
    item.addEventListener("click", () => commitSelectOption(index)); selectMenu.append(item); selectUI.optionNodes.set(index, item);
  }
  if (!entry.select.options.length) selectMenu.append(element("p", "暂无可选项", "select-empty"));
  if (!entry.select.options[selectUI.activeIndex] || !optionEnabled(entry.select.options[selectUI.activeIndex])) selectUI.activeIndex = entry.select.selectedIndex;
  if (!entry.select.options[selectUI.activeIndex] || !optionEnabled(entry.select.options[selectUI.activeIndex])) selectUI.activeIndex = [...entry.select.options].findIndex(optionEnabled);
  setSelectActive(selectUI.activeIndex, false);
}
function positionSelectMenu(entry) {
  const box = entry.button.getBoundingClientRect(); const gap = 6; const edge = 8;
  selectUI.anchor = { left: box.left, top: box.top, width: box.width, height: box.height, viewportWidth: innerWidth, viewportHeight: innerHeight };
  const below = innerHeight - box.bottom - gap - edge; const above = box.top - gap - edge;
  const desired = Math.min(320, entry.select.options.length * 44 + 12);
  const topSide = below < desired && above > below;
  const available = Math.max(44, Math.min(320, topSide ? above : below));
  const width = Math.min(box.width, innerWidth - edge * 2);
  selectMenu.style.width = width + "px"; selectMenu.style.maxHeight = available + "px";
  selectMenu.style.left = Math.min(Math.max(edge, box.left), innerWidth - width - edge) + "px";
  selectMenu.dataset.side = topSide ? "top" : "bottom";
  selectMenu.style.top = (topSide ? Math.max(edge, box.top - gap - Math.min(selectMenu.scrollHeight, available)) : box.bottom + gap) + "px";
}
function openEnhancedSelect(entry) {
  if (entry.button.disabled) return;
  if (selectUI.owner === entry) { closeEnhancedSelect(true); return; }
  closeEnhancedSelect(false, true);
  ++selectUI.epoch; selectUI.motion?.cancel(); selectUI.motion = null;
  selectUI.owner = entry; selectUI.activeIndex = entry.select.selectedIndex; selectUI.typeBuffer = "";
  const host = entry.button.closest("dialog[open]") || document.body;
  if (selectMenu.parentElement !== host) host.append(selectMenu);
  selectMenu.hidden = false; selectMenu.inert = false; selectMenu.removeAttribute("aria-hidden"); selectMenu.dataset.state = "open";
  entry.button.setAttribute("aria-expanded", "true"); renderSelectOptions(entry);
  if (typeof selectMenu.showPopover === "function" && !selectMenu.matches(":popover-open")) selectMenu.showPopover();
  positionSelectMenu(entry); setSelectActive(selectUI.activeIndex);
  if (!selectReducedMotion.matches && typeof selectMenu.animate === "function") {
    const offset = selectMenu.dataset.side === "top" ? -4 : 4;
    selectUI.motion = selectMenu.animate([{ opacity: 0, transform: "translateY(" + offset + "px) scale(.98)" }, { opacity: 1, transform: "translateY(0) scale(1)" }], { duration: 160, easing: "cubic-bezier(.2,.8,.2,1)" });
  }
}
function closeEnhancedSelect(returnFocus = false, immediate = false) {
  const entry = selectUI.owner;
  if (!entry && selectMenu.hidden) return;
  const epoch = ++selectUI.epoch; selectUI.motion?.cancel(); selectUI.motion = null;
  selectUI.owner = null; selectUI.activeIndex = -1;
  if (entry) { entry.button.setAttribute("aria-expanded", "false"); entry.button.removeAttribute("aria-activedescendant"); }
  selectMenu.inert = true; selectMenu.setAttribute("aria-hidden", "true"); selectMenu.dataset.state = "closing";
  if (returnFocus && entry?.button.isConnected && !entry.button.disabled) entry.button.focus({ preventScroll: true });
  const finish = () => {
    if (epoch !== selectUI.epoch || selectUI.owner) return;
    if (typeof selectMenu.hidePopover === "function" && selectMenu.matches(":popover-open")) selectMenu.hidePopover();
    selectMenu.hidden = true; selectMenu.dataset.state = "closed";
  };
  if (immediate || selectReducedMotion.matches || typeof selectMenu.animate !== "function") { finish(); return; }
  selectUI.motion = selectMenu.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 100, easing: "ease-out" });
  selectUI.motion.finished.then(finish, finish);
}
function commitSelectOption(index) {
  const entry = selectUI.owner; const option = entry?.select.options[index];
  if (!entry || !option || !optionEnabled(option)) return;
  const changed = entry.select.value !== option.value;
  entry.select.value = option.value;
  closeEnhancedSelect(true);
  syncEnhancedSelect(entry.select);
  if (changed) { entry.select.dispatchEvent(new Event("input", { bubbles: true })); entry.select.dispatchEvent(new Event("change", { bubbles: true })); }
}
function navigateSelect(entry, key) {
  const indexes = [...entry.select.options].map((option, index) => optionEnabled(option) ? index : -1).filter(index => index >= 0);
  if (!indexes.length) return;
  let at = indexes.indexOf(selectUI.activeIndex);
  if (key === "Home") at = 0; else if (key === "End") at = indexes.length - 1;
  else at = Math.max(0, Math.min(indexes.length - 1, at + (key === "ArrowDown" ? 1 : -1)));
  setSelectActive(indexes[at]);
}
function typeaheadSelect(entry, key) {
  const now = performance.now(); selectUI.typeBuffer = now - selectUI.typeAt > 700 ? key : selectUI.typeBuffer + key; selectUI.typeAt = now;
  const buffer = selectUI.typeBuffer.normalize("NFKC").toLocaleLowerCase();
  const query = [...buffer].every(char => char === buffer[0]) ? buffer[0] : buffer;
  const options = [...entry.select.options];
  for (let step = 1; step <= options.length; step++) {
    const index = (Math.max(0, selectUI.activeIndex) + step) % options.length; const option = options[index];
    if (optionEnabled(option) && [option.textContent, option.value].some(text => text.normalize("NFKC").toLocaleLowerCase().startsWith(query))) { setSelectActive(index); break; }
  }
}
for (const select of document.querySelectorAll("select:not([multiple])")) {
  if (!select.id || select.size > 1) continue;
  const labelNode = select.labels?.[0];
  const label = (labelNode ? [...labelNode.childNodes].filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent).join("").trim() : "") || select.getAttribute("aria-label") || select.id;
  const wrapper = element("span", null, "select-shell"); const button = element("button", null, "select-trigger"); const value = element("span", "", "select-value");
  button.type = "button"; button.id = select.id + "-trigger"; button.setAttribute("role", "combobox"); button.setAttribute("aria-haspopup", "listbox"); button.setAttribute("aria-expanded", "false"); button.setAttribute("aria-controls", selectMenu.id);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("aria-hidden", "true"); svg.classList.add("select-chevron");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); path.setAttribute("d", "m6 9 6 6 6-6"); svg.append(path); button.append(value, svg);
  select.before(wrapper); wrapper.append(select, button); select.classList.add("enhanced-select"); select.tabIndex = -1; select.setAttribute("aria-hidden", "true");
  const entry = { select, wrapper, button, value, label }; enhancedSelects.set(select, entry);
  select.addEventListener("focus", () => { if (!button.disabled) button.focus({ preventScroll: true }); });
  select.addEventListener("input", () => syncEnhancedSelect(select)); select.addEventListener("change", () => syncEnhancedSelect(select));
  new MutationObserver(() => syncEnhancedSelect(select)).observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "selected", "label", "value", "required", "aria-invalid", "aria-describedby"] });
  button.addEventListener("click", () => openEnhancedSelect(entry));
  button.addEventListener("keydown", event => {
    if (event.isComposing || event.ctrlKey || event.metaKey) return;
    const open = selectUI.owner === entry;
    if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); closeEnhancedSelect(true); return; }
    if (event.key === "Tab") { if (open) closeEnhancedSelect(false); return; }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) { event.preventDefault(); if (!open) { openEnhancedSelect(entry); if (event.key === "Home" || event.key === "End") navigateSelect(entry, event.key); } else navigateSelect(entry, event.key); return; }
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); if (open) commitSelectOption(selectUI.activeIndex); else openEnhancedSelect(entry); return; }
    if (!event.altKey && event.key.length === 1) { event.preventDefault(); if (!open) openEnhancedSelect(entry); typeaheadSelect(entry, event.key); }
  });
  syncEnhancedSelect(select);
}
selectMenu.addEventListener("mousedown", event => event.preventDefault());
document.addEventListener("pointerdown", event => { if (selectUI.owner && !selectMenu.contains(event.target) && !selectUI.owner.button.contains(event.target)) closeEnhancedSelect(false); }, true);
document.addEventListener("focusin", event => { if (selectUI.owner && !selectMenu.contains(event.target) && event.target !== selectUI.owner.button && event.target !== selectUI.owner.select) closeEnhancedSelect(false); });
function closeSelectIfAnchorChanged() {
  if (!selectUI.owner || !selectUI.anchor) return;
  const box = selectUI.owner.button.getBoundingClientRect(); const old = selectUI.anchor;
  if (["left", "top", "width", "height"].some(key => Math.abs(box[key] - old[key]) > .5) || old.viewportWidth !== innerWidth || old.viewportHeight !== innerHeight) closeEnhancedSelect(false, true);
}
document.addEventListener("scroll", event => { if (selectUI.owner && event.target !== selectMenu && !selectMenu.contains(event.target)) closeSelectIfAnchorChanged(); }, true);
window.addEventListener("resize", closeSelectIfAnchorChanged);
if (typeof ResizeObserver === "function") new ResizeObserver(closeSelectIfAnchorChanged).observe(byId("main-workspace"));
for (const form of document.forms) form.addEventListener("reset", () => queueMicrotask(syncAllEnhancedSelects));
selectReducedMotion.addEventListener("change", () => { if (selectReducedMotion.matches) selectUI.motion?.cancel(); });
