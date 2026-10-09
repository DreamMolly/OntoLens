# 核验与关系证据交互

D1.0 · 2026-10-09 · 证据与异步合同已在当前实现中保留；专项和完整交互验收状态以D1.1变更记录为准。

[返回设计规范目录](README.md)。MUST/SHOULD/MAY 强度见[产品原则](01-product-principles.md)。

## 先理解当前任务

本页定义关系检证台最重要的合同：被查看的结果必须属于明确输入/快照，原文必须属于选中的关系，人工记录必须属于明确run。三种身份不能靠视觉位置猜测。
MUST 让操作者看到“我正编辑的新申请”“我正看哪次记录”“这个原文支持哪条关系”；current/history/stale可并存，但不能合并成一个成功标记。
申请摘要折叠是节省空间，不是隐藏限制；MUST 可恢复编辑，且任何改值立即进入dirty。

| 当前上下文 | 主操作 | 结果与导出语义 |
| --- | --- | --- |
| 未运行草稿 | 核验并记录证据 | 不显示真实决定/导出 |
| 当前匹配结果 | 修改申请、查看关系 | 本次run可导出与解释 |
| 改过输入的草稿 | 重新核验 | 上次结果可查看，但明确属于旧输入 |
| 历史查看 | 返回历史、明确按此新建 | 导出/复核只对应被看run |
| 写入状态未知 | 查看保存状态/刷新 | 不声称未保存，也不盲重试 |

## 关系与原文的联动路径

关系数据 MUST 来自实际evidence。MAY 用“人员/批次/柜位→授权/库存/规则→决定”的稳定分组组织，但不能把某次缺失的边补成完整图。
每条关系 MUST 显示relation、subject/target与定位入口；缺口显示“原文待补件”，不改成连接正常装饰。
选中同一关系 SHOULD 保持检查器打开、原文定位和标题身份稳定；再点已选关系不能使引用身份错配。
换关系 MUST 在开始就更新selected状态；检查器加载时标清即将读取的来源，旧原文不能继续装成新关系的内容。
当引用被截断作预览，检查器 MUST 提供完整片段及相邻上下文，只有真实locator存在时才高亮定位。
copy hash/定位 MAY 增强，但必须返回“已复制/复制失败”的实际结果，不能假称剪贴板写入成功。
来源关闭恢复selected relation和读到的位置；history切换后不恢复另一run的引用。

### 6.1 核验申请

顺序 MUST为人员/批次/柜位→数量/只读单位/日期→核验；空业务库先导入并发布，synthetic五预设仅填值，不自动决定。
MUST 保留 `[data-view="check"]`、`#view-check`、`#check-form`、`#requester`、`#lot`、`#cabinet`、`#quantity`、`#unit`、`#as-of`。
MUST 保留 `[data-preset="allow"]`、`conflict`、`limit`、`isolate`、`missing` 五个值；缺资料预设使用未登记合成人员是合法演示，不因目录校验拦截。
`#empty-result` 表示尚未运行；`#decision-content` 只呈现真实 run，`#decision-banner`、`#decision-action`、`#approved-quantity`、`#result-version` 显示对应记录。
动作文案保持允许领用/本次打回/限量领用/隔离批次/需要人工复核；业务数量标“本次规则允许数量”，synthetic明确合成，保留单位/approved_quantity，不执行出库。
`#evidence-chain` MUST 用真实 `result.evidence` 生成 `.evidence-node`；一条关系对应一条可回查记录，不为了美观添加不存在的节点/边。
关系 SHOULD 使用稳定路径或矩阵，不用 force、无限画布或拖拽作为唯一入口；完整证据列表 MUST 与图共用同一真实数据。
关系选中 MUST 绑定 source_id/locator/sha256/version_id；原文缺失明确待补件，不能以空白代替。
MUST 保留 `#export-link`、`#explain-button`、`#model-output`、`#decision-json`、`#citation-form`、`#citation-claim`、`#citation-result`。
导出与解释 MUST 绑定所看 run；模型解释置于程序决定之后，字面引用核对不冒充在线语义可靠性评测。
MUST 保留 `#review-panel`、`#review-guidance`、`#review-form`、`#reviewer`、`#review-status`、`#review-note`、`#review-references`、`#review-submit`、`#review-history`。
引用checkbox默认未选，合法缺件quote:null/unresolved:true；业务复核人绑定登录actor，网页随填不能伪造身份；登录不代表专业资质，synthetic无认证兼容路径明确自身范围。

## 7 请求、来源与写入状态机

状态 SHOULD 正交存储：draft revision；request idle/pending/error/unknown；context current/history/stale；source idle/loading/ready/missing/error；review/publish pending/saved/conflict/unknown。
任一 request 字段或 active version 变化 MUST 立即 dirty/stale；旧 ALLOW 标“上次申请的结果”，新草稿标“尚未核验”，0ms 更新，不能等动画结束。
提交 MUST 冻结 payload、requestRevision、requestSequence、activeVersion；只有三项仍匹配且返回身份正确，响应才成为当前草稿结果。
迟到响应 MAY 保留为真实历史记录，MUST NOT 覆盖新草稿、当前所选关系、检查器或其他 run 的复核表单。
viewing_history MUST 有独立被看 run；不得默默把历史 request 填入新草稿。MAY 提供明确“按此记录新建申请”操作并标未核验。
普通读取 MAY AbortController 取消；取消客户端等待不代表服务器写入回滚。来源读取 MUST 再绑定 selection sequence/source/locator。
写入中 MUST 防重复，响应成功且持久化确认后才展示 saved；失败保留草稿、勾选和说明，给原位置重试。
超时/断网且可能写入 MUST 显示 unknown；复核从 `GET /api/runs` 取得相应记录，发布/回滚从 `GET /api/versions` 与 `/api/audit` 核对，核验按提交的request_id查近期保存记录，再判断能否重试。
现有 `/api/runs` 只给近期记录；查不到 MUST NOT 宣称未写入。无法排除重复时保留未知并给查看/刷新入口，不虚构幂等保障。
完整unknown恢复若需要单条run读取、幂等键或更久历史检索，MUST 标为 needs_support；目前不存在的接口不能写成已经支持，新增后须独立验证。
人工复核 MUST 固定 run_id + 选中引用 tuple + note/reviewer/status；旧响应不清空新 run 草稿，也不释放另一提交的 busy 状态。
字段 MUST 用 required、有限 quantity `>0且<=1e9`、日期、长度约束；单位只读。invalid 在字段附近写明原因，提交时聚焦首个错误。
普通状态使用 `role=status/aria-live=polite`；阻断失败使用 alert，pending使用 aria-busy；成功只播报一次，不能让每次关系hover刷读屏。
选择关系 MUST 联动原文定位、高亮和版本；完整引用不依赖 hover，长段原文可滚动但能看完整上下文。
native dialog MUST 有可见标题、关闭和 Escape；打开进入详情的可用焦点，关闭返回触发关系，若原视图隐藏则返回当前工作区标题。
切页只保持一个 aria-current=page；`[hidden]{display:none!important}` MUST 生效，隐藏视图不得残留键盘目标；跳转链接指向当前可见任务。
