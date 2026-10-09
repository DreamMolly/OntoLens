# OntoLens Nexent 模型绑定输入清单

形成日期：2026-09-24。以下平台输入依据工作区固定的 Nexent v2.6.0 源码契约，历史绑定记录保留原字段。当前主包及新配置使用 `ontolens` / `ONTOLENS_*`，旧机器标识与环境兼容见[品牌与兼容说明](39-brand-compatibility.md)。

## 模型绑定输入

1. `model_factory/provider`：例如 Nexent 支持的 provider 或 `OpenAI-API-Compatible`；不要把 JEV 当作 Agent 通用模型。
2. `model_name`：平台可识别的真实模型名；不能填展示别名或假 ID。
3. `model_type`：通常为 `llm`；视觉模型按实际能力填写，不把 JEV 的 Noul 当 VLM。
4. `base_url`：模型 API 基地址；Nexent 的模型记录还支持 `api_key`、TLS 校验和超时等配置。
5. 费用与调用上限：单次/每日额度、并发限制、超时和重试上限。
6. 联调范围：选定获准发送的固定合成申请，并保留模型标识、请求日志和失败结果。

## 平台操作边界

- 先在 Nexent 模型管理页做临时健康检查，再持久化模型记录；健康检查不等于 Agent 运行通过。
- 模型记录成功后，将返回的数值 `model_id` 绑定到 `peiwu_compliance_review` 的 `model_ids`；不直接编辑导入 ZIP 写入假 ID。
- 绑定后才可执行一次真实 Agent/run；运行必须先检索证据，再调用七工具链，最终决定仍由 `decision_check` 返回。
- API key 只放 Nexent 本地配置或项目 `.env`/密钥管理，不写仓库、截图、ZIP 或材料。
- 失败时保留 `tool_error`/模型错误，不能用 JEV 结果、固定文本或本地解释适配器冒充 Nexent Agent 运行。

## 思考强度与历史绑定

Nexent 的 Agent 请求契约包含 `reasoning_effort`（`auto/none/minimal/low/medium/high/xhigh/max`）和 `reasoning_budget_tokens`。界面只有在所选模型的 catalog 声明 `reasoning_capability.status=supported` 时才应提供对应选择；未知的自定义 OpenAI-compatible 模型可能没有下拉选项，不能自行把某个参数写成已支持。Anthropic 风格模型可能使用 thinking budget，其他 provider 可能使用 reasoning effort 或 thinking toggle，必须以该模型的 capability profile 为准。

2026-09-24 历史记录：本机 `.env` 中的 `PEIWU_MODEL_*` 只配置当时工作台的可选解释接口；该轮另外在 Nexent 中创建模型记录并将 `model_id=1` 绑定到 Agent。当时 Agent 可运行，但模型 capability profile 未声明 reasoning controls，所以思考强度下拉框没有可用选项。当前新配置推荐 `ONTOLENS_MODEL_*`，旧配置仍兼容；是否支持思考强度仍由实际 capability profile 判断。

## MCP key

`ONTOLENS_MCP_TOKEN` 是工作台 `/mcp/` 的访问令牌，不是模型 API key、JEV key 或 Nexent 登录密码；旧 `PEIWU_MCP_TOKEN` 仍兼容。已有本机恢复入口继续读取 `.runtime/peiwu-mcp-token.txt`，该文件名是原实例兼容路径，不应贴到聊天、截图或仓库。Nexent 容器访问 `http://host.docker.internal:8765/mcp/` 时，Authorization 必须填写 `Bearer <该令牌>`；既有令牌不因品牌更名而重新生成。

## 历史只读状态

`artifacts/nexent-model-readiness.json` 记录：Agent `model_ids=[1]`、可见模型为 1、七个 MCP 工具和一次历史合成 Agent/run 已验证；2026-09-26 Elasticsearch green、data-process 运行、部署审计及迁移后平台工具复测通过。这些结果属于当时实例，不用来推断当前就绪。

## 2026-10-09 模型与调用范围

`artifacts/nexent-model-configuration-20261009.json` 记录同一中转供应商 `gpt-6-sol` / `model_id=2` 的实际绑定；`artifacts/operational-deployment-20261009.json` 记录隔离业务流和 Agent2 无工具辅助解释。七 MCP 与 Agent1 工具编排来自2026-10-08历史收据，不属于本次 `gpt-6-sol` 工具编排验证。产品实时连接通过 `/api/integrations/nexent` 的 `observed_at` 与实际调用结果判断。真实资料、专业审核、长期调用预算及独立冷启动仍待验，详见[业务部署](38-operational-deployment.md)。
