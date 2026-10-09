# 来源资料与版本发布

D1.0 · 2026-10-09 · 来源与版本合同已在当前实现中保留；专项和完整交互验收状态以D1.1变更记录为准。

[返回设计规范目录](README.md)。MUST/SHOULD/MAY 强度见[产品原则](01-product-principles.md)。

## 资料是来源，版本是生效快照

上传保存来源原字节、性质和片段；候选提出有限变更；预览说明影响；发布改变active快照。这四个事件 MUST 不合并成“已审核”。
资料列表行 SHOULD 按标题/性质/可用片段/来源定位组织；选中读取失败保留原列表，不能清空后冒称无资料。
普通检索/JEV明确范围，业务台账候选与synthetic变更分开，公开制度不自行授予人员权限；导入须检查预览与显式发布。
文件名和原文超长 MUST自然换行且完整可访问，模型/引用解释属于派生内容，不替代原文件。
用户可查看已实现的来源建议/资产/本体草案；MUST标明候选、人工摘录、未核验等性质，不将草案图标呈现为已审核事实。

## 发布回滚的渐进步骤

| 步骤 | 必须展示 | 恢复与写入边界 |
| --- | --- | --- |
| 提案 | 当前parent、人、classes、来源与定位、日期、说明 | 无保存确认前保留表单，来源变更清locator |
| 预览 | 当前/目标版本、受影响记录、前后动作/数量 | 读取失败可重试，不直接进入发布 |
| 确认 | 当前业务/合成范围、expected_active及目标 | 默认未勾；业务admin confirm_publish，取消回候选 |
| 写入pending | 正在发布/回滚，当前按钮不可重复 | 不先更新active，不庆祝专业通过 |
| 成功 | API确认与重新读取active一致 | 旧核验stale，历史绑定不变 |
| 冲突 | 当前版本已改变、需刷新后重新预览 | 不覆盖、不自动改expected_active再提交 |
| unknown | 未确认写入；读取versions/audit | 无法排除已生效时不盲重复 |

发布后清除一次性确认，下一次重新核对；回滚显示目标版本及它的原来源，不解释成“撤销所有历史操作”。
日期valid_from/valid_until可空；若均填写，起始不能晚于结束，classes不能重复且只属于既有枚举；说明遵循CandidateRequest长度。
MUST保持事务权限边界：业务发布/回滚仅admin且confirm_publish，synthetic兼容confirm_demo；操作确认不代表专业审核。完整接口见[工程验证](10-engineering-validation.md)。

### 6.2 原始资料

顺序 MUST 为文件→性质/本地与外发范围→可选人工摘录→导入→检索列表→定位原文；导入不等于生效规则。
MUST 保留 `[data-view="sources"]`、`#view-sources`、`#upload-form`、`#source-file`、`#source-kind`、`#source-external`、`#transcript`。
每文件上限 `4 MiB`；性质为 synthetic/public/private，私有资料 MUST 禁用并清除外发允许，其他默认不外发。
图片预览和人工摘录 MUST 标明性质；未配置 OCR 不显示自动识别成功。完整原文与引文不得注入为 HTML。
MUST 保留 `#search-form`、`#search-input`、`#jev-search-button`、`#jev-status`、`#source-count`、`#source-list`；普通检索可离线，JEV 为可选辅助。
列表 SHOULD 呈现标题、性质、日期/范围、可读片段状态与回查动作；公开出处可查看不意味着已获全文再分发授权。

### 6.3 数据版本

业务六表为原始台账/授权说明→候选检查→影响预览→管理员发布/回滚；synthetic授权变更保留来源/日期/说明流程。
MUST 保留 `[data-view="versions"]`、`#view-versions`、`#candidate-form`、`#candidate-person`、`#candidate-classes`、`#candidate-source`、`#candidate-locator`、`#candidate-source-status`。
MUST 保留 `#valid-from`、`#valid-until`、`#candidate-note`、`#candidate-submit`、`#candidate-list`、`#impact-result`、`#confirm-demo`、`#version-list`。
候选来源切换 MUST 清除旧 locator，最新读取完成且匹配来源后才启用提交；类别多选必须有移动可操作路径。
比较 MUST 同屏显示当前/候选版本、受影响记录与前后决定/数量；关键冲突不得折叠隐藏，不能只用红绿差异。
业务明确“发布业务版本/回滚到此版本”，synthetic兼容演示文案；当前/目标范围与expected_active保护，不丢说明。

## v0.4.0六表导入

原始资料业务入口data-open-ledger与ledger-form可达；六组people/chemicals/lots/cabinets/issues/rules，每份1–2,000,000字节，前五JSON/YAML/CSV，rules仅JSON/YAML。
GET /api/ledger-bundles/template提供结构，POST multipart /api/ledger-bundles保存六原文及六规范化来源，检查hash/schema/引用/日期/单位/不变量。失败不发布。
label/basis/purpose/authorized_by/recorded_at/local_operation_authorized只记录授权声明，actor绑定认证，不认证文件真伪或专业资质。六表external_model_allowed=false，非synthetic people为private。
operator可导入/提案，admin发布/回滚，reviewer/viewer按服务端权限展示；UI隐藏不能代替403。
