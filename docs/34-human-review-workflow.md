# needs_review 人工复核

当申请缺少人员、批次或柜位资料，授权未生效/过期，或数量单位不一致时，工作台返回阻塞原因、补件建议和下一步，decision 保持为空。

## 操作者跟进

界面逐条展示已定位原文与缺失引用，由操作者选择本次记录涉及的引用；默认不选择。可以只记录补件要求。提交后原始核验结果保持不变，历史与导出展示新增记录。切换申请会重置表单；旧请求的成功或错误不会显示到另一条申请上。

复核人是操作者填写的名称，未进行身份认证，也不构成专业审核背书。状态为 queued、in_review、evidence_requested、closed_no_decision；最后一种只表示结束跟进记录。补件之后须创建新核验，不能用人工记录发布业务决定。

## 记录与引用

`POST /api/runs/{run_id}/review` 接受 evidence_references 中的 source_id、locator、sha256、quote 和 unresolved。明确缺失的引用必须使用 `quote=null, unresolved=true`。旧客户端的 evidence_ids 会在本次新建记录时展开为具体引用；历史审计记录不会被重新生成。

服务端在写入同一事务内重新检查原始字节哈希与定位原文，来源已变更时拒绝写入。新记录使用 ontolens-review-1，绑定记录 ID、run、版本、快照哈希及申请哈希，并返回该次提交自身的审计序号和时间。并发提交不会借用另一条记录的时间。decision_written 与 reviewer_identity_verified 固定为 false。

跟进记录仅允许追加到审计表；核验结果原始行不被修改。这是应用层追加约束，不是防止数据库管理员篡改的签名日志。

## 脱离数据库复核

导出校验器核对新记录的版本/申请绑定、引用集合、定位、原文、缺失状态、审计顺序和禁止改判字段。删除引用数组、删除 quote、改写哈希或注入决定会失败。旧记录没有新版本绑定信息时，review_records 明确为 unresolved，不会伪装为完整验证。

包内哈希与顺序只能证明内部一致性；重写整个未签名包或删除所有复核历史无法由此认证。操作者身份、来源真实性、语义正确性和专业审核均未验证。

## 验收

```powershell
.venv/Scripts/python.exe scripts/verify_review_workflow.py
.venv/Scripts/python.exe scripts/verify_evidence_export.py artifacts/human-review-evidence-export.json
```

第一条命令用独立临时 SQLite 经 ASGI HTTP 客户端创建合成核验和复核，再由另一进程仅凭 JSON 校验导出。它同时运行删除引用和注入决定两个负例，不访问日常工作台数据库，不发送模型请求。

收据为 artifacts/human-review-acceptance.json，原包与校验结果分别为 artifacts/human-review-evidence-export.json、artifacts/human-review-export-verification.json。收据包含输入源码和包的 SHA256。范围为合成软件验收，非真实行业效果。

针对性回归：

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_review_integrity.py tests/test_review_workflow.py tests/test_export_verification.py tests/test_workbench_flow.py
```
