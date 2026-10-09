# OntoLens 建设规划入口

当前规划与状态以[里程碑](37-teammate-handoff.md)为准。本页列可持续建设的模块及验收方法，不按人员分工组织。

| 范围 | 源码或文档 | 验收重点 |
| --- | --- | --- |
| 核验与规则 | `src/ontolens/`、`data/rules/` | 四决定、缺件边界、冻结基准与独立重算 |
| 来源与版本 | `workspace.py`、`ledger_import.py` | 原字节、定位、候选检查、管理员发布与并发比较 |
| 权限与部署 | `access.py`、`deploy/`、`docs/38-operational-deployment.md` | 角色、会话、CSRF、私有资料、持久化 |
| 界面与体验 | `src/ontolens/static/`、`design.md` | 侧栏、表单、证据联动、键盘、日期与减少动效 |
| 平台与模型 | `skills/ontolens/`、`nexent/` | 实际工具调用、Skill 绑定、解释不改判 |
| 资料与研究 | `docs/12-data-contract.md`、`docs/13-evaluation-protocol.md` | 授权、标签、公平基线与行业适用 |
| 材料与复现 | `submission/`、`artifacts/` | 实际数字、复现命令、证据范围与正式模板 |

后续优先完成真实任务验证、独立新机部署、读屏与真实设备、备份恢复和长期负载；新增能力应有对应的失败用例与可重跑证据。
