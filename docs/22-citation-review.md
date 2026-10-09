# 引用支撑复核与外发权限修复

日期：2026-09-24。来源：`21-jev-community-research.md` 中 citation-verifier 的逐项引用审查与 jev-review 的多问题拆分思路。只借鉴工作流，不复制其默认阈值、自动调用或项目成绩。

## 已实现与验证边界

- 复用 `/api/evidence/jev` 与 `evidence_rerank_jev`，新增可选 `citations`；MCP 仍为七工具，peiwu 仍只有 decide、eval、promote。
- 程序先逐项检查已发布快照成员、原始 BLOB 的 SHA256、定位和完整原文。重复、丢失、篡改或超出候选数量限制时拒绝，不截断漏检。
- 页面可以针对历史决定的证据输入事实性陈述，显示字面核验结果与 JEV 的实际状态。切换申请后不会把上一条的异步结果显示到新决定上。
- 可选 Noul 分别判断支持和矛盾，代码生成冲突信号、可能矛盾、支持不足或支持信号提示；它们只决定复核优先级，始终保留人工复核，不修改 action、approved_quantity 或 reason_code。
- 记录 model、resolved_model、usage、input_hash、question_version、概率；引用另绑定 snapshot_hash 和 citation_input_hash，审计事件为 jev_citations_reviewed。问题正文、模型与来源哈希参与指纹。
- 引用支持/矛盾概率处理目前只有模拟客户端测试。字面核验通过不意味着引用陈述已经得到语义支持。网页/MCP 即使有密钥也不发请求。

- 普通相关性重排已通过一次显式 `scripts/verify_jev.py --live` 合成请求；脱敏记录见 `artifacts/jev-live-verification.json`。这只验证模型端点、SDK、请求/响应字段和审计链路可用，不是准确率、事实认证或行业效果。引用支持/矛盾模式仍未在线验证。

本轮对同一固定合成相关性查询进行了三次短复测，`artifacts/jev-live-verification.json` 保存其中一条代表性样本；没有发送私有或真实行业资料，也没有把社区示例分数作为项目结果。引用在线演示仍只允许脚本固定合成陈述；真实资料和任意陈述的在线授权不在此实现内。

## 外发权限修复

旧逻辑在每次重启时自动把所有 synthetic 来源标成允许外发；这会覆盖上传者未授权的选择。现在只有内置种子显式授权。上传资料保持原选择；旧来源仅按已有 source_imported 审计恢复被误开的权限，并记录 source_permission_restored，不删除资料或修改业务快照。

实际工作台重启前使用 SQLite backup API 保存：`.runtime/workbench-permission-backups/20260924-124530.sqlite3`。SHA256：`314af8b48f3c31304a176b8dcf564299ac4f30999ff108b61ae935d82b35f65c`。这是本机恢复备份，不放入公开提交包。

## 实际验证

| 命令 | 退出码 | 观察到的结果与边界 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m pytest -q tests/test_citation_review.py tests/test_jev.py` | 0 | 29 passed；真实来源完整性、权限、模拟信号处理，不是模型效果评测 |
| `.venv/Scripts/python.exe scripts/verify_jev.py --task citation_review` | 0 | citation_check=passed、JEV unavailable、request_count=0 |
| `.venv/Scripts/python.exe scripts/verify_jev.py --live` | 0 | 一次合成相关性请求；resolved_model=jev-1.13.0、request_count=1；不是效果评测 |
| `.venv/Scripts/python.exe scripts/verify_nexent.py` | 0 | 真实平台 offline_citation_check=true；模型编排仍为 false |
| `.venv/Scripts/python.exe scripts/validate_local.py` | 0 | 2026-09-28 最新全量 271 passed；浏览器、MCP、资产回归、JEV 预检、pip check、JS 检查全部退出 0 |
| `.venv/Scripts/python.exe scripts/verify_evidence_export.py <export.json>` | 0 | 2026-09-28 对 ready 与 needs_review 的 HTTP 只读导出包做内部一致性校验；不联网、不重跑决定、不证明真实性或专业审核 |
| `.venv/Scripts/python.exe scripts/audit_deliverables.py` | 0 | 验证报告、Word/PPT、Agent ZIP 与证据矩阵一致；不代表模型或行业效果 |

引用阶段原始日志保存在 `.runtime/validation/20260924-124829-5ce869df/`；变更复核加入后的最新 132 项复测日志由 `artifacts/local-validation-report.json` 指向。后续新增测试时数字可能增长，不覆盖本阶段历史结论。

首次全量检查为 115 passed / 1 failed：旧测试错误地要求 legacy synthetic 自动获得外发许可。修正为旧资料默认不允许、内置种子仍允许后，全量通过；随后为交付自检和本地 `.env` 读取增加 5 个测试，最终为 121 passed。没有删除失败测试，没有修改冻结规则或 H01–H60。

## 仍待完成

变更影响复核、关系候选审查和模型结果录制/重放的离线契约已实现；真实资料语义、独立标签与阈值校准仍待队员。Nexent 模型绑定、一次合成 Agent/run、F 盘迁移和平台复测已完成，但这些不能替代引用语义或行业效果验证。
