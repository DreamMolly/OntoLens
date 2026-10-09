# 变更影响复核排序

日期：2026-09-24。来源：`docs/21-jev-community-research.md` 中 jev-test-filter、jev-review 等社区工作流的边界化借鉴。

## 已实现

- `JevReranker` 新增 `purpose=change_review` 和问题版本 `peiwu-change-impact-review-v1`。候选文本只产生 `jev_impact_probability`、`impact_signal/context_signal` 等人工复核提示。
- 程序仍先计算确定性前后差异和受影响申请；JEV 不决定影响集合，不发布候选，不改库存、授权、规则或四种 action。
- 只有显式脚本的固定合成陈述才允许在线模式；网页/MCP 没有在线许可。当前 `scripts/verify_jev.py --task change_review` 只做本地预检，request_count=0。
- 候选、问题正文、模型和来源哈希仍参与 input_hash；`review_required` 始终为 true。

## 验证边界

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m pytest -q tests/test_change_review.py` | 0 | 变更信号、权限门禁、无 action/decision 输出通过 |
| `.venv/Scripts/python.exe scripts/verify_jev.py --task change_review` | 0 | 固定合成预检；`request_count=0`；JEV unavailable/live_not_authorized |
| `.venv/Scripts/python.exe -m pytest -q` | 0 | 最近全量 138 passed；不是行业效果 |

尚未执行 `--live` 变更复核，未发送真实资料，也没有把模型概率写成准确率或合规结论。候选关系语义审查、真实制度变更和独立人工金标准仍待队员。
