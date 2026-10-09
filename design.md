# 格物镜 · OntoLens 设计规范

## Overview

v0.4.0 · D1.1 · 2026-10-09。业务空库/认证/台账候选发布与展示首页，保留认可配色和生成Logo；最新侧栏只保留品牌图标折叠、边缘调宽及真实账户操作。
本轮修复了缩放布局和 Nexent 上游错误被误报成功的问题，选择器、日期、业务容器、模型与完整软件验证结果统一见[工程验证](design/10-engineering-validation.md)及[变更状态](design/11-change-control-status.md)。可移植专项收据保存在 `artifacts/workbench-select-interaction-report.json` 和 `artifacts/workbench-date-interaction-report.json`；真实设备、读屏、独立新机与行业效果仍分开记录。

本文件是唯一导航入口，[design/README.md](design/README.md)解释规范层级。精确token仅由[基础规范](design/02-foundations.md)的frontmatter管理，各篇不得复制另一套值。

| 阅读主题 | 规范 |
| --- | --- |
| 产品目标、真实性与任务流程 | [01 产品原则](design/01-product-principles.md) |
| 唯一颜色、字体、空间token | [02 基础规范](design/02-foundations.md) |
| 展示首页、可拉伸侧栏与条件检查器 | [03 工作空间](design/03-workspace-navigation.md) |
| dirty/stale、关系来源联动、异步写入 | [04 核验证据](design/04-verification-evidence.md) |
| 资料权限、候选、影响、发布与回滚 | [05 来源版本](design/05-sources-versions.md) |
| 复核追加、历史、基准与模型边界 | [06 复核历史模型](design/06-review-history-models.md) |
| 状态反馈、动效、日期与减少运动 | [07 动效](design/07-motion-feedback.md) |
| 键盘、焦点、触控、日期、缩放与窄屏 | [08 无障碍响应式](design/08-accessibility-responsive.md) |
| Logo、图标、alpha与出处 | [09 品牌资产](design/09-brand-assets.md) |
| 接口兼容、30项原合同与10项侧栏验收 | [10 工程验证](design/10-engineering-validation.md) |
| 允许变更与未完成状态 | [11 变更状态](design/11-change-control-status.md) |
| 164项已咨询入口、取舍与能力缺口 | [12 技能讨论](design/12-skill-discussion.md) |

MUST为必须、SHOULD为建议、MAY为可选；分篇共同构成D1.1合同，未修订的D1.0数据/交互保护继续有效。技能默认模板不能覆盖用户现行方向。
默认业务入口可接授权台账；synthetic仍显式保留。授权声明/一次调用/软件通过不证明行业效果或专业审核。部署步骤见[业务说明](docs/38-operational-deployment.md)。
本规范不授权仓库推送或正式发布。[讨论交接索引](docs/38-design-council.md)只链接上述规范，不另建产品权威。
