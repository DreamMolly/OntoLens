# Nexent 参赛配置包

2026-09-26 当前运行说明：数据已冷拷贝并切换到项目 F 盘，逻辑备份恢复 MCP、Agent 和三个 Skill，模型已重新健康检查并绑定，data-process 已补齐。部署审计及迁移后七工具、四种决定、引用和导出复测均通过。一次 Agent/run 仍是历史合成证据，不代表真实资料或独立冷启动。

2026-09-23 用户确认报名完成。本页说明报名后如何把本地工作台接入 Nexent；队员姓名、导师和审核人仍不写入仓库。

## 已交付文件

- nexent/agent.json：按当前固定 Nexent 的 agent_id / agent_info / mcp_info 格式维护，agent_info 用字符串形式的 ID 索引；模型 ID 故意留空。
- nexent/mcp-service.local.json：同机运行模板。
- nexent/mcp-service-docker.json：Nexent 在 Docker 中运行的模板。
- nexent/skills/peiwu-intake/SKILL.md：输入边界。
- nexent/skills/peiwu-evidence/SKILL.md：证据与关系路径。
- nexent/skills/peiwu-decision/SKILL.md：确定性决定与变更预览。
- nexent/package.ps1：调用 scripts/build_nexent_package.py，打包为 artifacts/peiwu-nexent-agent.zip；ZIP 内含 agent.json 与 skills/<name>.zip，各子包内为 SKILL.md。相同输入产生相同 ZIP，旧包保留到 .runtime/package-backups，不删除文件。

## 导入前

已经安装并迁移的本机实例，日常只运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1`。脚本固定正确的数据目录，复用令牌与既有 Agent 配置；不需重新导入或绑定模型。`-CheckOnly` 可先验证路径和资源条件，详见 `30-demo-startup.md`。下面的导入步骤用于新环境准备。

本地启动：

~~~powershell
.\\.venv\\Scripts\\python.exe -m pip install -e ".[workbench,test]"
.\\start-workbench.ps1
~~~

同机 Nexent 使用 http://127.0.0.1:8765/mcp/。如果 Nexent 在 Docker 容器里，使用 host.docker.internal 地址，并在工作台进程中设置同一个令牌：

~~~powershell
$env:PEIWU_MCP_TOKEN = "队员自己生成的随机令牌"
.\\start-workbench.ps1 -BindHost 0.0.0.0
~~~

容器配置不能使用示例中的占位符。不要把令牌提交到仓库、截图或 PPT。

## Nexent 导入顺序

1. 按本机/容器模板在 Nexent MCP 仓库添加 peiwu-local；URL 使用对应地址。Authorization 必须是完整的 Bearer 加令牌，不是裸令牌。模板不是实际密钥文件。
2. 测试七个工具：asset_recognition、evidence_lookup、graph_query、candidate_suggestions、evidence_rerank_jev、decision_check、candidate_review。JEV 未配置时，evidence_rerank_jev 应返回 unavailable，不影响其他工具。
3. 在工具配置页执行“扫描/更新工具”（后端 GET /api/tool/scan_tool），使七工具进入工具目录；仅刷新 MCP 工具计数不足以导入 Agent。运行 nexent/package.ps1，然后导入 ZIP。单独 JSON 不携带 Skill 文件。重试前检查已有 Agent/Skill，不能重复创建。
4. 当前 Agent 为 peiwu_compliance_review，已绑定 `model_id=1`，并完成一次合成 Agent/run；只读状态见 `artifacts/nexent-model-readiness.json`，运行摘要见 `artifacts/nexent-agent-run-20260924.json`，字段清单见 `docs/29-nexent-model-inputs.md`。当前模型 capability profile 未声明 reasoning controls，因此没有思考强度下拉；真实行业资料、独立审核和部署修项仍待补。不填写假 ID、不自动消费额度。
5. 保存并调试一条申请：先查证据，再查关系，再调用 decision_check。
6. 保留 Nexent 版本、模型标识、工具调用日志和截图，作为初赛材料的可复现记录。

## 可选 JEV 证据重排

可用 `.venv/Scripts/python.exe scripts/import_nexent_agent.py` 检查包与现有 Agent/Skill。只有显式 --apply 才可能创建缺少的 Agent；已有内容一致则复用，同名冲突不覆盖。真实环境重跑报告见 docs/20-repeatable-nexent-import.md。

社区用法拓展见 docs/21-jev-community-research.md。已实现引用字面核验、变更影响、关系候选和录制/重放的离线契约；普通相关性重排的代表性在线记录见 `artifacts/jev-live-verification.json`，复核预检分别见 `scripts/verify_jev.py --task change_review`、`--task relation_review`。这些语义仍未在真实资料上在线验证，详见 docs/22-citation-review.md、docs/25-change-impact-review.md、docs/26-relation-review.md 与 docs/27-jev-replay.md。

JEV 只用于“哪些来源片段更支持当前问题”的结构化 Noul 判断。它不读取或修改最终决定，不参与 ALLOW、DENY、LIMIT、ISOLATE 的计算。

JEV 只接收已发布快照中 external_model_allowed=true 的文本片段。私有资料、未发布上传资料和图片二进制不会发送到 TypeSafe。公开资料是否可外发仍由资料授权决定，不能因为页面可访问就默认开启。

~~~powershell
.\\.venv\\Scripts\\python.exe -m pip install -e ".[jev]"
$env:TYPESAFE_API_KEY = "队员自己的 TypeSafe 密钥"
$env:TYPESAFE_MODEL = "jev-1.13.0"
$env:TYPESAFE_BASE_URL = "https://api.typesafe.ai"
~~~

可选的 TYPESAFE_BASE_URL 用于自定义服务端点；为兼容旧环境，代码也会读取 TYPESAFE_ENDPOINT。密钥只放在本机环境变量或密钥管理中，不提交仓库。JEV 的 Noul 只返回支持关系概率，没有独立置信度；正式使用前要用独立资料评测阈值。
`scripts/verify_jev.py` 会读取项目根目录被忽略的 `.env`，但不覆盖已有的非空进程环境变量；因此可以直接运行下面的预检或显式 `--live` 命令。
工作台的可选解释接口另有 `PEIWU_MODEL_PROTOCOL`：`chat_completions` 发送 `/chat/completions`，`responses` 发送 `/responses`，`messages` 发送 Anthropic 风格 `/messages`。这只是配伍工作台的解释适配器，不等于 Nexent Agent 已完成模型编排；Nexent 的模型仍需在平台中绑定并单独验证。

不消耗额度的预检：

~~~powershell
.\\.venv\\Scripts\\python.exe scripts/verify_jev.py
.\\.venv\\Scripts\\python.exe scripts/verify_jev.py --task citation_review
~~~

确认密钥和端点后，显式发送一条合成查询：

~~~powershell
.\\.venv\\Scripts\\python.exe scripts/verify_jev.py --live
~~~

TYPESAFE_JEV_REVIEW_THRESHOLD 的默认值是 0.75，只用于界面标记高优先级证据，不会自动批准候选或改变四种业务决定。阈值必须以后续独立资料评测校准。

引用模式对同一片段分别提出支持和矛盾问题；代码仅生成 conflicting_signals、possible_contradiction、weak_support、support_signal 复核提示，始终需要人工审核。字面校验失败、重复引用或引用数量超过 limit 时不发送请求，不能截断后漏检。`--task citation_review --live` 只允许脚本固定的合成陈述与内置来源，不接受自定义查询；该模式尚未在线验证。

## 复现验收

验收输出必须包含：

- Nexent Agent 配置版本和模型标识。
- MCP 服务 URL、工具列表和测试结果。
- 申请输入、工作台快照 ID、决定 JSON、reason_code 和 source_id/locator。
- needs_review 或 tool_error 的失败演示。
- 合成演示标签、审核人空缺说明和没有真实出库的说明。

2026-09-24 已通过运行中 Nexent 的 AgentImportRequest 校验并实际导入 ZIP，Agent ID 为 1；三个 Skill 已绑定。`.venv/Scripts/python.exe scripts/verify_nexent.py` 通过真实平台 /api/tool/validate 验证七工具、四种决定、needs_review、来源引用和重复决定，并保存版本/配置/调用结果到 artifacts/nexent-integration-report.json。此脚本不调用模型，不等价于模型驱动编排。

交付材料同步检查：`.venv/Scripts/python.exe scripts/audit_deliverables.py`。该命令核对最近一次 `validate_local.py` 的七项退出码、Word/PPT 测试数、Agent ZIP SHA256、当前平台/部署报告和证据矩阵边界；不把一致性检查写成模型或行业效果。

2026-09-26 平台部署修项已完成：关键持久化路径改为项目内 Windows F 盘绑定，Elasticsearch green，data-process 运行，部署审计退出 0。旧错误挂载源未删除，恢复前空库另有备份；详见 `19-deployment-review.md`。长期运行和独立冷启动仍需另行验证。

导出问题已定位为宿主机 IDM 返回“204 Intercepted by the IDM Advanced Integration”；容器内部 Web 导出一直正常。收紧端口后，宿主机导出已连续复测返回 200。脚本只对明确的 IDM 拦截启用容器内 Web 读取，未知空响应直接失败；不修改 IDM 设置、不绕过 Nexent 身份校验。平台实际导出包另存 artifacts/nexent-agent-export.zip，不能与源码构建包混淆。详见 `19-deployment-review.md`。
