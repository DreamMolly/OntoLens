# JEV 录制与重放边界

日期：2026-09-24。录制/重放只用于可复核开发记录，不替代在线服务或模型效果评测。

## 规则

- 只有 `scripts/verify_jev.py --live --record-output <path>` 在成功在线请求后才能生成 `peiwu-jev-replay-1` 记录；失败或 unavailable 结果不能录制。
- `scripts/verify_jev.py --replay <path>` 不请求网络，输出 `status=replay`、`replay=true`、`live_request_sent=false`、`request_count=0`。
- 记录保留 model、resolved_model、usage、input_hash、question_version、purpose 和候选信号；不得保存 API key。
- 重放结果必须标为 recorded/replay，不能作为新的 JEV 请求、真实资料结果、准确率或专家结论。权限撤销后也不能用它发起新请求。
- replay 只影响证据/候选人工复核提示，不能修改 `decision_check`、规则、库存、授权或四种 action。

## 离线验证

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m pytest -q tests/test_jev_replay.py` | 0 | 录制条件、格式门禁、重放标记通过 |
| `.venv/Scripts/python.exe -m pytest -q` | 0 | 2026-09-28 全量 271 passed；不是模型效果 |

本轮没有新增在线 JEV 请求；已有代表性在线样本与回放记录必须分开保存。
