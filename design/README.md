# 设计规范阅读与权威层级

v0.4.0 · D1.1 · 2026-10-09。业务部署与最新界面合同生效，实施验收以11的当前新记录为准。

入口是[根design.md](../design.md)，本目录按任务拆开同一份合同。精确token唯一来源是[02基础规范](02-foundations.md)frontmatter；产品状态唯一来源是[11变更状态](11-change-control-status.md)。

## 如何阅读

- 理解产品先读[01](01-product-principles.md)，页面布局读[03](03-workspace-navigation.md)。
- 核验与异步读[04](04-verification-evidence.md)，上传/候选/版本读[05](05-sources-versions.md)，历史/模型读[06](06-review-history-models.md)。
- 实现视觉读[02](02-foundations.md)，动态反馈读[07](07-motion-feedback.md)，键盘/移动读[08](08-accessibility-responsive.md)。
- 素材生成读[09](09-brand-assets.md)，所有实现需检查[10](10-engineering-validation.md)的接口与30项验收。
- 改动与缺项读[11](11-change-control-status.md)，技能咨询和反驳读[12](12-skill-discussion.md)。

## 规范强度与状态

MUST必须满足，SHOULD允许有记录的内容/场景例外，MAY为可选增强。基础token使用implementation_partially_verified来源标记；实际实施/验收状态按11新回执，不能仅以文档存在声称已完成。
新增可逆组件与修复按已有授权继续，不增加审批步骤；重大设计变化更新同一分篇及对应验收，不让各队友重新选择另一套skill样式。
旧UI/截图只是历史证据，peiwu工程协议与真实业务边界是兼容合同。根目录文件是入口，不保存第二份token。

## 来源与部署边界

[技能讨论](12-skill-discussion.md)记录157社区入口与7原生入口咨询，会员内容和未暴露工具不冒称执行。逐项咨询JSON由本轮汇总代理生成；本机runtime日志不是启动或部署必要文件。
只承认最终实际代码/接口和新验收收据证明实现。所有性能数字是目标预算，真实用户研究、专业审核与完整平台验收单独确认。

业务启动/角色/台账/模型隐私与Docker见[38业务部署](../docs/38-operational-deployment.md)，软件/平台/研究门槛分开，不把所有工作叫合成演示。
