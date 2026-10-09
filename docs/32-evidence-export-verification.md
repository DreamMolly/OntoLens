# 导出复现包离线校验

这项校验用于脱离工作台后检查 `peiwu-replay-1` 导出包的内部一致性。它不联网、不依赖工作台数据库，并按快照内的冻结规则离线重算一次 status/decision，以发现导出结果被篡改；不验证来源真实性、语义正确性或专业审核，也不会把 `needs_review` 转成业务决定。

## 当前复核（2026-10-07）

本轮重新运行离线校验器复核了工作台既有 run 的导出包，没有创建新 run；CLI 校验阶段只在导出包内重算，不请求模型或外部服务。当前正式复核包为：

```powershell
.\.venv\Scripts\python.exe scripts/verify_evidence_export.py artifacts/peiwu-evidence-export-20261002-core.json
.\.venv\Scripts\python.exe scripts/verify_evidence_export.py artifacts/peiwu-evidence-export-20261002-needs-review-core.json
```

`ready` run `run_d609dabaed834bd3bd01` 为 15,977 字节、6 个来源、6/6 条引用已定位；`needs_review` run `run_43cbd91121e34894a6ae` 为 15,895 字节、6 个来源、4 条引用已定位、2 条显式 `unresolved`。两包 CLI 均退出 0，并通过 `review_records`、`decision_reexecution` 校验。HTTP 与包内校验收据为 `artifacts/evidence-export-http-acceptance-20261002-core.json`，独立报告为 `artifacts/evidence-export-verification-20261002-core.json` 和 `artifacts/evidence-export-verification-20261002-needs-review-core.json`。

2026-09-28 的历史 `needs_review` 包是在 `unresolved` 标记门禁修复前生成的，旧报告不再代表当前校验规则；保留它只用于历史追溯，不把它写成当前通过证据。

## 历史命令

```powershell
.\.venv\Scripts\python.exe scripts/verify_evidence_export.py artifacts/peiwu-evidence-export-20260928-core.json
.\.venv\Scripts\python.exe scripts/verify_evidence_export.py artifacts/peiwu-evidence-export-20260928-needs-review-core.json
```

校验内容包括：

- 导出格式、`run`/`version`/快照哈希绑定；
- `raw_encoding=base64` 的原始字节解码与 SHA256；
- 快照 provenance、人员证据和决定证据的来源闭包；
- locator、引用原文和来源哈希的一致性；
- `needs_review` 人工复核记录的 run 绑定、状态、来源定位、哈希、原文与 `decision_written=false`；
- 快照规则与原申请的离线 status/decision 重算（报告中的 `decision_reexecuted=true`）；
- 重复来源、重复 locator、损坏 JSON、非有限数字和损坏 Base64 的失败门禁。

`needs_review` 中明确的 `quote: null` 会计为 `unresolved`，不计入已验证引用；缺少 quote 字段、错误 locator 或不一致原文仍会失败。

## 2026-09-28 历史实测

HTTP 只读验收没有创建新 run。`ready` run `run_a3974294800a4098ba68` 的导出包为 15,977 字节，6 个来源、6/6 引用定位通过；`needs_review` run `run_7d9d1d09dfb54c409913` 的导出包为 15,808 字节，6 个来源、4 条引用定位通过、2 条为 `unresolved`。当时两包 CLI 均退出 0，输入文件未被改写；该历史校验尚未包含后续新增的离线决定重算与人工复核记录检查。

收据：`artifacts/evidence-export-http-acceptance-20260928-core.json`。独立校验报告：`artifacts/evidence-export-verification-20260928-core.json` 与 `artifacts/evidence-export-verification-20260928-needs-review-core.json`。

## 包含人工复核记录的验收

`artifacts/human-review-acceptance.json` 记录当前独立临时数据库的 HTTP 验收与脱离数据库的子进程校验，包含一条已定位引用与一条明确缺失引用。新 peiwu-review-1 记录绑定 run、版本、快照、申请哈希、序号和时间；删除引用、删除原文或注入业务决定会失败。无新版绑定信息的历史跟进记录显示 unresolved；不存在跟进记录的包不能作为人工复核功能的验收证据。

此检查不认证操作者身份或整个历史的完整性：未签名包中删除全部记录或重新编写全部字段无法通过内部一致性独立证明。
