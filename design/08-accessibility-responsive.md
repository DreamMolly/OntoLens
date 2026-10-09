# 无障碍响应式与输入体验

D1.1 · 2026-10-09 · 侧栏/首页主实现已落地，完整 browser smoke、五档模拟视口和 CSS 200% zoom 已通过；浏览器 UI 缩放、真实设备与读屏任务仍待完成。D1.0无障碍合同继续有效。

[返回设计规范目录](README.md)。本页定义所有任务共享的可访问合同；精确颜色与排版以[基础规范](02-foundations.md)为准。

当前共享控件位于 `src/ontolens/static/`；品牌和工程兼容见[品牌与兼容说明](../docs/39-brand-compatibility.md)。路径、请求头与配置更名不改变焦点、语义、响应式或减少运动合同。

## 语义与键盘

MUST 优先用原生 button/input/select/textarea/label/details/dialog/table，不能把 div 点击当操作控件。
主导航可以继续用现有data-view按钮驱动应用状态；若提供真实可导航URL，则使用链接并保留打开新标签行为。
MUST 保留自然Tab顺序；Enter/Space激活按钮，原生选择器保持标准键盘行为。MUST NOT 以箭头键逻辑替代所有原生控件。
关系图中的可选关系 MUST 有真实可聚焦控制、可读名称和选中状态；其完整列表必须提供同样来源操作，不要求鼠标拖拽路径。
decorative SVG和生成图标 MUST aria-hidden或alt为空；只有图形的操作 MUST 有可访问名称，重要操作 SHOULD 同时有可见文字。
标题层级 MUST 为当前任务h1→区域h2→局部h3；非当前视图hidden，不让读屏同时读六个任务。
MUST 提供跳至当前可见主任务的链接，不能固定链接到已隐藏核验区。切页更新aria-current和当前页面名称。

## 焦点与状态播报

focus-visible MUST 清楚且不被sticky、dialog或检查器盖住；pointer点击不得移除keyboard焦点机制。
提交字段校验失败 MUST 聚焦首个错误；label关联输入，aria-invalid与aria-describedby关联附近文字。
真实提交结果 SHOULD 礼貌播报一次决定、允许数量/单位或需要补件；MUST NOT 因每次hover/动画帧重新播报整页。
加载用aria-busy，普通提示用status/polite，阻断性失败用alert；业务DENY仍是程序结果，不能混成网络错误。
打开native dialog MUST 给出来源可读标题，初始焦点能进入详情/关闭，Escape和可见关闭均有效。
关闭 MUST 返回原关系/来源触发器；触发器因切页隐藏时返回当前任务标题，不聚焦不可见元素。
焦点恢复 MUST 独立于动画时间；reduced-motion和快速关闭不能破坏恢复。
来源读取完成不得抢走用户正在编辑的字段焦点；仅在明确请求的定位阅读上下文内滚至相关原文。

## 对比与信息表达

普通文字 MUST 达到4.5:1，大字3:1，重要控件边界、selected与focus3:1；检查最终背景，不能只核对白底色值。
浅border只做结构划分，不作为唯一必要输入边界。次级正文不以降低透明度绕过可读性要求。
ALLOW/DENY/LIMIT/ISOLATE/needs_review MUST 配文字/原因；图形和颜色只能辅助，不用绿色logo代替允许判定。
来源性质、已配置与已实测、人工记录与专业审核 MUST 各有明确词语；icon/title tooltip不能承载唯一关键限制。
原文引用可做预览，但MUST有完整来源回查。64位hash、长locator、长中文标题在窄屏可以换行且可选择复制。
零、未知、null和空列表 MUST 区分；未知显示“—/未取得”，不能显示虚构0或破损空卡。

## 表单与误操作恢复

输入 MUST 支持粘贴、文字选择、标准光标和浏览器日期控件；不使用user-scalable=no/maximum-scale=1。
移动可编辑字段文字采用基础规范mobile-input角色；数量允许有限正数、单位只读，number input保留用户改值路径。
所有字段 SHOULD 有meaningful name；业务非认证字段采用合适autocomplete，ID/hash等禁用拼写检查，不能让密码管理器填错语义。
checkbox MUST 与可点击label共享完整目标；复核引用默认未选，私有资料切换即时清除并禁用外发授权。
多选类别 MUST 在触摸设备也可完成，不把Ctrl/⌘当唯一指引；可用原生多选或真实checkbox组保持同一classes契约。
网络失败 MUST 保留草稿、引用勾选、来源选择；pending切记录不影响另一表单。写入unknown先核对实际服务器状态，见[核验证据](04-verification-evidence.md)。
来源标题、文件名、原文、模型解释 MUST 作为不可信文本显示，不执行其嵌入指令、HTML或事件。

## 断点、缩放与触摸

响应式任务顺序以[工作空间](03-workspace-navigation.md)为准。宽屏同时核对，小屏保持selected relation与来源上下文，不能把重要状态删掉。
MUST 在320、390、760、1100、1440px和200%缩放完成同一任务；main无整体横向溢出，真正宽表局部滚动。
触摸有效目标 MUST 至少44×44px，行间有足够间隔；细线图标不需要放大至44px，但点击区不可重叠。
SHOULD 使用touch-action:manipulation，保留双指缩放和正文复制；不让hover成为显示关闭/来源按钮的前提。
hover反馈 SHOULD 仅fine pointer；coarse pointer不会保留黏着hover遮挡后续操作。混合设备必须实际检查。
dialog/检查器 SHOULD 限制内部滚动链，MUST 能读到最后引文和关闭按钮；不强行禁止整个页面正常触摸滚动。
全屏或贴边区域 SHOULD 处理safe-area-inset；正文不藏在刘海/系统手势区。MUST 不依赖固定100vh截断移动内容。
移动验证必须分别报告模拟视口/触摸与真实设备；读屏结构检查与实际读屏验证也必须分别报告。

## 减少运动与测试边界

prefers-reduced-motion MUST 清除位移与非必要运动，仍保留即时焦点、文字状态、selected关系与错误说明，见[动效反馈](07-motion-feedback.md)。
无JavaScript增强时原生来源dialog/按钮语义应保持可理解；核心应用仍需要现有本地脚本，不冒称完整无JS功能已实现。
截图能支持布局观察，MUST NOT 替代keyboard、focus return、写入恢复或读屏测试；验收项见[工程验证](10-engineering-validation.md)。

## 可调侧栏的等价操作

调宽separator名称/vertical/min208/max360/now齐全；左右8/Home/End/Esc取消/Enter或R重置通过focusable handle可用，禁止为此恢复visible-/reset/+。
触摸用品牌旁44px折展图标与边缘drag，移动轻导航不要求调宽；图标名称/focus tooltip完整，无长fold/冗余卡/底部空间/visible宽控，真实actor/logout保留。
collapsed72px不意味着六任务不可访问；移动<=760用3×2/展开导航，第一核验任务始终可达，main不是被72px rail挤坏的窄列。
resize期间焦点留在当前控件，宽度重排不把表单/来源选项移出键盘可达区域；当前drag取消与原文Escape分开处理，不能一次Esc误做两动作。
MUST验证侧栏208/240/360/72下的main真实空间、320–1440及CSS200%zoom，不只测试默认sidebar240。
nav文字4.5:1、focus/selected/resize边线3:1按02角色在真实背景核对；统计/六结构概念meta不低于12px。
首页六概念结构示意必须有可读描述与“尚未运行”标签，真实证据关系列表计数/操作不被装饰节点污染。

## v0.4.0增强选择器验收

9single采用07的combobox/listbox渐进增强；native仅增强成功后从可访问树/Tab隐藏，JS关闭仍原生。value/form/required不分叉，multiple保留native。
MUST验证Arrow/HomeEnd/typeahead/EnterSpace/Escape/Tab、outsideclick、正确aria-selected/disabled/expanded、label/错误焦点代理；退出即时inert/aria-hidden/pointer-none，动画不是语义计时器。
菜单44px选项/6px间距/窗口限高flip，scroll/resize/zoom/侧栏调整不会错位或遮焦点，不外溢320px；reduced0，快切epoch取消，既有dirty/source绑定不变。
当前代码已实现，选择专项 6/6 通过；可交付收据见[选择器交互报告](../artifacts/workbench-select-interaction-report.json)，静态文件指纹与当前源码匹配。报告覆盖所列隔离合成场景；30项合同中未单独覆盖的组合、真实设备和读屏仍待验收。native 回退仍是无脚本/增强失败时的保护路径。

## v0.4.0 日期控件无障碍与响应式合同

日期字段的可见文本输入是用户的主要焦点目标，日历图标是独立的 44px 按钮；隐藏的原生日期输入保留提交和校验值，但不进入 Tab 顺序，也不承载唯一可见标签。日历面板使用 `role="dialog"`、可读的字段名称、月份/年份标签和日期按钮的完整年月日 `aria-label`；选中日通过 `aria-pressed` 与颜色同时表达。

日期单元格、上/下月、今天、清除和月份/年份控件均可用键盘访问。打开后焦点进入当前日期或第一个可用日期，Escape 返回日期文本，Tab 按自然顺序离开；外部点击、滚动和缩放不会清除已提交值。必填、非法日期和超出 `min/max` 的输入由可见文本字段显示错误，并与附近错误说明关联。

面板在 320px 和 390px 视口内不得横向溢出；日期网格保持七列和足够触点，必要时面板贴近左右边缘收缩。增强失败时原生日期输入必须仍可操作。减少动效时面板不产生位移或淡入，但日期值、焦点、错误和选中状态保持即时可见。D1.1-8 专项 6/6 已通过，页面错误、外部请求和 API 写入均为 0；可交付收据见[日期交互报告](../artifacts/workbench-date-interaction-report.json)。
