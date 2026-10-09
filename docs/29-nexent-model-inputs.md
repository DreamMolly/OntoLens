# Nexent 模型绑定输入清单

日期：2026-09-24。依据工作区固定的 Nexent v2.6.0 源码契约；不代表当前实例已经配置模型。

## 队员需要提供

1. `model_factory/provider`：例如 Nexent 支持的 provider 或 `OpenAI-API-Compatible`；不要把 JEV 当作 Agent 通用模型。
2. `model_name`：平台可识别的真实模型名；不能填展示别名或假 ID。
3. `model_type`：通常为 `llm`；视觉模型按实际能力填写，不把 JEV 的 Noul 当 VLM。
4. `base_url`：模型 API 基地址；Nexent 的模型记录还支持 `api_key`、TLS 校验和超时等配置。
5. 费用与调用上限：单次/每日额度、并发限制、超时和重试上限。
6. 独立联调窗口：队员确认可以发送一条固定合成申请，并保留模型标识、请求日志和失败结果。

## 平台操作边界

- 先在 Nexent 模型管理页做临时健康检查，再持久化模型记录；健康检查不等于 Agent 运行通过。
- 模型记录成功后，将返回的数值 `model_id` 绑定到 `peiwu_compliance_review` 的 `model_ids`；不直接编辑导入 ZIP 写入假 ID。
- 绑定后才可执行一次真实 Agent/run；运行必须先检索证据，再调用七工具链，最终决定仍由 `decision_check` 返回。
- API key 只放 Nexent 本地配置或项目 `.env`/密钥管理，不写仓库、截图、ZIP 或材料。
- 失败时保留 `tool_error`/模型错误，不能用 JEV 结果、固定文本或本地解释适配器冒充 Nexent Agent 运行。

## 思考强度与当前缺口

Nexent 的 Agent 请求契约包含 `reasoning_effort`（`auto/none/minimal/low/medium/high/xhigh/max`）和 `reasoning_budget_tokens`。界面只有在所选模型的 catalog 声明 `reasoning_capability.status=supported` 时才应提供对应选择；未知的自定义 OpenAI-compatible 模型可能没有下拉选项，不能自行把某个参数写成已支持。Anthropic 风格模型可能使用 thinking budget，其他 provider 可能使用 reasoning effort 或 thinking toggle，必须以该模型的 capability profile 为准。

本机 `.env` 中的 `PEIWU_MODEL_*` 只配置配伍工作台的可选解释接口；本轮已另外在 Nexent 中创建模型记录并将 `model_id=1` 绑定到 Agent。当前 Agent 可运行，但模型 capability profile 未声明 reasoning controls，所以思考强度下拉框仍没有可用选项。

## MCP key

`PEIWU_MCP_TOKEN` 是本地工作台 `/mcp/` 的访问令牌，不是模型 API key、JEV key 或 Nexent 登录密码。当前令牌保存在 `.runtime/peiwu-mcp-token.txt`，不应贴到聊天、截图或仓库。Nexent 容器访问 `http://host.docker.internal:8765/mcp/` 时，Authorization 必须填写 `Bearer <该令牌>`；现有七工具测试已使用这条本地链路，不需要重新生成令牌。

## 当前只读状态

`artifacts/nexent-model-readiness.json` 记录：Agent `model_ids=[1]`、可见模型为 1、七个 MCP 工具和一次历史合成 Agent/run 已验证；2026-09-26 Elasticsearch green、data-process 运行、部署审计及迁移后平台工具复测通过。真实资料、独立审核、费用上限和独立冷启动仍待补。
