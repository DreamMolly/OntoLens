# 工程合同与交互验收

D1.1 · 2026-10-09 · 既有30项合同继续有效，首页/侧栏/选择器/日期控件主实现已落地；完整侧栏、200%缩放、设备与读屏验收仍有待验项。历史D1.0结果见11。

[返回设计规范目录](README.md)。MUST/SHOULD/MAY 强度见[产品原则](01-product-principles.md)。

## 8 功能兼容与接口边界

MUST 保留共享 `.nav-item`、`.nav-label`、`.view`、`#breadcrumb`、`#connection-state`、`#notice`、`#active-version`、`#app-version` 的脚本合同；布局类可重构。
MUST 保留 `#source-dialog`、`#close-dialog`、`#dialog-title`、`#dialog-meta`、`#dialog-image`、`#dialog-chunks`；原生来源查看仍可用。
现有 overview IDs MAY 变为对应资料/记录视图的实际计数或兼容节点；JS不得查询不存在的节点，计数未知是“—”，不得伪造0。
MUST保留核验/来源/候选/回滚/关闭来源语义，业务发布明确“发布业务版本”，synthetic兼容演示文案；不将全部功能叫local demo。
读取接口：`GET /api/status /api/catalog /api/documents /api/documents/{id} /api/evidence /api/graph /api/runs /api/versions /api/audit /api/evaluation`，MUST 不因视觉重构修改语义。
来源已实现读取还包括 `/api/documents/{id}/suggestions`、`/assets`、`/file`和`/api/ontology`；MUST保留其真实功能及“候选/草案/预览”范围，不因新版设计遗漏。
`POST /api/check` 使用 CheckRequest：request_id/requester_id/lot_id/destination_cabinet_id/quantity/unit/as_of/version_id；`/api/runs/{id}/export`仍为GET原记录导出。
`POST /api/documents` 为 multipart file/kind/transcript/allow_external_model，不设JSON content-type；候选 `/api/candidates` 使用 CandidateRequest 保留 parent/source/locator/classes/date/note。
publish/rollback用expected_active/note；业务admin confirm_publish:true，synthetic兼容confirm_demo。review四状态/引用tuple保留，认证actor覆盖网页随填reviewer。
review_status 四值 MUST 保留 queued/in_review/evidence_requested/closed_no_decision；引用为 source_id/locator/sha256/quote/unresolved，不允许客户端注入 action。
JEV payload增加live显式授权；/api/runs/{id}/explain遵守private摘要，/orchestrate为tool-free Nexent；GET /api/integrations/nexent当前观察，均不改/api/check。
客户端 MUST 保留 CSRF token、`X-Peiwu-Token`、同源调用和安全textContent输出；凭证只在受控本地配置，不写HTML/素材/公开收据。

## 11 工程与性能预算

MUST 保持当前vanilla HTML/CSS/JS、本地资源与离线核心；设计不要求React迁移、在线字体/图标、Canvas截图应用、Figma/Canva或host-only widget。
CSP MUST 保持同源边界：`default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'`；新增行为写外部本地JS/CSS，不放inline代码绕过策略。
关系布局 SHOULD 确定、有限、容器响应；选中重绘局部，不因每次输入重跑force或全页面DOM。脚本保持defer，图片设尺寸避免跳动。
未来性能预算：按压/选中反馈100ms量级，本地操作400ms量级，CLS<0.1、logo最终资源<=100KiB、首屏静态总量建议<=300KiB；这些是目标，MUST NOT 冒称已测。
模型/网络耗时 MUST 独立记录和显示；不能拿本地UI响应速度宣传模型服务延迟。静态体积目标可因清晰度调整并记录。
私有引文、复核备注和凭证 MUST NOT 默认写localStorage；MAY 保存最小化非敏感会话选择，新增持久化需明确范围/清理方式。

## 12 交互与设计验收矩阵

以下每项 MUST 用最终实际运行界面验收，保留结果/失败证据；截图mockup、静态代码和技能咨询不能替代交互验证。

| 编号 | 操作/状态 | 必须满足的观察 |
| --- | --- | --- |
| 01 | 六视图导航及返回 | 当前项唯一、隐藏视图不入Tab、草稿/选择保持 |
| 02 | synthetic五预设填值 | 仅填值，缺资料可提交；业务空库不填demo |
| 03 | 正常申请 | 正确ALLOW、实际数量单位、原快照与真实证据 |
| 04 | 冲突/超量/过期批次 | 分别DENY/LIMIT/ISOLATE，原因与数量正确 |
| 05 | 缺资料 | needs_review、decision=null、阻塞字段与补件可读 |
| 06 | 已有ALLOW后编辑任一字段 | 即时dirty，旧结论不代表新草稿 |
| 07 | 核验等待期间编辑 | 三重绑定，迟到结果不覆盖新草稿 |
| 08 | 快速重复提交 | 正确busy与防重复，不虚假成功 |
| 09 | 数量非有限/零/过界、日期错误 | 字段原因关联、聚焦首错、草稿保留 |
| 10 | 请求失败和网络未知 | 明确区分，重试前核对写入，保留草稿 |
| 11 | 鼠标/键盘选关系 | 同一真实引用联动，节点固定且列表等价 |
| 12 | 来源请求乱序 | 旧响应不覆盖新source/locator选择 |
| 13 | 缺quote/locator异常 | 待补件或失败，不伪造原文通过 |
| 14 | 来源详情Escape/关闭 | 焦点与选中关系返回，完整原文能读 |
| 15 | 导入/私有与外发 | 4MiB边界、私有不外发、摘录性质明确 |
| 16 | 普通搜索无结果/读取失败 | 空结果与错误不同，普通检索独立可用 |
| 17 | 候选来源切换 | 旧locator失效，最新完整读取后可提交 |
| 18 | 影响预览与取消发布 | 前后数量/动作可比，取消不丢说明 |
| 19 | 发布/回滚/CAS冲突 | 业务admin confirm_publish/合成确认，冲突不覆盖 |
| 20 | active改变后旧结果 | 即时stale，历史快照与原文保持 |
| 21 | 复核默认引用 | 默认全不选，逐条选择正确tuple |
| 22 | 复核失败/未知网络 | 草稿勾选保持，查询保存状态后重试 |
| 23 | 复核等待切另一run | 不清空新草稿，不错误释放另一个busy |
| 24 | 查看历史再回草稿 | history/current隔离，选择/滚动可恢复 |
| 25 | 导出/模型/JEV不可用 | 原run导出正确，解释不改判，禁用原因可见 |
| 26 | 320/390/760/1100/1440、200%缩放 | 无全页溢出、44px目标、同语义与完整任务 |
| 27 | 长中文/64位hash/空列表/大数 | 无截断关键信息，单位、空值、原文完整可访问 |
| 28 | 键盘与reduced-motion | 焦点清楚、读屏一次状态、运动0ms但反馈完整 |
| 29 | logo及说明素材 | 真alpha、裁切、16/32/64px、出处与hash一致 |
| 30 | 离线/CSP/控制台 | 核心无外部依赖、无未处理异常/安全策略违规 |

最终产品实施 MUST 执行适用的现有browser_smoke、test_workbench_flow与JavaScript语法检查，并按最终变更完成 `scripts/validate_local.py`；必须用隔离库，不写日常业务库。
新增交互需要有意义的回归验证；不能只写与CSS常量重复的测试。触摸视口模拟与真实设备、读屏实际测试 MUST 分别报告。
运行截图 MUST 来自最终代码的实际页面，标记日期/视口/状态；旧截图不冒充新设计验收。完整平台与真实业务验收另有门槛。
素材/源码改变后 MUST 核对交付指纹；仅确实更新Word/PPT时执行对应全页渲染与材料一致性流程。`audit_deliverables.py`不是行业效果证明。

## D1.1 首页与侧栏专项验收

以下是新增实际验收，不用D1.0浏览器通过或参考截图推定完成；原30项保护继续回归。

| 编号 | 操作/状态 | 必须满足的观察 |
| --- | --- | --- |
| S01 | 默认首页1440×900 | 大主句/4真实stats/6概念+新logo、主CTA可达；字体/触点不缩小 |
| S02 | 四统计及API失败 | documents/public/runs最近50/needs_review实际值；未知不是0，无假增长 |
| S03 | pointer拖240→208/360 | capture+rAF/clamp，即时一帧，无width动画/业务重请求/草稿丢失 |
| S04 | 拖动Esc/pointercancel | 恢复startWidth、释放drag态、不存中途值；不误关闭来源 |
| S05 | separator键盘 | 左右8/Home208/End360/Enter或R重置240，aria真实，不截字段键 |
| S06 | collapse/expand与reload | 72px图标名称/tooltip完整，expanded width恢复，存储仅2项偏好 |
| S07 | 触摸与删繁 | 品牌44px图标折展，移动轻导航；无长fold/冗余卡/本地空间/visible宽控 |
| S08 | 原文开启时调宽 | main实际空间重排，源dialog/定位/focus/run保持，不挤表单与360检查器 |
| S09 | sidebar多宽+320–1440+CSS200% | body零横向overflow，移动3×2第一任务可达，同语义/12pxmeta |
| S10 | reduced-motion/rapid操作 | 调宽无动画、collapse运动0、focus完整，无串来源/假计数 |

统计复用overview-sources/public/runs/review且只设一份ID；来源source-count独立。未运行六概念用独立DOM类，不添加到真实`.evidence-node`或导出证据。
sidebar preference键必须namespace化且只含expanded width/collapsed；读写存储异常不阻断初始化，未知/旧非法值clamp或用默认，不删其他应用存储。
ResizeObserver监听main应避免读写反馈循环，布局类型只在真实阈值变更时更新；resize不触发核验和model请求。性能结果需实测，不能用rAF存在冒称60FPS。

## v0.4.0业务新增验收

create_app新库默认operational不seed；Workspace类默认seed保留脚本兼容，validator/tests显式synthetic，不对业务库写入smoke。
必须补验auth/session/logout/角色403/会话撤销/CSRF/actor审计，六表原始+规范化导入/失败拒绝，admin confirm_publish/CAS回滚，private模型摘要、JEV获准live、Nexenttool-free/observed_at。
选择控件增强按07验证native value/form/required/disabled、keyboard/typeahead/Escape/outsideclick/anchorflip/reduced，不只测效果；当前专项 6/6 通过，覆盖 9 个 single select，收据见 `.runtime/select-final-qa/summary.json`。该收据为隔离 synthetic fixture，不替代完整30项矩阵。
专项68/45/旧新组合105和6HTTP流程重叠，不加总；本轮全suite/七阶段/容器build/新截图/材料一致性待最终回执。

## D1.1-8 日期控件专项验收

| 项目 | 验收内容 | 当前状态 |
| --- | --- | --- |
| Date-01 | 四个日期字段保留原生 ISO value、required/min/max 和表单提交 | 通过 |
| Date-02 | 日历面板、月份/年份切换、闰年和 UTC civil-date 计算 | 通过 |
| Date-03 | 键盘移动、Enter/Space、Escape、Tab、外部点击和焦点恢复 | 通过 |
| Date-04 | 非法日期、范围边界、清除/今天和错误说明 | 通过 |
| Date-05 | 320/390px、向上翻转、滚动/缩放重定位和无横溢出 | 通过 |
| Date-06 | 160ms进入、100ms退出、快速中断和 reduced-motion | 通过 |

日期控件实现文件为 `src/peiwu/static/date-controls.js`，功能编号为 D1.1-8；页面 `style.css`/`index.html` 当前使用 `D1.1-14` 查询串仅做缓存失效。专项收据为 `.runtime/date-picker-qa/summary.json`，测试使用隔离合成工作区，不证明真实业务日期适用性。

## 2026-10-09 CSS Zoom 修复验证

隔离 Chromium 探针复现 1440px 视口在 200% CSS zoom 时 `scrollWidth=1470`：证据示意图容器在布局切换瞬间收缩，而固定 116px 的绝对定位 `.map-core` 仍向两边绘制。中心节点与图片现按容器比例限制宽度并保留方形比例，最大尺寸和正常桌面外观保持一致，不依靠页面裁剪掩盖溢出。

修复后同一探针 `scrollWidth=clientWidth=1440`、越界节点和页面错误均为空，收据见 `.runtime/date-picker-qa/zoom-200-fixed.json`；日期与选择器回归 `12 passed in 44.35s`。本轮完整 `tests/browser_smoke.py` 在第 327 行因候选定位器保持 disabled 提前失败，未到 zoom 断言，因此不能声称完整 smoke 或原生浏览器 UI 缩放验收通过。
