# 格物镜 · OntoLens：可追溯的实验室危化品领用核验工作台

版本：0.1.0 草稿
状态：已报名。v0.4.0 带账户的空业务库、六台账导入/检查/发布、核验/复核/导出已实现；2026-10-09 Docker 业务部署与当前 gpt-6-sol（model_id=2）边界调用收据通过。行业字段适用、独立评测、专业审核、外部冷启动、长期稳定性和正式提交待补。

## 1. 项目概述

格物镜 · OntoLens 面向实验室危化品领用的旁路历史核验和证据追踪。系统把申请、人员授权、批次台账、柜位限制、未归还类别和规则版本绑定为可回查快照，返回 ALLOW、DENY、LIMIT、ISOLATE 四种程序决定；资料缺失、冲突、单位不一致或授权失效时返回 needs_review，不猜测业务决定。

比赛演练使用明示的合成台账或公开制度；业务入口默认空库，不注入演示事实。软件可导入授权资料并形成版本化旁路核验，但字段适用与规则专业审核另验，不执行真实出库。

## 2. 真实问题与范围

真实场景验证仍需记录一个获授权的旁路任务：谁在什么场景下需要核对哪些资料，资料发生版本变化后如何找出受影响申请。目前软件已经支持六台账导入、业务旁路核验与合成回放；领域审核、真实表单和资料授权仍待完成。

范围包括资产来源记录、证据定位、关系路径、确定性判定、候选变更预览、版本发布/回滚和审计导出。范围不包括化学品配制、反应、提取、使用指导、自动出库、门锁控制和替代专业审核。

## 3. 整体架构

    申请 JSON
       ↓
    FastAPI / Nexent MCP
       ├─ evidence_lookup：来源检索
       ├─ graph_query：版本快照关系路径
       ├─ asset_recognition：资产标识和待审关系
       ├─ decision_check：可信快照 → ontolens.checker
       ├─ candidate_suggestions：低资源候选提取
       ├─ evidence_rerank_jev：可选证据相关性重排
       └─ candidate_review：候选影响与冻结基准
       ↓
    SQLite 版本快照、来源哈希、审计事件
       ↓
    ALLOW / DENY / LIMIT / ISOLATE

Nexent 只编排、检索、解释和记录，不能改写决定。最终决定 JSON 由程序生成。MCP 工具不提供任意数据库写入、规则发布或回滚权限。

## 4. 数据资产和处理

当前合成来源包括人员授权、物料属性、批次台账、柜位限制、未归还记录和 v2 教学规则。每个来源记录文件哈希、媒体类型、来源性质、定位片段和创建时间。文本、Markdown、JSON、CSV、YAML 和带文本 PDF 可导入；图片只保存预览或人工摘录，自动 OCR 尚未配置。

仓库额外提供 synthetic-asset-label.png 和对应人工摘录，验证图像来源进入资产识别链。该图由本地模板生成，图像内容和人工摘录均标为合成演示，不能称作自动图像理解或 OCR。

真实资料导入前必须登记可读、可处理、可外发和可再分发范围。工作台对每份来源保存 external_model_allowed；默认仅本地处理，私有资料无法标记为可外发。来源正文只作为数据，不能作为工具指令。上传不自动成为有效事实；候选必须明确来源定位和有效期，由具备权限的管理员显式发布。发布是软件版本操作，不代表字段适用性获专业审核。

## 5. 知识图谱 / 关系模型

当前最小实体为 Chemical、HazardClass、Lot、StorageZone、Person、Policy、Request、Decision、Evidence、RuleVersion。当前实现以版本化 JSON 快照和确定性关系路径展示，不声称已经完成自动本体生成。

申请核验路径为：申请 → 人员授权 → 批次 → 化学品/危害类别 → 柜位限制 → 未归还类别 → 规则版本 → 程序决定。每条边带 source_id、locator、quote 和 sha256。

后续真实资料应单独建立本体类型、关系端点、有效期和冲突记录；新增事实不能自动变成可执行安全规则。

## 6. Nexent Agent 配置

导入包见 nexent/：Agent 为 peiwu_compliance_review；Skill 为 peiwu-intake、peiwu-evidence、peiwu-decision；MCP 服务为 peiwu-local。工具包括 asset_recognition、evidence_lookup、graph_query、candidate_suggestions、evidence_rerank_jev、decision_check、candidate_review。可移植导入包不固化模型 ID；本机当前运行实例绑定 model_id=2（gpt-6-sol，中转配置），模型配置收据为 `artifacts/nexent-model-configuration-20261009.json`；ZIP 按官方格式包含 Skill 子 ZIP，已实际导入并绑定。复现：.venv/Scripts/python.exe scripts/verify_nexent.py。

上述 `peiwu` 前缀仅为既有平台机器标识，产品名称为格物镜 · OntoLens。原始 Agent/Skill 包、参赛草稿文件及历史证据保留原档案名，以保持引用和校验对应；当前源码主包为 `ontolens`，迁移说明见[品牌与兼容说明](../docs/39-brand-compatibility.md)。

JEV 的 Noul 只判断证据片段是否支持查询，用于排序和人工复核分流；最终决定仍由 decision_check 调用的确定性程序产生。JEV 只读文本状态，图片资料需先有本地提取文本或人工摘录，因此当前不把 JEV 写成图像理解或 OCR 能力。

Nexent 连接步骤见 docs/17-nexent-package.md。artifacts/nexent-integration-report.json 记录迁移后平台 API 七工具及四种决定调用；历史合成 Agent/run 摘要单独标记。JEV 网页/MCP 入口须显式 live=true，且来源非 private 并获准外发才在线；配置密钥不会自动请求。scripts/verify_jev.py --live 用于显式联调。关键数据已切换到项目 F 盘，10 服务部署审计通过；单机即时健康不代表独立冷启动。最新记录见 docs/19-deployment-review.md。

## 7. 判定和版本

当前 `ontolens` CLI 提供 decide、eval、promote 三个命令，旧 `peiwu` CLI 保留兼容入口。工作台的 decision_check 使用版本快照调用相同判定器。v1、v2、v3 和 H01–H60 是冻结教学基准；当前 v2 在 60 条合成留出上 exact_match=60、unsafe_release=0，v3 候选被门禁拒绝。

这些数字只说明合成规则基准可复现，不是行业准确率，不是模型准确率，也不是现实事故减少率。

## 8. 变更和可追溯性

操作者可从已定位的合成来源提出授权字段候选。系统先预览受影响的历史申请，经过冻结基准检查后才能在合成演示空间发布；发布会创建新快照，旧运行记录仍指向旧快照。回滚只能回到历史祖先，且要求确认说明。

演练版本标注资料性质。管理员可显式发布已检查的业务候选；真实规则是否适用于本单位仍须领域审核和独立复核，当前未完成。

## 9. 评测计划

正式实验需要与人工字段表 + 表连接、普通文档检索、固定图谱和全量重建四类基线公平比较，并单独测原始 PDF/表格/图片处理误差。主指标是固定人工审核预算下正确修复的受影响业务问题比例，另报来源定位、路径正确率、冲突发现、人工耗时和各类安全错误。

软件业务操作与合成规则基准分别验收；真实行业评测、领域金标准和盲测尚未开始。

目录还提供 5 条资产识别合成回归夹具，当前实体、关系和有效期 schema 候选在该夹具上均为精确匹配。报告由 scripts/evaluate_assets.py 生成；该结果不能写成真实行业识别准确率。

## 10. 复现和限制

已准备的本机演示先运行 `start-demo.ps1`；仅预检可传 `-CheckOnly`。入口复用现有令牌、数据库和 Agent 配置，在执行 Compose 前核验关键挂载，并等待数据库和数据处理 API 就绪。该入口不安装依赖、不迁移数据、不新建模型；首次准备与独立冷启动另行验收。

    .\\.venv\\Scripts\\python.exe -m pytest -q
    python tests/browser_smoke.py --url http://127.0.0.1:8765
    .\\.venv\\Scripts\\python.exe tests/mcp_smoke.py --url http://127.0.0.1:8765/mcp/
    .\\.venv\\Scripts\\python.exe scripts/evaluate_assets.py --output artifacts/asset-recognition-report.json

浏览器冒烟覆盖四种决定、证据弹窗、导出、资料导入/搜索、候选发布、回滚、基准、历史和移动端。使用 .venv/Scripts/python.exe scripts/validate_local.py 自动创建隔离数据库，不清空日常演示记录。持续模型调用预算、真实资料适用性和专业审核仍待验证。

## 11. 赛题评分映射

| 赛题 3 要求 | 当前证据 | 仍需补 |
| --- | --- | --- |
| MCP/Skill 深度集成 | 2026-10-09 gpt-6-sol（model_id=2）绑定、Docker 业务流与 Agent2 无工具解释；七 MCP 和 Agent1 工具编排来自2026-10-08历史收据 | 外部冷启动、当前模型工具编排复现、长期稳定性和真实资料运行 |
| 数据资产业务价值 | 证据账本、版本快照、合成历史核验 | 真实任务、资料授权、领域审核 |
| 低资源本体算法 | 版本关系模型和变更预览接口 | 明确候选算法、基线、金标准和盲测结果 |
| 交互与能力沉淀 | 本地网页、复现导出、审计与回滚 | Nexent 页面复现、可交接运行和真实评测 |

表中“仍需补”不能用合成数据或模型自评替代。

## v0.4.0 业务工作区与 D1.1 当前范围

业务入口为 `start-operational.ps1`，默认 8768；Nexent 宿主 Web 为 13000、容器内部 3000。四角色 admin/operator/reviewer/viewer 由服务器检查，审计身份来自登录账户，不代表专业资质。六台账 people/chemicals/lots/cabinets/issues/rules 导入保留六原始和六规范化来源，只创建候选；管理员检查、预览并显式确认发布，expected_active 拒绝并发覆盖。历史/复核/导出绑定原运行和快照，追加复核不改决定。

普通解释对私有或未获准来源只发送固定枚举和计数摘要；2026-10-09 当前部署收据记录的是 gpt-6-sol/model_id=2 与 Agent 2 的无工具/记忆隔离。2026-10-08 12:02–12:04UTC 的七 MCP 工具与 Agent 1/model 1 编排、以及早先 Agent 2 自动 search_memory 发现，均是历史收据，不能把旧 tool_calls={} 当作当前绝对零工具。

D1.1-7 保留品牌旁折叠按钮、边缘拖动及键盘调宽，删除冗余侧栏卡和底部控件。九个单选控件与四个日期控件各有 6/6 隔离交互测试通过，0 页面错误、0 外站请求；收据为 `artifacts/workbench-select-interaction-report.json` 与 `artifacts/workbench-date-interaction-report.json`。这不是实际读屏、真实设备或行业效果验收。P10 使用当前首页结构示意，不冒充本轮 ALLOW 核验。

最终软件收据：`artifacts/local-validation-report.json` 为 passed，464 passed、7 stages exit 0、158 项输入指纹一致，快照目录为 `artifacts/source-validation/20261009-094214-e5337f3f/`。部署与边界见 `docs/38-operational-deployment.md`，规划见 `docs/37-teammate-handoff.md`。官方模板姓名、认证与行业效果不得自行填入。


## v0.4.0 公开与命名迁移验收（2026-10-09）

`artifacts/local-validation-report.json` 为 `passed=true`：`.venv/Scripts/python.exe -m pytest -q` 返回 **464 passed in 166.48s**，browser、MCP、assets、JEV、pip、JavaScript 六项与 pytest 共七阶段均 exit 0；最终快照为 `artifacts/source-validation/20261009-094214-e5337f3f/`，输入指纹 158 项一致。

`artifacts/operational-deployment-20261009-ontolens.json` 为新 OntoLens Docker 部署 passed，35 项检查通过；验证 ontolens 入口、新配置、请求头、真实 Agent 2 解释与重启持久化，`real_industry_data_used=false`。既有 Nexent 机器 ID、schema 与档案名保留兼容，平台未重新登记；行业适用、专业审核、独立评测、外部冷启动、长期稳定性及正式提交仍未验证。
