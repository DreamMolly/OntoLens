# OntoLens 模型解释协议

本接口服务工作台的可选解释路由，与 JEV 重排和 Nexent 平台模型绑定分别配置、分别验收。

## 协议

由 `ONTOLENS_MODEL_PROTOCOL` 选择，默认 `chat_completions`：

| 值 | 请求与响应 |
| --- | --- |
| `chat_completions` | `/chat/completions`，messages 与 choices |
| `responses` | `/responses`，input 与 output_text/output |
| `messages` | Anthropic 风格 `/messages`，system、用户消息、x-api-key 与 content |

`ONTOLENS_MODEL_BASE_URL`、`ONTOLENS_MODEL_NAME` 和 `ONTOLENS_MODEL_API_KEY` 只放本机配置。参数能力以实际供应商与模型契约为准。

## 信任边界

三协议只服务 `/api/runs/{run_id}/explain`，输出文本不写回决定、数量、规则或快照。私有或未获准来源只发送受控枚举与计数摘要；获准原文也须保留引用检查。服务失败或空解释不被记录为成功。

离线契约测试覆盖构造与解析，不证明三个协议均在线可用。Nexent Agent 编排需要平台自身的模型绑定与真实运行收据，不能由本地适配器推定。

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_model_protocols.py
```

真实调用记录协议、模型、请求限制和失败状态，独立评测解释正确性与稳定性，不使用模型自报准确率。
