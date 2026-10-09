# 关系候选审查

日期：2026-09-24。该项对应低资源本体的 proposed 关系审核，不是自动本体更新。

## 已实现

- `JevReranker` 新增 `purpose=relation_review` 和问题版本 `peiwu-relation-review-v1`。输入由程序提供 subject、relation、object、原文定位和来源哈希。
- 输出只有 `jev_relation_probability` 与 `relation_support/relation_gap` 复核提示，`review_required` 始终为 true；不会产生 `approved`、`decision` 或四种 action。
- 关系仍保持 `proposed`，人工审核和确定性版本发布流程不变；MCP 仍只有七个工具，没有新增写入能力。
- 在线模式只允许脚本固定的合成陈述；当前只执行本地预检，request_count=0。

## 验证

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m pytest -q tests/test_relation_review.py` | 0 | 关系支持信号、合成权限门禁和无业务决定输出通过 |
| `.venv/Scripts/python.exe scripts/verify_jev.py --task relation_review` | 0 | 固定合成预检；未发在线请求 |

尚未执行在线关系语义请求，未把模型概率写成专家认可、关系真值或行业效果。真实领域本体、标准对齐和独立审核仍待队员。
