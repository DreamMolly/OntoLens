# 工作空间首页与可调侧栏

D1.1 · 2026-10-09 · 用户参考方向已决策，首页/侧栏主实现已落地；缩放、设备与完整交互验收仍待完成。D1.0数据/异步/来源合同继续有效。

[返回设计规范目录](README.md)。MUST/SHOULD/MAY 强度见[产品原则](01-product-principles.md)。

## 导航及返回合同

桌面侧栏任务项 MUST直接可达，不用“更多”隐藏主要任务。核验默认，来源/版本为更新支线，实验/历史用于理解复现，连接展示环境状态。
MUST 保留data-view的check/sources/versions/evaluation/history/setup及对应view-ID；可以改变顺序和外观，不改变可到达性。
任务导航 SHOULD 有明确容器名称，当前仅一个aria-current=page；breadcrumb为任务提示，不作为唯一切页方式。
来源检查器是局部上下文，不占用顶层导航；关闭回关系，历史详情返回原列表，不跳回初始空页面。
MAY 用非敏感hash/URL状态保存view和筛选，使浏览器返回可恢复；MUST NOT 把私有原文、凭证、复核备注塞入URL。
会话内选择必须保留，但刷新是否持久化是工程新增项，不因UI设计默认声称已有。实际会丢未保存草稿时才提示。
范围/服务状态应邻近工作空间信息；不得用重复横幅、伪数字和装饰性英文标签占据主要操作空间。

## 进入、收起与选择

首次空业务库 MUST引导六台账导入/预览发布，不编造人员库存；synthetic才显示合成预设，预设只填值。
一次结果到达后决定在前、关系随后；MAY收起申请以便原文阅读，但“修改申请”和输入摘要必须持续清楚。
条件检查器 MUST 显示所选关系名称和来源版本；未选中时主区完整使用空间，不展示没有内容的第三栏。
跨断点时MUST保留同一selected relation/run和完整原文数据，只改变布局；不重新请求生成不同的业务决定。
来源页与历史页计数 MAY展示真实记录范围，未知用“—”；全局概览不得使用无来源评分、增长率或收益值。

## 5 壳层、布局与响应式

桌面 MUST恢复深墨可调侧栏及首页四真实统计，遵守用户最新参考，不以技能反KPI/侧栏默认覆盖用户方向；主区保留认可的矿物底/白面/蓝操作。
工作区最大内容宽度 SHOULD 为 `1600px`，边距桌面 `24–32px`、移动 `16px`，主区间距 `24px`。
可编辑申请默认380–420px，内容需要可在360–440px调节；主证据区弹性。原文检查器条件开启约360px，按实际main可用空间决定同屏，不能挤小表单/元数据。
检查器打开时申请 MAY 收为可编辑摘要；MUST 保留申请身份、数量日期和“修改申请”入口，不默默删除字段。
没有选中关系时 MUST NOT 空占第三栏；决定摘要 MUST 在证据路径之前，不被巨大关系图挤出阅读顺序。
MUST按main实际内容宽度而非仅viewport重排：可用>=820px申请/结果两区，原文开启且>=860px可收申请摘要同屏检查器，完整三栏仅实际>=1240px；不足用native dialog。阈值为布局预算，实测不满足时先重排。
viewport<=760px侧栏转轻移动导航3×2/可展开，申请摘要→决定→关系→原文详情；第一核验项和展开入口可达，不保留fixed72px rail挤手机。
`<=390px` 与 `320px` MUST 保持相同功能/状态/语义；导航自然换行，不缩小文字和触点，也不要求悬停。
200% 缩放 MUST 可完成核验、来源回查和复核。表格确实不可重排时 MAY 在独立 `.table-scroll` 横向滚动，不能全页横向溢出。
顶栏若 sticky MUST 不遮住焦点和定位原文；采用 scroll-margin，避免多层固定面板抢占手机视口。
范围提示 MUST来自当前mode：operational_empty引导导入，imported_workspace说明使用当前资料/规则及单位出库审批，synthetic_demo明确合成不出库，不能全贴演示标签。
本地连接、模型配置、JEV 配置及 Nexent 实测 MUST 各自显示状态，不能一个绿点表示所有链路已验证。

## D1.1 首页展示

MUST显示首页主句“把依据看清，让决定可查”，默认34px、按空间32–36px；副句可为“申请、规则与原始资料，在同一条证据链上相遇”。展示优先但不暗示已审核/真实业务完成。
四统计复用overview IDs：documents实际来源数、kind=public公开数、runs返回最近50条数、这批记录needs_review数；来源页source-count独立保留。
每卡范围清楚，未知为“—”，读取失败说明未取得，不能当0；无增长/行业准确率、无虚构收益，图标非序号步骤。
未运行结果区恢复人员身份/物料批次/目标柜位/人员授权/库存记录/核验规则六概念与中央实际生成logo。独立DOM类不占`.evidence-node`计数。
MUST标“结构示意 · 尚未运行”，不是实际Ontology/evidence事实；真实run后依旧实际决定/引用、dirty/history状态。采用已认可新logo资产，不还原旧mark/teal。
1440×900默认首页 SHOULD可完整触达主提交及核心空态，通过合理双字段行/约88px统计高度/去无意义留白实现；正文/字段44px目标与meta12px不退。

## 可拉伸与折叠侧栏

默认240px、展开208–360px、collapsed72px；折叠/展开仅品牌旁44px图标按钮，完整aria-label/expanded/focus tooltip，不渲染长fold/reset按钮，不改view/run/draft/来源。
collapsed保留logo和六功能图标，完整accessible names及focus/hover tooltip；触摸可展开读标签，不hover-only。
MAY持久化width/collapsed两项非敏感偏好，读取容错clamp；不保存私有引文/凭证/草稿，移动切换不覆盖桌面偏好。
右边缘8–12px pointer命中区、resize光标/可发现边线；键盘separator用role=separator、aria-orientation=vertical、tabindex=0、名称、aria-valuemin208/max360/now。
Left/Right每步8px、Home208/End360；Esc取消恢复startWidth，Enter/R在focusable handle重置240。删除visible-/reset/+和底部本地空间文字；触摸用品牌44px图标与边缘drag，移动轻导航无需调宽。
pointerdown记录startWidth/pointerId并capture；rAF应用最新clamped值，pointerup先标commit再release；pointercancel或未commit的lost capture取消至开始值。正常release触发lost capture不得回滚已提交宽度。
width/margin/grid即时一帧更新，不动画、不每move存储；只在pointerup/键盘完成/collapse保存偏好。drag期间短暂禁文本选择，结束恢复。
展开宽度与collapsed布尔分别保存，72px不可覆盖已保存expanded width；键盘keydown即时更新，keyup/完成后再保存，Esc取消不保存中途宽度，事件只作用separator不截获表单方向键。
调宽只布局，不重发业务/来源读取，不清草稿，不抢焦点；Esc取消drag不要同时关闭源dialog，active操作优先。
MUST用main ResizeObserver/container query或等效可用宽度机制；208→360、collapse/expand、200%zoom均能重排，不能挤坏360px检查器/表单。
源区转换保留source/locator/run、native关闭和focus return；未运行草稿不自动收掉，已run收摘要仍有“修改申请”。
折叠可局部transform/opacity160–180ms、几何一次到位，拖宽完全不动画，reduced0。body320–1440及CSS200%zoom无横向溢出。
首页/侧栏改变不弱化旧ALLOW不审批新draft、三重绑定、模型不改判、review引用默认未选与network unknown恢复；不授权Gitea推送。

## v0.4.0侧栏删繁与业务状态

MUST删除“决策证据工作台/来源关系版本”侧栏卡；sidebar-footer只显示真实登录actor/角色与退出，无登录不补假本地身份。调宽handle保留键盘提示，不新增visible宽控。
空业务库主页显示六表导入指引，真实统计可以为0但失败是未知；业务快照与synthetic预设模式分开，认证/权限按服务器结果，不能凭UI假设。
