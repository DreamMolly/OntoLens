# OntoLens JEV 录制与回放

录制和回放用于可复核开发，不替代在线服务或模型效果评测。

只有 `scripts/verify_jev.py --live --record-output <path>` 的成功在线结果才能生成 `ontolens-jev-replay-1`。失败或 unavailable 结果不能录制。记录保留 model、resolved_model、usage、input_hash、question_version、purpose 与候选信号，排除 API key。

`scripts/verify_jev.py --replay <path>` 不请求网络，输出 `status=replay`、`replay=true`、`live_request_sent=false`、`request_count=0`。回放只影响人工复核提示，不修改决定、规则、库存或授权，也不能在撤销权限后发起新请求。

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_jev_replay.py
```

录制样本标明时间与资料性质。回放不计为新的请求、真实资料效果或行业准确率。
