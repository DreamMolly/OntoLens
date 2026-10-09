# OntoLens 变更影响复核

`JevReranker` 的 `purpose=change_review` 使用 `ontolens-change-impact-review-v1` 问题版本。候选文本产生 `jev_impact_probability`、`impact_signal/context_signal` 等人工复核提示。

程序先计算确定性前后差异和受影响申请。JEV 不决定影响集合，不发布候选，不改库存、授权、规则或 action；`review_required` 始终为 true。候选、问题正文、模型与来源哈希参与 input_hash。

默认固定合成预检不发在线请求，在线范围按脚本许可与来源外发约束执行：

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_change_review.py
.venv/Scripts/python.exe scripts/verify_jev.py --task change_review
```

离线契约只验证信号、权限与无决定输出。真实制度变更、在线语义、独立人工标签及阈值校准仍需专门评测，模型概率不作为准确率或合规结论。
