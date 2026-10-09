<!-- ppt-master-schema: design-spec/v1 -->
# 格物镜 · OntoLens竞赛演示 - Design Spec

## I. Project Information

| Item | Value |
| --- | --- |
| Project Name | 格物镜 · OntoLens竞赛演示 |
| Canvas Format | PPT 16:9, 1280 × 720 |
| Page Count | 11 |
| Primary Language | zh-CN |
| Target Audience | 华为 ICT 创新赛赛题 3 的技术评委及参赛队员 |
| Communication Intent | 用一个合成领用案例解释资料、关系、规则和决定如何衔接，再交代可复现证据与未验证部分 |
| Desired Audience Outcome | 评委能指出决定由哪个程序产生、如何追溯来源、制度变化如何触发复核，并准确理解当前成果边界 |
| Core Message / Ask / Action | 格物镜 · OntoLens让每个程序决定都能回到当时的资料与规则；软件业务操作可用，行业效果另验 |
| Delivery Context | 有主讲的技术答辩，约 12 分钟讲解，可选 6 分钟现场操作 |
| Artifact Afterlife | 可编辑答辩草稿与队员讲解资料 |
| Reading Mode | balanced |
| Content Strategy | 保留已验证事实，允许重组页面和改写表达；禁止把合成数据当作真实行业效果 |
| Design Style | 证据链讲解：暖白技术图纸、深蓝标题、青绿证据路径 |
| AI Image Acquisition Path | not applicable |
| Generation Mode | continuous |
| Spec Refinement | disabled |
| Speaker Notes | enabled — workflow default，解释依据和验证边界 |
| Custom Animations | disabled — workflow default |
| Narration Audio | disabled — workflow default |
| Design Spec Depth | brief |
| Created Date | 2026-09-27 |

Design decisions use the user's standing autonomous project/material optimization instruction and explicit PPT improvement request. No UI confirmation receipt is fabricated. Three solution intents were considered: (1) evidence-chain explanation, a concrete case followed through source, graph and decision; (2) code-review briefing, dense interface and validation reference; (3) product demonstration, screenshot-led walkthrough. Direction 1 is selected because technical judges need the reasoning chain and its boundaries before implementation details. Direction 2 would put too much command detail on screen; direction 3 would under-explain the ontology and deterministic decision boundary. All three retain the same sourced facts; candidate 2 uses a serif/sans contrast, candidates 1 and 3 use a consistent sans family. Rendering candidates are technical flat line work, monochrome annotated evidence, and screenshot-led documentary composition respectively; no AI image is needed by the chosen resource plan.

## II. Canvas Specification

| Property | Value |
| --- | --- |
| Format | PPT 16:9 |
| Dimensions | 1280 × 720 |
| viewBox | `0 0 1280 720` |
| Margins | 64 px |
| Content Area | x=64..1216, y=150..642；页脚 y=670..704 |

## III. Visual Theme

### Theme Style

- **Mode**: custom
- **Mode References**: instructional
- **Mode Behavior**: 以一个领用申请为线索，从任务、资料、关系到程序决定逐层解释；最后用软件验证和演示步骤收束，讲稿负责解释细节。
- **Visual style**: custom
- **Visual Style References**: swiss-minimal
- **Visual Style Behavior**: 用清晰对齐、强弱有别的字级和少量大色面组织信息。关系图依靠直接连线、边界和文字说明，少量青绿强调可追溯路径；封面与结束页为深蓝底，内容页为暖白底，真实截图保留原色。
- **Theme**: 沿用格物镜 · OntoLens的深蓝/青绿识别度。来源到决定的连续细线是含义明确的重复元素；位置和结构随关系变化。
- **Tone**: 清晰、克制、可核验。

### Color Scheme

| Role | HEX | Purpose |
| --- | --- | --- |
| Background | #F7F9FA | 内容页背景 |
| Secondary background | #EDF3F6 | 归属区域 |
| Primary | #17384B | 标题、核心程序、深色页 |
| Accent | #087F8C | 来源链路、已核验入口 |
| Secondary accent | #B66320 | 待复核与限制 |
| Body text | #243746 | 正文 |
| Secondary text | #526874 | 注释与脚注 |
| Divider | #CCD9DF | 分隔线 |
| Positive | #176B55 | ALLOW |
| Negative | #A33845 | DENY 与 ISOLATE |
| Inverse text | #FFFFFF | 深底正文 |

## IV. Typography System

### Font Plan

| Role | Character (Reference) | Primary | English if non-English | Fallback tail |
| --- | --- | --- | --- | --- |
| Title | 粗体无衬线 | Microsoft YaHei | Arial | sans-serif |
| Body | 中性无衬线 | Microsoft YaHei | Arial | sans-serif |
| Code | 等宽标识符 | Microsoft YaHei | Consolas | monospace |

- **Title stack**: Microsoft YaHei, Arial
- **Body stack**: Microsoft YaHei, Arial
- **Code stack**: Microsoft YaHei, Consolas
- **Role rationale**: Code 用于确切的来源字段和复现命令，其等宽间距帮助识别不可改写的标识符。

### Font Size Hierarchy

| Purpose | Anchor Size (px) |
| --- | ---: |
| Body | 24 |
| Title | 44 |
| Subtitle | 30 |
| Lead | 28 |
| Annotation | 18 |
| Footnote | 16 |
| Code | 18 |
| Display | 72 |
| Cover | 104 |

## V. Layout Principles

### Deck-wide Direction

- **Hierarchy direction**: 先看到主题，再读图中的关系，最后读取样例和限制。
- **Composition tendency**: 关系页使用足够大的整体图解；案例页用对照，指标页用平面大数字，截图页保留完整界面。
- **Cross-page continuity**: 资料、关系、决定采用一致的深蓝与青绿语义；封面提出可追溯性，结束页回到真实验证条件。
- **Spacing posture**: 内容页密度有差别，复杂链路与单一结论交替。
- **Spacing anchors**: page margin 64 px；block gap 24 px；column gutter 40 px；corner radius 4 px；body leading 36 px。

## VI. Icon Usage Specification

- **Primary bundled library**: none

| Icon Path | Suitable Scenarios |
| --- | --- |

## VIII. Image Resource List

| Filename | Dimensions | Ratio | Purpose | Type | Image pattern | Crop Policy | Acquire Via | Status | Reference | text_policy | page_role |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| image-8-1.png | 1440 × 1230 | 1.170732 | 第 10 页展示工作台中申请、程序决定与证据入口 | Screenshot | 完整界面放在主要视区，右侧用操作顺序解释 | no-crop | user | Existing | D1.1-7 当前首页结构示意，1440×1230真实viewport，六节点尚未核验；Logo为模型生成后处理位图 | embedded | local |

## IX. Content Outline

### Part 1: Task and Decision Chain

#### Slide 01 - 格物镜 · OntoLens
- **Audience move**: 只知道项目名 → 知道项目解决领用核验与依据追溯。
- **Relationships**: order：来源证据 → 关系路径 → 程序决定。
- **Composition**: 深蓝底的大标题与右侧纵向证据路径，标题是主要焦点。
- **Title**: 格物镜 · OntoLens
- **Core message**: 每个决定，都能回到依据。
- **Content**:
  - 可追溯的实验室危化品领用决策智能体。
  - 第十一届华为 ICT 大赛 · 创新赛赛题 3。
  - 合成演示 / 旁路核验 / 不执行真实出库。
- **Cover impact**: 每个决定，都能回到依据；以资料—关系—程序决定的连续路径承载项目主张。

#### Slide 02 - 领用核验需要哪些依据
- **Audience move**: 将任务视为问答 → 理解一次核验需要多份资料与历史时点。
- **Relationships**: link：人员授权、批次台账、柜位限制与当日记录共同支持一条领用申请；contrast：资料齐全与资料不足产生不同编排状态。
- **Composition**: 上方一条示例申请，下方将四类资料与核验入口连在一起。
- **Title**: 领用核验需要哪些依据
- **Core message**: 必须核对来源、时点与适用规则，才能产生程序决定。
- **Content**:
  - 示例：stu01 / lot_eth / cab_flam / 100 mL。
  - 人员授权、批次与库存、柜位限制、当日未归还类别。
  - 输入资料缺失、过期或冲突时进入 needs_review，decision=null。
  - 场景仍为教学合成目录，真实行业任务待验证。

#### Slide 03 - 四项能力串成一条核验链
- **Audience move**: 看到零散功能 → 能对齐赛题要求与实现位置。
- **Relationships**: order：异构资料 → 资产认知 → 本体候选 → 检索与规则判定；membership：跨文档溯源贯穿各环节。
- **Title**: 四项能力串成一条核验链
- **Core message**: 接入、候选、检索判定与追溯共享同一来源和版本。
- **Content**:
  - 文本 / 表格 / PDF 文本 / 图片人工摘录。
  - 人员、物料、批次、柜位等资产，采用目录与别名基线。
  - 关系和 schema 候选先标记 proposed，再进行演示确认。
  - 检索与图路径提供证据，decision_check 调用规则程序。
  - source_id、locator、quote、SHA256 贯穿全链；当前不代表自动 OCR 或行业本体标准对齐。

#### Slide 04 - 决定绑定当时的来源与版本
- **Audience move**: 仅相信输出文字 → 知道如何回查同一决定的来源和版本。
- **Relationships**: link：stu01 的来源定位与原文哈希绑定快照 demo-initial，快照与规则 v2 共同绑定决定记录。
- **Title**: 决定绑定当时的来源与版本
- **Core message**: 查询历史记录时，应回到原快照与原规则。
- **Content**:
  - 来源定位示例：source_id=doc_c9a9d19a967b4db5a2b3；locator=$.stu01。
  - 原文片段含授权类别 FLAMMABLE / ACID / GENERAL；完整 quote 与 SHA256 可在工作台展开。
  - 快照 demo-initial；规则 v2；程序结果 ALLOW / 100 mL / ALLOWED。
  - snapshot_hash 与 source SHA256 分别标记快照和原文，二者不混用。
  - 版本发布后，旧决定仍指向原快照。
  - external_model_allowed 默认本地处理；图片依赖人工摘录。

#### Slide 05 - 四种决定与停判状态
- **Audience move**: 知道四个输出词 → 能解释每种决定对应的实际合成输入。
- **Relationships**: contrast：同一快照规则下，不同申请/当日类别/批次状态触发四种决定；needs_review 是缺证据状态而非第五种业务决定。
- **Title**: 四种决定与停判状态
- **Core message**: 决定来自确定性程序，模型不能改判。
- **Content**:
  - demo-initial / v2 / as_of=2026-09-23 的实际平台工具回放。
  - stu01、lot_eth、100 mL → ALLOW 100 mL / ALLOWED。
  - stu03、lot_eth、100 mL，当日已有 OXIDIZER → DENY / SESSION_INCOMPATIBLE。
  - stu01、lot_eth、300 mL，库存 2000 → LIMIT 250 mL / ISSUE_CAP。
  - stu01、lot_eth_exp、100 mL → ISOLATE / LOT_NOT_ISSUABLE。
  - unknown_demo_person → needs_review / decision=null，交人工补证。
- **Visualization**: decision-cases：输入、程序决定、reason_code 三列原生文本表格，四行决定与独立停判说明。
- **Native-ready**: decision-cases=yes

### Part 2: Review, Orchestration and Evidence

#### Slide 06 - 候选审核、发布与回滚
- **Audience move**: 将本体更新视为自动学习 → 理解候选与有效规则之间的确认边界。
- **Relationships**: order：原始来源 → proposed 关系/schema → 影响预览 → 演示确认 → 新快照；link：回滚指向原历史快照。
- **Title**: 候选审核、发布与回滚
- **Core message**: 候选不会自动成为有效业务事实。
- **Content**:
  - 授权句式形成 authorized_for 关系候选；日期形成 valid_from、valid_until 属性候选。
  - 先预览哪些历史申请受影响，经过冻结基准检查后再演示发布。
  - 合成授权变化演示可出现 ALLOW → DENY → 回滚恢复 ALLOW。
  - 演示确认不等于专业审核；CLI promote 仅检查，工作台演示发布才生成新快照。

#### Slide 07 - JEV 与模型的职责边界
- **Audience move**: 把所有 AI 输出视为决定 → 区分复核提示、编排解释与程序裁决。
- **Relationships**: membership：JEV 属于可选证据复核，通用模型属于工具编排和解释，decision_check 属于唯一业务决定来源；order：外发授权检查先于显式在线 JEV 请求。
- **Title**: JEV 与模型的职责边界
- **Core message**: 复核提示和解释都不能替代 decision_check。
- **Content**:
  - 先核对 locator、完整 quote、SHA256，再输出可选相关性或复核优先级。
  - Noul 概率不是事实准确率；一条合成相关性请求已验证连通性。
  - 引用语义、阈值校准和真实资料效果未验证。
  - JEV 在线请求需显式 `live=true`，且来源必须非 private 并获准外发；未配置时返回 unavailable。一次联调只证明连通性，不是准确率。
  - 通用模型调用工具与解释结果；ALLOW / DENY / LIMIT / ISOLATE 由程序产生。

#### Slide 08 - Nexent 编排与本机恢复
- **Audience move**: 怀疑只有本地脚本 → 看清真实 Nexent 平台、七工具与工作台的连接。
- **Relationships**: link：Nexent Agent 经 MCP 调用工作台工具；membership：三个 Skill 划分输入、证据、决定职责；order：启动条件检查先于现有服务恢复。
- **Title**: Nexent 编排与本机恢复
- **Core message**: 平台负责调度，程序负责决定，来源记录负责复查。
- **Content**:
  - 可见名称为 OntoLens Agent，三项职责为申请输入、证据链、确定性判定；现有机器 ID 保留兼容。
  - 工具集合：asset_recognition、evidence_lookup、graph_query、candidate_suggestions、evidence_rerank_jev、decision_check、candidate_review。
  - 当前 OntoLens 新镜像 35 项检查通过，gpt-6-sol/model_id=2 与 Agent 2 解释延续既有平台配置，未重新登记机器 ID；旧 30 项部署与 10-08 七工具/Agent 1 编排保留历史，外部冷启动和行业效果另验。
  - start-demo.ps1 面向已准备本机，复用 F 盘数据和令牌；增加数据库等待与数据处理健康检查。
  - 日常恢复不等于新机一键部署或独立冷启动。
  - 启动入口不安装依赖、不迁移数据、不创建模型、不重复导入 Agent。

#### Slide 09 - 当前合成软件验证
- **Audience move**: 误把测试数当行业准确率 → 理解各数字对应的命令与有限范围。
- **Relationships**: contrast：冻结规则集、软件回归和平台工具是不同验证对象，不能相互替代。
- **Title**: 当前合成软件验证
- **Core message**: 已验证可复现的软件链路，行业效果仍未验证。
- **Content**:
  - 冻结合成规则集：60/60 exact_match，unsafe_release=0。
  - 平台 MCP：7 个工具实际验证。
  - 当前全量回归 464 passed in 166.48s，七阶段 exit 0、158 项输入指纹一致；新镜像收据为 35 checks passed，real_industry_data_used=false。权威收据为 artifacts/local-validation-report.json、artifacts/source-validation/20261009-094214-e5337f3f/ 和 artifacts/operational-deployment-20261009-ontolens.json。
  - .venv/Scripts/python.exe -m pytest -q。
  - .venv/Scripts/python.exe scripts/verify_nexent.py。
  - 规则结果、项目测试数和模型效果分开解释；不宣称行业准确率。
  - 冻结 60 条已由开发者查看，不能称为盲测；unsafe_release 指标不覆盖过高的 LIMIT 数量。

#### Slide 10 - 工作台上的六分钟演示
- **Audience move**: 只看抽象流程 → 知道如何按界面核验真实程序行为。
- **Relationships**: order：启动检查 → 四种决定 → 点击来源 → 合成授权变化 → 影响预览/发布/回滚 → Nexent 工具回放。
- **Title**: 工作台上的六分钟演示
- **Core message**: 现场从申请打开原文，再演示一次版本变化。
- **Content**:
  - start-demo.ps1 检查通过后打开工作台。
  - 四种决定与 needs_review 可分别展示；点击来源查看 locator、quote、SHA256。
  - 授权变化后预览影响，再演示发布与回滚。
  - Nexent 展示证据→关系→程序决定；合成标签与专业审核未完成标记保留。
- **Images**: image-8-1.png 精确 1440×1230 viewport 截图，完整保留该视窗；D1.1-7 当前首页结构示意，六节点尚未运行核验；右侧为软件演练路径，行业适用性/独立评测/专业审核仍待完成。

#### Slide 11 - 后续验证与交付条件
- **Audience move**: 将本机演示视为全部完成 → 明确后续实际证据和验收责任。
- **Relationships**: order：资料授权与领域核验 → 公平对照与独立复现 → 模板冻结与队员答辩。
- **Title**: 后续验证与交付条件
- **Core message**: 先补真实证据，再扩大结论。
- **Content**:
  - 真实关联资料、业务审核人和处理权限待队员落实。
  - 独立冷启动、持续负载、JEV 校准和公平方法对照待验证。
  - 队员/导师资料、官方模板字段和答辩准备待完成；不承诺奖项。
  - 持续模型调用的费用上限仍待确认。
  - 已完成部分以可复现命令、证据矩阵和失败记录交接。
- **Closing impact**: 先补真实证据，再扩大结论；用三个明确验收阶段形成结束。

## X. Speaker Notes Requirements

- **Generation**: enabled
- **Filename**: match each SVG filename under notes/
- **Content**: 逐页解释可见图解、标识符和限制。数字引用本地 artifacts 与冻结 data，来源写入讲稿，避免把软件测试当成效果评估；不增加未经证明的业务收益。
- **Total duration**: 约 12 分钟讲解，现场操作另预留 6 分钟。
- **Notes style**: 自然、清楚的中文技术讲解。
- **Presentation purpose**: 让评委理解格物镜 · OntoLens的可追溯决定链路和当前证据边界。




本轮 v0.4.0/D1.1-7 保留原生 11 页主题和数值几何，采用 officecli DOM 修改现有正文、备注、计数和第10页图片，不重新生成整套幻灯片。六台账业务导入、账户权限、候选检查/管理员发布、核验/复核/导出已实现，行业适用与独立专业验收另记。当前首页图不表示实际核验结果；最新原生 QA 收据见 `.runtime/material-public-ontolens-20261009/receipt.json`，历史 exports/validation 保留原范围。


公开与命名迁移验收：464 个测试、七阶段通过、158 项输入指纹一致；最终耗时与日志目录以 `artifacts/local-validation-report.json` 为准。新 OntoLens Docker 收据 `artifacts/operational-deployment-20261009-ontolens.json` 为 35 项检查通过。PPT 第 8 页可见 Agent/Skill 名称使用 OntoLens 与职责词，实际平台旧 ID 留在备注作兼容说明；未重新登记。QA 收据 `.runtime/material-public-ontolens-20261009/receipt.json`；旧 exports/validation 保留历史。
