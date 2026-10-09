# 动效与真实状态反馈

D1.1 · 2026-10-09 · 侧栏、首页、选择器与日期控件主实现已落地；完整交互验收仍有待验项。D1.0原生检查器即时关闭例外继续有效。

[返回设计规范目录](README.md)。MUST/SHOULD/MAY 强度见[产品原则](01-product-principles.md)。

## 动效的任务边界

本页的motion是操作反馈，不是页面装饰。MUST先真实更新数据身份，再显示局部视觉变化；即使动画被取消，状态仍然正确。
决定色、允许数量和stale标签承载业务含义，MUST不延迟；原文检查器的短位移只解释它来自所选关系。
请求没有报告进度时只显示pending/busy，不设计分阶段运行故事。模型无streaming合同就一次展示真实响应，不伪打字。

## 9 动效合同

动效 MUST 由真实动作/状态变化触发，用于确认选择和保持上下文；决定、stale、错误、数量、单位与成功事实 MUST 瞬时真实更新。
默认 easing 为 `cubic-bezier(.23,1,.32,1)`；按压 `ease-out`；每次新状态可打断旧过渡，但不能取消数据身份和焦点合同。

| 触发 | 变化与目的 | 时间 | 限制 |
| --- | --- | --- | --- |
| 指针按压 | 局部背景/边线确认输入 | 100ms | 不缩放文字，不移动触点 |
| 关系选中 | 固定路径描边与对应来源浅底 | 120ms | 节点坐标不漂浮，文字立即正确 |
| 检查器进入 | opacity、translateX最多8px | 180ms | 先稳定排版，不动画width/height |
| 原生检查器退出 | 立即关闭并返回关系上下文 | 0ms | 原生语义、焦点与点击/Tab释放优先；见下方例外 |
| 复核真实保存 | 新记录局部opacity反馈 | 160ms | 不强制滚动，不先清空草稿 |
| 当前结果更新 | 摘要边线/浅底可轻反馈 | 120ms | action/quantity/data在0ms更新 |
| dirty/stale/错误 | 明确文字、静态标记、字段原因 | 0ms | 不延迟安全语义 |
| 页面切换/首次加载 | 默认即时；保持任务上下文 | 0ms | 不做整页入场和瀑布动画 |

`prefers-reduced-motion:reduce` MUST 将全部位移和运动时长归零；选中、状态、焦点和文字仍完整即时存在，不以淡入作为必要信息。
动画 SHOULD 仅用本地 CSS transition/原生 Web Animations API，限制 opacity/transform；不为动效引入远端运行依赖。
MUST NOT 动画允许数量、概率和计数，不伪模型打字、假百分比、假逐步完成、粒子、force graph、自动pan、视差或滚动劫持。
pending超过约250ms MAY 出现预留尺寸的中性读取占位与真实busy文本；不人为延迟请求，不让 skeleton冒充数据。

## 中断、减少运动与失效恢复

连续选择A→B→C时 MUST 中断前一视觉过渡，只有C的selection sequence允许展示其来源；过渡完成回调不可写业务数据。
检查器enter尚未结束就关闭，MUST即时执行关闭语义并返回焦点；exit动画不得让dialog在关闭后继续拦截点击/Tab。
MUST NOT 通过setTimeout“等动画完再提交/改判/清空表单”。动画只读真实状态，写请求由明确用户动作与接口返回驱动。
reduced-motion时用户操作、数据替换、focus return、aria-live与selected路径保持完整；不是删掉检查器或默认关闭证据。
未支持动画增强的浏览器 MAY直接显示/隐藏；MUST保留原生dialog、按钮和[hidden]行为，不能让特效失败阻止核验。
opacity/transform SHOULD局部作用于检查器内容/新增记录，不让整个决定/表单每次响应先消失。
MUST预留可读pending区或稳定容器，成功/失败反馈不导致用户按压中的按钮跳走；不动画width/height/auto或强制测量滚动高度。
表单字段错误与stale标记静态呈现，不做震动/闪烁；ALLOW不触发庆祝、烟花、全屏成功或安全印章。
按压颜色不等于成功；真实确认失败后保留可读错误和恢复操作，不能让短暂绿色动效成为唯一反馈。

## 具体动效验收

- 选中关系时保持节点坐标和标签清晰，原文身份始终一致；连续快速切换不会交叉引用。
- pending按钮防重复，量值/单位在响应匹配时一次真实替换，没有假计数或加载百分比。
- native dialog开/关及中途取消均能用Escape，关闭后焦点回可见触发源。
- 切换prefers-reduced-motion后全部位移/运动归零，仍能识别current/stale/history与所选引用。
- 失败/未知写入不会播放“已保存”成功反馈；只有持久化确认的新复核记录出现保存反馈。
- 200%缩放和窄屏没有动画引起遮挡、外溢或控件跳动；性能目标见[工程验证](10-engineering-validation.md)。

## 原生检查器即时关闭例外（2026-10-08）

本实现同时使用桌面原生非模态 dialog 停靠和窄屏模态 dialog，并在关闭时同步释放检查器列、恢复焦点与原生交互。D1.0 明确采用 0ms 原生关闭作为可访问性例外，不将其列为未完成动效。
CSS discrete display/overlay 支持本身不证明该停靠/重挂载路径具有可靠退出动画。为了保留120ms画面而延迟 close、保留拦截层或复制原文幽灵面板，会增加焦点、重复ID、快速换来源和过期内容风险；本实现不引入这些机制。
进入仍为180ms局部反馈，关闭、Escape和连续换来源的语义立即生效；减少运动下全部位移归零。以后只有在不延迟close、不拦pointer/Tab、不镜像来源且保持选择序号绑定的实际验证成立后，才可恢复可选视觉退出；不得仅以CSS.supports判定通过。

## D1.1 可伸缩侧栏与首页反馈

拖动/键盘调宽 MUST即时rAF更新几何，width/grid-template-columns/margin不动画、不积累move回调，每帧至多一次最新宽度更新。
折叠/展开 MAY局部transform/opacity160–180ms，空间尺寸一次到位；禁止整页滑动、触点跳动或等过渡后才生效。
reduced-motion MUST侧栏全部运动0ms；折叠、resize、focus/tooltip和主区正确布局仍可用。
Esc/pointercancel恢复startWidth及release捕获/drag态为0ms；reset为0ms；只在完成事件持久化，不每帧写存储。
四统计pending“—/正在读取”，响应静态真实替换；未运行六关系示意默认静态，不假依次验证或百分比。
真实关系/来源/复核延续本页既有反馈合同；dirty/error/quantity/unknown仍0ms，侧栏不延迟业务状态。
MUST验收快速拖动→Esc、pointercancel、折叠中切任务、focus tooltip与原文打开时拖宽；不能串来源/丢草稿/发送新check。

## v0.4.0选择控件渐进增强（已实现，专项QA 6/6通过）

用户明确现有native下拉动效不好看；9个现有single select统一本地vanilla增强，不引入React迁移。native继续拥有value/options/required/disabled/form提交，测试select_option仍驱动同一change；只在增强成功后opacity0/aria-hidden/tabindex=-1，JS关闭或未增强时回原生。multiple暂保留native，不能退成single。
触发器role=combobox与aria-expanded/controls/active-descendant准确，manual popover role=listbox、option的selected/disabled/name完整。选中即时native value+一次change，保持dirty/单位/候选来源/异步保护；highlight不是提交，动画结束不执行语义。
菜单与anchor间距6px、白面圆角8px、option有效高度44px、蓝选中tick；按窗口available height自动flip、最大高度320px并内部滚动，trigger宽度及内容受视口约束，长中文可完整访问。
enter160ms opacity0→1、沿实际展开方向translateY±4px、scale0.98→1，transform-origin跟随方向；exit100ms fade，但inert/aria-hidden/pointer-none与focus语义即时生效。chevron120ms，reduced全部0。
每次开/关/换目标以epoch中断旧motion，禁止依赖animationend/setTimeout写业务状态；快速关闭再开不复活旧选项/旧source。
Arrow/Home/End/typeahead移动，Enter/Space选择，Escape取消且focus回trigger，Tab自然离开；outside click关闭。scroll/resize/侧栏变化重定位或关闭并保持value，不调用业务API。校验/label焦点代理到可见trigger，不能focus隐藏native。
mobile/coarse可保持原生增强回退，触点44px/字段16px；disabled与刷新options立即联动，popover退出不留透明拦截层/旧焦点，源dialog即时关闭例外仍独立有效。
参考公开UIUX/Motion取消式状态转换及RadixSelect keyboard/typeahead/popper/availablewindow与ShadcnSelect文档；未运行独立MotionMCP/会员工具，不以参考库名冒称通路。当前专项 6/6 通过，覆盖 9 个 single select 的同步、键盘、typeahead、required/disabled、翻转、reduced-motion、侧栏/滚动关闭与无写入回归；收据为 `.runtime/select-final-qa/summary.json`。该收据是隔离 synthetic fixture，不代表真实业务或模型效果。

## v0.4.0 日期控件渐进增强（D1.1-8）

四个日期字段（核验日期、台账记录日期、生效日、有效至）使用独立的 vanilla 增强模块。原生 `input[type=date]` 继续保存唯一 ISO 值、`min/max`、`required`、表单语义和后端提交值；增强层只提供可编辑的 `YYYY-MM-DD` 文本入口、日历按钮和日历面板。JavaScript 未加载时仍回退到原生日期控件。

日期面板使用白色表面、细边框、8px 圆角、6px 锚点间距和钴蓝选中日。面板宽度最多 328px，窄屏按视口收缩；日期网格按周一至周日排列，日期触点至少 40px，按钮和月份/年份入口保持可触达。空间不足时面板向上展开，窗口或滚动变化立即关闭面板但不改日期值，避免浮层脱离输入框。

进入使用 opacity/translateY(4px)/scale(.98) 到稳定状态的 160ms 过渡，退出使用 100ms 淡出。Escape、外部点击、Tab、窗口变化立即结束交互语义；动画只影响视觉层，不能延迟值提交、校验或焦点恢复。`prefers-reduced-motion: reduce` 下不播放日期面板动画。

键盘支持日期单元格的左右/上下移动、Home/End、PageUp/PageDown（Shift 加年）、Enter/Space 提交和 Escape 取消；月份与年份可直接编辑，`今天`与可选的`清除`只在明确点击后提交。日期计算使用 UTC civil date，避免本地时区和夏令时造成跨日；闰年、非法日期、最小/最大日期和空值必须回到同一原生校验路径。

当前状态：代码已实现，Node 语法检查通过；日期专项 6/6 浏览器用例通过，覆盖 ISO 同步、键盘、闰年/范围、320/390px、焦点、reduced-motion 和无 API 写入。功能编号为 D1.1-8，页面资源查询串当前为 `D1.1-14`（仅用于缓存失效）。收据位于 `.runtime/date-picker-qa/summary.json`；日期面板不代表日期真实性或业务规则适用性。
