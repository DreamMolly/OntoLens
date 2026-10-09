# 格物镜 · OntoLens Nexent 导入包

这是格物镜 · OntoLens 的赛题 3 Agent 配置模板，按 Nexent 官方 Agent 导出/导入格式整理。它可以先导入查看，再绑定本地 MCP、模型和资料；不能在没有这些依赖时声称已完成 Nexent 联调。


## 目录

- agent.json：Agent 配置模板。
- mcp-service.local.json：Nexent 与本机工作台同机运行时使用。
- mcp-service-docker.json：Nexent 在 Docker 容器中运行时使用；需要宿主机端口可达，并在工作台设置 `ONTOLENS_MCP_TOKEN`。
- skills/ontolens-intake/SKILL.md：申请输入和边界。
- skills/ontolens-evidence/SKILL.md：证据检索与关系路径。
- skills/ontolens-decision/SKILL.md：确定性判定、候选审核和输出契约。
- 可选 JEV：evidence_rerank_jev 只做证据相关性重排，不参与四种决定。

## 使用顺序

已经部署的本机演示使用根目录 `start-demo.ps1`，自动读取现有 MCP 令牌并核验实际挂载。以下为首次合成演练接入步骤；日常恢复不要重复导入 Agent 或模型。详细说明见[日常启动](../docs/30-demo-startup.md)。实际业务工作区使用带账户的[业务入口](../docs/38-operational-deployment.md)，本包的合成接入步骤不替代业务部署。

1. 在项目根目录启动工作台：

   ~~~powershell
   $env:ONTOLENS_WORKSPACE_MODE = "synthetic"
   .\\start-workbench.ps1
   ~~~

2. 在浏览器打开 http://127.0.0.1:8765/api/status，确认返回 mode=synthetic_demo。
3. 在 Nexent 的 MCP 仓库添加 mcp-service.local.json 中的服务。容器化 Nexent 使用 Docker 模板，并把同一个令牌写入工作台进程环境。
4. 先在工具配置页扫描工具，再导入 ZIP 包。ZIP 含三个独立 Skill 子包；单独 JSON 不携带 Skill 内容。Agent 的 model_ids 留空，之后在实际部署中绑定真实模型，不使用假 ID。
5. 在 Nexent 工具测试中依次测试 asset_recognition、evidence_lookup、graph_query、candidate_suggestions、evidence_rerank_jev、decision_check、candidate_review。没有 JEV 密钥时，重排工具应明确返回 unavailable。
6. 只展示工作台返回的决定 JSON。needs_review 或 tool_error 时，不输出四种业务决定。

## 边界

本包默认使用合成目录和合成来源。上传真实资料前要核对处理/外发权限；上传后也不会自动变成有效规则。Agent 不提供化学品配制、反应、提取或使用指导。最终决定只来自 decision_check 调用的程序。

2026-09-26 已恢复本机 Agent、七工具、三个 Skill 和模型绑定，并有一次历史合成 Agent/run；2026-09-27 增加统一启动与启动依赖检查。命令：`.venv/Scripts/python.exe scripts/verify_nexent.py`。这些是对应日期的历史链路记录；当前模型与业务部署范围见[业务部署](../docs/38-operational-deployment.md)，真实资料、独立冷启动和长期稳定性仍待验证，详见[历史部署复核](../docs/19-deployment-review.md)和[日常启动](../docs/30-demo-startup.md)。

JEV 是可选的证据重排层，需要项目环境安装 .[jev] 并设置 TYPESAFE_API_KEY；它不能生成四种业务决定。
