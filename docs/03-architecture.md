# OntoLens 架构

当前实现以 FastAPI、SQLite 和确定性 Python 内核构成工作台，Nexent 与 JEV 提供受限辅助。业务部署和状态见[部署指南](38-operational-deployment.md)，界面合同见[设计规范](../design.md)。

## 数据与决定

六类台账保存原始字节、规范化事实、哈希和来源定位；候选先检查引用、日期、数量与规则，再由管理员显式发布。发布和回滚比较 `expected_active`，拒绝并发覆盖。历史核验绑定原版本，不因新发布改变。

申请只提交人员、批次、柜位、数量、单位与日期。授权和已领类别来自服务端快照，申请方不能注入可信事实。`decision_check` 调用 `ontolens.checker`，是唯一业务决定来源。资料缺失、失效或矛盾进入非决定状态。

## 模块

| 模块 | 职责 |
| --- | --- |
| catalog / rules / checker | 目录引用、冻结规则、四种确定性决定 |
| evaluate / gate / counterfactual | 合成回归、候选门禁与变形边界检查 |
| workspace / ledger_import | 原始来源、快照、候选、核验与审计 |
| access / web / mcp_app | 角色权限、会话、CSRF、HTTP 与 MCP |
| ontology / public_corpus | 目录资产、待审关系与公开摘录验证 |
| jev / jev_replay / model_explain / nexent_runtime | 重排、复核信号、录制回放、解释和平台连接 |
| export_verification / review_verification / delivery | 脱库重算、复核绑定与交付一致性 |

CLI 提供 `decide`、`eval`、`promote`。CLI `promote` 返回规则候选检查报告；工作台版本发布由管理员接口承担。

## MCP 与 Skill

`asset_recognition`、`evidence_lookup`、`graph_query`、`candidate_suggestions`、`evidence_rerank_jev`、`decision_check`、`candidate_review` 共七个工具。工具不提供任意 SQL、任意路径读写、发布、回滚或真实出库权限。

Agent 为 `ontolens_compliance_review`，MCP 服务为 `ontolens-local`；Skill 为 `ontolens-intake`、`ontolens-evidence`、`ontolens-decision`。解释实例 `ontolens_result_explainer` 不绑定工具和 Skill，其输出只作辅助说明。

## 信任与模型边界

来源正文视为数据，不能指示工具执行。引用核验先检查快照成员、原始哈希、定位和完整原文；失败不请求 JEV。JEV 的支持/矛盾或影响概率只安排人工复核，不改决定或版本。

在线 JEV 需要显式 `live=true`、非私有来源及外发许可。私有或未获准资料的解释只发送受控枚举与计数摘要。三种解释协议只返回文本，失败保留程序结果。

## 复现与限制

导出包含申请、快照、规则和来源原始字节；离线验证检查闭包、哈希、引用和复核绑定，重新计算决定。本地追加审计不抵御数据库管理员篡改。真实性、专业适用、独立行业评测及持续运行仍有单独验收条件。
