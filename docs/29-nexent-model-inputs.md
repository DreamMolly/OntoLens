# OntoLens Nexent 模型配置

平台输入按固定 Nexent 源码契约填写。Agent 通用模型、JEV 与工作台解释适配器分别配置。

## 必需输入

provider/model_factory、真实 model_name、model_type、base_url、api_key，以及超时、并发和调用额度。视觉能力与 reasoning 参数按实际 capability profile 判断，不能凭模型名称推断。

在模型管理页进行临时健康检查后保存模型记录，将实际返回的 `model_id` 绑定到 `ontolens_compliance_review`。可移植 Agent ZIP 不固化本机模型 ID。解释实例 `ontolens_result_explainer` 不绑定工具和 Skill。

绑定成功不等于运行成功。实际编排必须保存请求、工具轨迹、模型标识与错误状态，最终决定只能来自 `decision_check`。相关证据入口为 `artifacts/nexent-model-readiness.json`、`artifacts/nexent-integration-report.json`。

## 凭证与思考参数

API key 只放 Nexent 本机配置或项目 `.env`/密钥管理，不能进入仓库、ZIP、截图或材料。工作台使用 `ONTOLENS_MODEL_*`。

Nexent 请求支持 reasoning_effort 与 reasoning_budget_tokens 等字段，但界面选项取决于模型 catalog 的 reasoning_capability。未知自定义模型不得写成已支持；不同 provider 的 effort、budget 或 toggle 不可混用。

`ONTOLENS_MCP_TOKEN` 是工作台 `/mcp/` 访问令牌，不是模型 key、JEV key 或登录密码。已准备本机入口读取 `.runtime/ontolens-mcp-token.txt`，容器调用使用 `Authorization: Bearer <令牌>`；令牌不写命令行、截图或公开收据。

## 验收边界

保留当前中转供应商和实际模型配置。`observed_at` 证明本次探测时间，实际解释或编排仍以其调用结果为准。真实资料、独立专业审核、长期调用预算与跨机器冷启动分别验证。
