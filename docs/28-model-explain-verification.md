# 模型解释联调预检

日期：2026-09-24。该脚本只验证本地工作台的可选解释路由，不等于 Nexent Agent 模型编排。

## 用法

- `.venv/Scripts/python.exe scripts/verify_model_explain.py`：只读取 `.env` 配置，不发模型请求。
- `.venv/Scripts/python.exe scripts/verify_model_explain.py --live`：只在队员明确配置模型端点、模型名和凭证后，向本机工作台发送一条固定合成申请解释请求。
- `--output` 只能写入项目内 JSON；输出不包含 API key。

## 边界

- `PEIWU_MODEL_PROTOCOL` 可为 `chat_completions`、`responses` 或 `messages`；解释响应不改写原决定和证据。
- 没有模型配置时预检仍退出 0，并明确 `configured=false`、`live_request_sent=false`。
- 本脚本不调用 Nexent 平台、不绑定 Agent model_id、不替代真实 Agent/run 验证。

## 本轮结果

`.venv/Scripts/python.exe scripts/verify_model_explain.py` 默认预检不发请求。2026-09-26 本地 `.env` 模型配置存在，并已用于恢复 Nexent 模型记录和健康检查；工作台三协议在线解释仍未逐项验证，费用与持续调用上限待队员确认。
