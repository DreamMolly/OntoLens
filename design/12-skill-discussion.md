# 格物镜 · OntoLens 全体技能设计讨论结论

日期：2026-10-08。现行结论版本：D1.1，保留以下D1.0全技能讨论历史。唯一入口为[design.md](../design.md)，本文不建立另一套token/实现权威。

## D1.1用户参考与展示体验裁决

已实际查看用户附件：深色品牌侧栏、首页大主句、四真实统计、居中六概念关系示意。用户明确认为D1颜色线条好但首页不如参考，并要求可拉伸侧栏及比赛前端美观/体验优先。
此次参考和偏好是现行governing direction，MUST覆盖D1.0“移除侧栏/KPI”的旧裁决。保留认可配色/新生成logo，恢复展示结构，而非复制旧teal/旧mark或把技能默认审美置于用户之上。
本轮小讨论已与前端组核对：default240[208,360]/collapsed72、pointer+rAF与键盘8/HomeEnd/Esc/reset、touch44替代、非敏感width/collapse保存。main可用宽度驱动，表单默认380–420且内容允许360–440，不挤小字凑三栏。
四统计仍来自真实API与最近50范围，六概念图明确尚未运行；current/stale/history、三重绑定、review默认引用未选、模型不改判与网络unknown保护不变。
无需再次重读已完成的164入口；原意见在用户现行目标下修订。D1.1主实现已落地，选择器/日期专项已通过，完整侧栏、缩放、设备与读屏验收状态见02/03/07/08/10/11；未声称技能共识或合成测试证明真实行业效果。

## 讨论范围与证据强度

用户要求先咨询文章全部可取得前端技能及OpenAI自带设计相关技能，再从零规划，覆盖交互、体验和动态效果。旧界面仅供功能合同与反面观察，不具有视觉保留权。
文章来源：[前端设计技能汇总](https://mp.weixin.qq.com/s/pLNS3Z6IGkkK-uFdrQOmqA)。文章的包数、价格和版本是当时介绍，当前覆盖以实际源文件和读取收据为准。
本轮社区覆盖157项：156项新安装、1项现有UI UX Pro Max更新；分组为Designer111、其余44、公开Motion1、更新UIUX1。另完整查阅7个OpenAI原生入口。
“咨询”表示完整读主技能并把适用意见纳入方案/反驳；不表示执行全部CLI、用户研究、A/B、审计引擎、云设计工具或取得专业审核。
逐项路径、版本、正文hash和读取证据存于本机咨询收据；这些本机构建记录不是部署依赖。源码交接使用下列可移植上游与canonical技能目录，而非开发机绝对路径。

## 文章16组来源、贡献与限制

| 组 | 当前来源与canonical入口 | 讨论贡献及执行边界 |
| --- | --- | --- |
| Impeccable | [pbakaus/impeccable](https://github.com/pbakaus/impeccable)，`.agents/skills/impeccable/SKILL.md` | 目的/层级/反模板、状态修复；完整技能与适用playbook已读，不批量轮流polish应用 |
| UI Skills | [ibelick/ui-skills](https://github.com/ibelick/ui-skills)，`skills/*/SKILL.md`及现行官网featured对应源 | 可访问、元数据、motion性能、规范提取；按当前实际作者/featured边界覆盖，不把整个动态目录当单一skill包 |
| Taste Skill | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)，`skills/*/SKILL.md` | 刻意字体/留白/差异化；包含当前四入口，拒绝将营销AIDA/随机布局/GSAP强加业务工具 |
| Better Icons | [better-auth/better-icons](https://github.com/better-auth/better-icons)，`skills/SKILL.md` | 功能图标统一网格/语义；技能已读，未假称MCP或下载CLI已运行 |
| UI Design Brain | [carmahhawwari/ui-design-brain](https://github.com/carmahhawwari/ui-design-brain)，`SKILL.md` | 表单/检查器/来源/状态组件模式；主文完整，参考读取范围明确，不声称全部60+目录都审计过 |
| Motion AI kit | [motiondivision/ai-kit](https://github.com/motiondivision/ai-kit)，`plugins/motion/skills/motion/SKILL.md`；[官方说明](https://motion.dev/docs/ai-kit) | 公开MIT技能实际取得/安装/咨询；此前页面超时不代表无公开版。会员性能/编辑工具未取得或运行，不购买/冒称认证 |
| UI UX Pro Max | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)，`.claude/skills/ui-ux-pro-max/SKILL.md` | 更新到`1a2c459b35f26116fd165b0a0f30597f252749ff`并咨询当前可搜索UX/图表/栈指导；保留旧版备份，不把文章旧数据库规模当当前值 |
| Anthropic frontend-design | [anthropics/skills](https://github.com/anthropics/skills)，`skills/frontend-design/SKILL.md` | 从产品任务推导有意图的视觉；不冒称为OpenAI原生skill |
| Vercel guidelines | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)，`skills/web-design-guidelines/SKILL.md`及[Vercel官方界面规则](https://github.com/vercel-labs/web-interface-guidelines) | 主文与后续官方codeload取得的8055字节规则全文已咨询；焦点/缩放/原生控制/动效规则纳入合同，不把正文阅读称为真实运行合规审计 |
| Designer Skills | [Owl-Listener/designer-skills](https://github.com/Owl-Listener/designer-skills)，各分类`skills/*/SKILL.md` | 当前111入口全读及逐项建议，任务/关系/状态/系统/研究边界；没有实际执行访谈、A/B或团队会议 |
| Emil | [emilkowalski/skills](https://github.com/emilkowalski/skills)，当前公共skill目录 | 14个公共入口咨询，动效目的/中断/反馈/细节；付费课程更完整内容未取得，不用旧文章价格推定授权 |
| InterfaceCraft | [interfacecraft.dev](https://www.interfacecraft.dev) | 官方页面已查看，会员技能未取得；明确缺口，不称已调用、不购买、不复制猜测的会员内容 |
| Superdesign | [superdesigndev/superdesign](https://github.com/superdesigndev/superdesign)转向[官方后继skill](https://github.com/superdesigndev/superdesign-skill) | 后继skill已取得/咨询；旧IDE仓库不含有效技能，云CLI/auth/credits未配置或运行 |
| Design Plugin | [0xdesign/design-plugin](https://github.com/0xdesign/design-plugin)，实际安装主入口 | 原创视觉与明确方案；插件/云canvas未启动，不把阅读称成外部设计生成 |
| Make Interfaces Feel Better | [jakubkrehel/make-interfaces-feel-better](https://github.com/jakubkrehel/make-interfaces-feel-better)，`SKILL.md` | 光学对齐、按钮/字体、克制反馈；具体尺寸从本项目任务重新决定 |
| User Interface Wiki | [raphaelsalaja/userinterface-wiki](https://github.com/raphaelsalaja/userinterface-wiki)，实际技能入口 | 可读性、动效/UX和图标规则；不将规则数直接当产品合规证明 |

UI Skills现行featured额外来源包含antfu、rams、Apple设计、interface-design、React/motion审阅等，均在其余44组逐项收据中；同名入口已保持命名与来源区分。
Vercel/antfu远程规则最初抓取发生连接重置；后续从官方仓库codeload实际取得并读取全文，因此该获取缺口已关闭。历史失败保留在本地收据，当前不能继续称“无法取得规则”。

## 七个OpenAI原生入口

| 入口与canonical位置 | 对规范的贡献 | 不能误报的能力 |
| --- | --- | --- |
| imagegen，系统`imagegen/SKILL.md` | 品牌prompt/参考约束、生成后检查、真实alpha、非破坏迭代与出处 | 当前无callable image_gen；用户已授权provider API/CLI fallback，不重复请求；别名不冒称官方型号 |
| visualize，bundled`visualize/.../skills/visualize/SKILL.md` | 真交互示例、可读标记、键盘/触摸与选中反馈 | 无show_widget工具，不把截图mockup、host CSS/Tweak或CDN变应用依赖；此轮不制造未执行可视化 |
| Presentations，primary-runtime`presentations/.../skills/presentations/SKILL.md` | 品牌/事实一致、原生可编辑图表与全页渲染 | 不是网页前端框架；PPT字号/平面版式不直接约束网页，未修改PPT |
| documents，primary-runtime`documents/.../skills/documents/SKILL.md` | 阅读层级、表格、来源与全页检查/结构可访问 | Markdown规范无需Word作者流程；合成真实边界优先于减少披露默认，未修改DOCX |
| pdf，primary-runtime`pdf/.../skills/pdf/SKILL.md` | 图文清晰、逻辑数据与显示结果双检查 | 导出不是可编辑UI和真实交互验收，未创建PDF |
| template-creator，primary-runtime`template-creator/.../skills/template-creator/SKILL.md` | 参考保留与可重复模板的边界 | 用户没请求个人模板，不创建Gallery模板/插件，不把design.md称为Product Design模板 |
| openai-docs，系统`openai-docs/SKILL.md` | 官方文档与provider能力区分 | 未暴露Product Design/Canva/Figma/Sites与官方检索工具不能冒称调用；本机发现目录不是官方云功能验证 |

OpenAI原生技能是图像、交互可视化、Office/PDF质量与模板的不同能力，没有虚构一个隐藏“全部前端设计工具”。当前provider只读模型发现确认2.5-flare/sunburst别名；生成、处理与视觉验收仍在方向锁定之后执行。

## 概念比较与共同裁决

| 整体方向 | 要验证的任务组织 | 代价与选择理由 |
| --- | --- | --- |
| A 关系检证台 | 申请、真实关系、所选原文与决定联动，可直接核对为何支持 | 中等实现成本；选择它体现产品本体/证据机制，条件检查器避免固定三栏拥挤 |
| B 逐项核验/现场核对卡 | 填写→核验→补件连续路径，移动与初用更直接 | 中低成本，但跨来源核对需要多次展开；吸收线性移动阅读，不叠加第二套导航 |
| C 版本案卷/证据记录簿 | 历史索引与单记录深读、复核追溯 | 中等成本，适合记录详情；作为默认可能成为普通文档门户，吸收历史层级而不作为主界面 |

原生组最初提出暖纸“证据记录簿”；其余44组指出可能削弱可操作关系，Designer111进一步指出桌面全drawer拆散依据与结论。原生组接受反驳，方案改为标准web关系工作面、没有纸纹/印章/仪器拟物。
D1.0历史共识是“同时核对”而非固定三栏；当时约300–320px申请、选中后360px原文，并选择移除深侧栏/装饰KPI。D1.1已按用户参考修订侧栏、首页统计及表单空间，该句不再约束布局；同时核对与数据保护继续有效。暖矿物底/白面/石墨/钴蓝保留。
操作钴蓝与ALLOW绿分离；“允许数量”明确为本次合成规则结果，同时保持approved_quantity协议和单位，不换成模糊概念。
候选属于来源更新支线，六视图兼容并不要求等权；current draft、viewing_history和原run追加复核必须隔离。

## 技能意见到规范决定

| 意见来源 | 纳入D1.0的具体合同 |
| --- | --- |
| Designer111任务/架构/状态 | 关系原文决定联动；dirty立即标旧结果；requestRevision/requestSequence/activeVersion三重绑定；历史草稿隔离 |
| 其余44产品/前端/组件 | 顶部任务导航、稳定关系路径/完整列表、条件检查器、原生控制、CSP/offline/selector兼容 |
| 更新UIUX与可访问指导 | 中文系统fallback、正文14/元数据12/移动输入16、44px、200%缩放、真实错误与恢复 |
| Motion/Emil/animation原则 | 真实动作触发100/120/180/120/160ms，数量/stale/错误0ms，reduced-motion全运动0，禁止假进度/打字/force |
| 原生imagegen与图标技能 | 品牌无安全seal、HTML字标、少量生成说明资产、功能SVG统一、alpha/crop/hash/16–64px验收 |
| 原生Office/PDF | 同品牌与事实，可编辑数据图表、最终实际页面截图与全页渲染边界 |
| 全组真实性/恢复意见 | 复核/发布网络未知先查真实状态，草稿保留，CAS确认，默认引用不选，原文来源性质不冒充审核 |

## D1.0冻结结论与未完成范围（历史）

D1.0方向、token、任务结构、状态、动效与30项交互验收已决策；完整规范由根design.md管理。各技能不分别拥有产品主题，后续增量必须遵守同一规范。
图像生成、后处理、代码实施、真实运行截图、完整交互与设备/读屏验收尚待完成；设计咨询不证明这些步骤已通过。InterfaceCraft会员技能仍未取得；Motion公开MIT技能已取得/咨询，其会员增强工具与Emil会员课程不在已执行范围。
基础规范的frontmatter采用平面colors/spacing/rounded和mapping形态typography，token来自本轮已决策新方向，标记normative_target_pending_implementation；不把旧CSS重复值推成设计意图。离线结构检查不冒称Google lint/export工具认证；实际工具校验以随后真实收据为准。
当时应用为合成演示；当前默认业务模式、Nexent新回执与软件发布门槛由以下v0.4.0裁决覆盖。历史未完成项不能直接写成现在仍未实现，也不由咨询代替真实行业/专业验证。

## v0.4.0最新用户删繁与业务裁决

用户红框要求覆盖D1.1首轮visible宽控建议：折叠只保留品牌旁44px图标，删工作台/来源关系版本卡、底部本地空间和-/reset/+；边缘drag和focusablehandle键盘仍可操作，真实actor/logout保留。不为反侧栏/通用a11y模板恢复被用户删掉的装饰。
用户又要求select效果更好看，采纳vanilla渐进增强、native value/form/validation保留、完整键盘/ARIA/anchorflip、enter160/exit100/reduced0；这是待实现/QA合同，不冒称参考Radix/shadcn等于运行依赖或已验证。
新默认业务空库/认证/六表发布可接授权业务数据，synthetic保留为显式测试/展示；字段和授权声明不证明行业有效性。当前 Nexent、全suite、容器和新界面验收已分别收口，源码已推送；真实行业效果、独立专业审核和正式参赛提交仍待完成。
