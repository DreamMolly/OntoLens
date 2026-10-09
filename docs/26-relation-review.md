# OntoLens 关系候选审查

`purpose=relation_review` 与 `ontolens-relation-review-v1` 问题版本对 proposed 关系提供辅助复核。输入包含 subject、relation、object、原文定位与来源哈希。

输出只有 `jev_relation_probability` 和 `relation_support/relation_gap`，`review_required` 始终为 true。不生成 approved、decision 或 action，不自动发布本体；人工审核与确定性版本流程继续有效。

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_relation_review.py
.venv/Scripts/python.exe scripts/verify_jev.py --task relation_review
```

默认预检使用固定合成资料，不发在线请求。离线信号处理不证明关系真值、专家认可或行业收益，真实领域本体、标准对齐和独立审核分别验收。
