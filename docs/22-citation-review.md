# OntoLens 引用支撑复核

引用复核复用 `/api/evidence/jev` 与 `evidence_rerank_jev`，可选输入 `citations`。它只提供来源核对与人工复核提示，不产生业务决定。

## 处理顺序

程序逐项检查已发布快照成员、原始 BLOB 的 SHA256、定位与完整原文。重复、丢失、篡改或过量引用拒绝，不按 limit 截断漏检。页面按原 run 绑定异步结果，切换申请后不展示其他决定的响应。

可选 Noul 分别判断支持与矛盾信号。代码显示支持不足、可能矛盾或支持提示；`action`、`approved_quantity`、`reason_code` 保持程序结果。字面匹配不能证明陈述语义正确。

## 权限与证据

上传资料默认本地处理，私有来源不能外发；内置合成种子的许可不扩展到上传资料。在线请求必须显式 `live=true`，且来源非私有并获准外发。配置密钥不自动请求。

记录 model、resolved_model、usage、input_hash、question_version、snapshot_hash、citation_input_hash 与信号。审计事件为 `jev_citations_reviewed`；原始记录不得作为准确率或专业审核结论。

## 验证方法

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_citation_review.py tests/test_jev.py
.venv/Scripts/python.exe scripts/verify_jev.py --task citation_review
```

默认预检不发在线请求。当前软件结果见 `artifacts/local-validation-report.json`；引用语义、独立标签、阈值校准和真实资料效果需要单独评测。
