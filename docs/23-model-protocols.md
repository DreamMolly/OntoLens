# 模型解释协议边界

日期：2026-09-24。这里描述的是配伍本地工作台的可选“模型辅助解释”接口，不是 JEV，也不是 Nexent Agent 的模型绑定。

## 支持的协议

由 `PEIWU_MODEL_PROTOCOL` 选择，默认 `chat_completions`；兼容别名 `response`→`responses`、`message`→`messages`：

- `chat_completions`：发送到模型端点的 `/chat/completions`，使用 `messages`。
- `responses`：发送到 `/responses`，使用 `input` 与 `output_text/output` 解析。
- `messages`：发送到 Anthropic 风格 `/messages`，使用 `x-api-key`、`anthropic-version`、`system` 和用户消息。

请求只包含当前运行的 request/result 上下文，提示要求引用来源且不得改判。响应只返回文本，异常时保留原决定和证据。

## 信任边界

- 三种协议只服务 `/api/runs/{run_id}/explain`，不被 MCP 工具用于决定。
- JEV 仍只负责证据重排和复核优先级；`decision_check` 仍是唯一业务决定来源。
- 本轮只做请求构造和响应解析的离线契约测试，没有向通用模型端点发送请求。
- Nexent 源码目录包含 provider/model catalog 的配置能力，但当前 Agent 的 `model_ids` 仍为空；不能把本地适配器测试写成 Nexent Agent 模型编排通过。

## 复现

~~~powershell
.venv/Scripts/python.exe -m pytest -q tests/test_model_protocols.py
~~~

配置真实模型时由队员补充端点、模型名和费用/权限；密钥只放在项目根目录 `.env` 或本机密钥管理，不写入仓库、ZIP、截图或材料。在线验证后还要记录协议、resolved model、请求限制和失败结果，不能用模型自报准确率。
