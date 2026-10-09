# OntoLens 证据导出验证

`ontolens-replay-1` 包含申请、结果、版本快照、规则与引用闭包中的来源原始字节。验证脱离工作台数据库运行，不联网、不调用模型；核对包内一致性并按冻结规则重新计算 status/decision。

```powershell
.venv/Scripts/python.exe scripts/verify_evidence_export.py artifacts/ontolens-evidence-export-ready.json
.venv/Scripts/python.exe scripts/verify_evidence_export.py artifacts/ontolens-evidence-export-needs-review.json
```

也可将最后一个参数换为自己从工作台导出的 JSON。校验结果列出格式、运行/版本绑定、快照与原字节 SHA256、来源闭包、定位、引文、规则决定和人工复核绑定；输入损坏、重复项、非有限数字或篡改会失败。

## 复核边界

`ontolens-review-1` 记录绑定 run、版本、snapshot_hash、request_sha256、引用及审计序号/时间。缺失引用必须保留 quote=null、unresolved=true；人工记录不写入业务决定。删除原文、篡改引用或注入决定会被独立检查拒绝。

needs_review 仍没有业务决定，不被离线检查转换为放行。没有复核记录的包不证明复核功能，结构与哈希匹配不认证来源真实性、身份、语义正确性或专业审核。

当前软件测试见 `tests/test_export_verification.py`、`tests/test_review_integrity.py`；独立复核验收入口为 `scripts/verify_review_workflow.py` 和 `artifacts/human-review-acceptance.json`。
