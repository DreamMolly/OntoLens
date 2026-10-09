## 01_cover

格物镜 · OntoLens 是一个面向实验室危化品领用核验的合成演示项目。今天只展示旁路历史核验，不执行真实出库。我们要看的主线很简单：每个程序决定，都能沿着来源证据、关系路径和版本记录回查。

## 02_task

一条领用申请不是一句问题，而是多个时点和来源的交叉核对。这个示例包含人员授权、批次库存、目标柜限制和当日未归还记录。资料缺失、过期或冲突时，系统不会猜一个业务答案，而是返回 needs_review，并把 decision 留空。

## 03_pipeline

四项能力按顺序衔接。系统先导入不同格式的资料，再识别人、物料、批次和柜位，提出待审核的关系或属性候选，最后用证据检索和规则程序完成决定。source_id、定位、引文和哈希从头到尾保留。这里是确定性的低资源基线，不是自动 OCR，也不是已经通过行业标准的本体系统。

## 04_trace

以 stu01 的授权记录为例，系统保留 source_id 和 JSON 定位，也保留完整引文和原文哈希。这个来源属于 demo-initial 快照，决定使用 v2 规则，最后得到 ALLOW 100 mL。snapshot_hash 标记快照，source SHA256 标记原文，两者用途不同。external_model_allowed 默认关闭，图片资料只有人工摘录才进入资产链。

## 05_decisions

这些是迁移后真实 Nexent 平台工具回放中的合成样例，统一使用 demo-initial、v2 和 2026 年 9 月 23 日的核验日期。正常的 stu01 100 mL 得到 ALLOW；stu03 因当日已有未归还的 OXIDIZER 得到 DENY；stu01 申请 300 mL 时按规则限到 250 mL；过期批次进入 ISOLATE。未知人员没有业务决定，只有 needs_review 和空的 decision，这不是第五种决定。

## 06_review_cycle

业务台账导入保留六原始及六规范化来源，先检查候选与来源绑定，再预览影响。管理员以明确确认和 expected_active 发布，active 变化时拒绝覆盖；回滚保留旧历史。页面下方 ALLOW 到 DENY 再恢复 ALLOW 是合成授权变化演练，不能作为实际行业审批或专业审核。

## 07_model_boundaries

JEV 在线需要明确 live=true，且只能使用非私有、获准外发的来源。一次合成相关性请求只证明连通性，不是准确率；引用、关系语义和阈值仍待独立验证。解释与 Nexent 编排不能覆盖 decision_check 的决定；私有或未获准资料只提供枚举和计数摘要。

## 08_nexent

当前主包、命令和可见产品名称为 OntoLens。原 Nexent Agent peiwu_compliance_review、Skill peiwu-intake/peiwu-evidence/peiwu-decision 与服务 peiwu-local 仍是既有机器 ID，未重新登记，页面只采用产品名称和职责说明。新镜像收据 artifacts/operational-deployment-20261009-ontolens.json 为 passed、35 项检查通过，包含 ontolens 入口、配置、请求头、真实 Agent 2 解释及重启持久化；使用合成私有夹具，真实行业资料未使用。gpt-6-sol/model_id=2 延续既有中转配置；解释不能改判，外部冷启动与专业审核仍待验证。

## 09_validation

60/60 和 unsafe_release 0 属于冻结合成规则基准，不是行业准确率或盲测。7 是历史 MCP 工具逐项回放数，不等于当前模型一次调用全部工具。命名迁移后本轮全量回归为 464 passed in 166.48s，pytest、browser、MCP、assets、JEV、pip、JavaScript 七阶段 exit 0，158 项输入指纹一致；权威收据为 artifacts/local-validation-report.json，快照为 artifacts/source-validation/20261009-094214-e5337f3f/。OntoLens 新容器收据 artifacts/operational-deployment-20261009-ontolens.json 为 passed、35 项检查通过，real_industry_data_used=false。当前 gpt-6-sol/model_id=2 和 Agent 2 辅助解释延续既有平台配置；JEV 仍须显式 live=true 和外发授权，解释不能覆盖决定。外部冷启动、真实行业资料、专业审核与长期稳定性仍待验证。

## 10_demo

先用独立演练业务库运行 start-operational.ps1，登录后导入六类明示资料，检查候选并由管理员确认发布。随后核验申请、打开原文，追加复核并导出离线重算，保持原决定与版本可追踪。第十页图片是 D1.1-7 当前首页结构示意，六节点尚未形成实际核验，不能当成本轮 ALLOW 100 mL 运行证据。九个单选控件的六条隔离交互测试通过，实际业务资料适用与专业审核仍待完成，不执行真实出库。

## 11_next

当前软件已支持业务资料导入、核验、复核与导出；可部署软件与实际行业效果分别验收。扩大行业结论前仍需经授权真实资料、领域金标准、独立对照、专业审核与持续运行证据。正式提交另需官方模板字段和队员最终讲解，本项目不执行真实出库，也不承诺奖项。
