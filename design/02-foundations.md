---
name: 格物镜 · OntoLens 产品设计规范
version: D1.1
status: 代码主实现已落地，专项验收部分通过，完整验收待完成
description: 关系检证台的视觉、任务、交互、动效与工程合同
evidence-status: implementation_partially_verified
colors:
  canvas: '#f5f3ed'
  paper: '#ffffff'
  ink: '#25323a'
  secondary: '#54636b'
  border: '#d7dcda'
  action: '#285fa1'
  primary: '#285fa1'
  allow: '#2f6b47'
  warning: '#8a640c'
  blocked: '#a83c39'
  action-surface: '#edf3fb'
  allow-surface: '#eef5f0'
  warning-surface: '#fbf5e7'
  blocked-surface: '#fbefed'
  focus: '#285fa1'
  nav-surface: '#25323a'
  nav-text: '#e6edf2'
  nav-secondary: '#b4c2ce'
  nav-hover: '#31414c'
  nav-active: '#315985'
  nav-active-text: '#f8fbff'
  nav-focus: '#8cc1ff'
  nav-resize: '#718391'
typography:
  body:
    fontFamily: '"Noto Sans SC","Source Han Sans SC","PingFang SC","Microsoft YaHei UI","Microsoft YaHei","Segoe UI",sans-serif'
    fontSize: 14px
    lineHeight: '1.6'
    fontWeight: 400
  metadata:
    fontSize: 12px
    lineHeight: '1.6'
    fontWeight: 400
  mobile-input:
    fontSize: 16px
    lineHeight: '1.5'
    fontWeight: 400
  heading1:
    fontSize: 28px
    lineHeight: '1.35'
    fontWeight: 600
  heading1-mobile:
    fontSize: 26px
    lineHeight: '1.35'
    fontWeight: 600
  heading2:
    fontSize: 20px
    lineHeight: '1.4'
    fontWeight: 600
  home-heading:
    fontSize: 34px
    lineHeight: '1.3'
    fontWeight: 600
  home-heading-compact:
    fontSize: 32px
    lineHeight: '1.35'
    fontWeight: 600
  heading3:
    fontSize: 16px
    lineHeight: '1.5'
    fontWeight: 600
  label:
    fontSize: 14px
    lineHeight: '1.5'
    fontWeight: 500
  quote:
    fontSize: 14px
    lineHeight: '1.7'
    fontWeight: 400
  mono:
    fontFamily: '"Cascadia Code",Consolas,monospace'
    fontSize: 12px
    lineHeight: '1.6'
    fontWeight: 400
rounded:
  input: 6px
  button: 6px
  workspace: 8px
  dialog: 10px
spacing:
  step1: 4px
  step2: 8px
  step3: 12px
  step4: 16px
  step5: 20px
  step6: 24px
  step7: 32px
  step8: 48px
---

# 基础颜色排版与空间

D1.1 · 2026-10-09 · 首页与可拉伸侧栏主实现已落地；完整验收待完成，D1.0实现记录保留。

[返回设计规范目录](README.md)。MUST/SHOULD/MAY 强度见[产品原则](01-product-principles.md)。

## 3 视觉世界与色彩

视觉从实验室的清楚记录、钢制工作面、丁腈用品和识别标签推导：暖矿物底、白色阅读面、石墨正文、钴蓝操作，状态色独立；没有纸纹、仪器刻度拟物或认证印章。
MUST 使用本页frontmatter的语义 token；实现可沿用兼容 CSS 变量名，但角色和值必须一致，新增色彩必须登记。

颜色角色：canvas承接全局画布，paper承接阅读面，ink/secondary区分正文层级，action只代表操作和选择，allow/warning/blocked独立表达业务状态，浅底与focus保持同一语义。精确值只在本页frontmatter维护。

品牌/操作蓝 MUST 与 ALLOW 绿分离；来源性质 MUST 用文字“合成/公开/私有”表达，不借绿色假设可信。
颜色 MUST 配合文字、原因或形状；禁止仅红绿区分通过与拒绝。连接点只表示对应本地服务状态。
MUST 达到普通文字 4.5:1、大字 3:1、有效控件边界和焦点 3:1；浅中性 border 不可独自承担必要控件边界，输入边界 SHOULD 使用 secondary 或对比达标的 role。
已计算 secondary 对白 6.224:1、对 canvas 5.609:1、action 对白 6.478:1、allow 对白 6.335:1；其他组合 MUST 在实际组件背景上验证。
默认是浅色工作台；MAY 后续增加经过同等验收的暗色主题，MUST NOT 自动引入第二套品牌和状态映射。

## D1.1 首页与深色侧栏

用户认可D1主区颜色和线条，并明确选择参考图的深侧栏、大标题、真实四统计及中央六关系结构示意。MUST保留canvas/paper/ink/action/线条，侧栏只新增nav语义角色，不恢复旧teal主题。
nav-surface由石墨ink派生；nav-text/secondary承载文字，nav-active/active-text表达当前任务，nav-focus用于深底焦点与selected边线，nav-resize用于调宽边线。
色值计算：nav-text/nav-surface11.128:1、nav-secondary/nav-surface7.236:1、nav-active-text/nav-active6.982:1、nav-focus/nav-surface7.009:1、nav-focus/nav-active3.860:1、nav-resize/nav-surface3.357:1。MUST再查实际hover/focus背景。
首页主句 MUST为“把依据看清，让决定可查”，home-heading默认34px，允许按实际空间32–36px；极窄屏用heading1-mobile并自然换行，不造成溢出。
四统计卡允许浅阴影与一致边线，图标不能是伪步骤01–04；数值来自真实API，不数字tween。

## 4 排版、空间与形状

字体 MUST 优先使用本地覆盖中文的 UI 无衬线栈：`"Noto Sans SC","Source Han Sans SC","PingFang SC","Microsoft YaHei UI","Microsoft YaHei","Segoe UI",sans-serif`。
不声明这些字体都已安装；MUST 保留系统 fallback，不加载 CDN，也不为规范擅自打包未经许可的字体。
正文 `14px / 1.6 / 400`，元数据最低 `12px / 1.6`，移动可编辑字段 `16px`；MUST NOT 用 8–10px 把证据和范围提示塞进首屏。
标题 h1 `28px / 1.35 / 600`、h2 `20px / 1.4 / 600`、h3 `16px / 1.5 / 600`；移动 h1 MAY 为 `26px`。
标签 `14px / 1.5 / 500`；强调以 500/600 字重和位置表达，不增加大写英文 kicker 或伪步骤编号。
数字与数量 SHOULD 使用 tabular-nums；只有 ID、hash 和技术片段使用本地 `Cascadia Code / Consolas / monospace`，中文任务与原文不用满屏等宽字。
原文 SHOULD 为 13–14px、行高 1.7、阅读宽度约 45–75 字符；长中文名和 64 位 hash MUST 支持换行及完整访问。
空间刻度为 `4/8/12/16/20/24/32/48px`；同级内容采用相同间距，新增例外 MUST 有内容原因。
输入/按钮圆角 `6px`、主要工作面 `8px`、dialog `10px`；边框通常 `1px`，焦点 `3px`、offset `2px`。
主工作面 SHOULD通过位置和轻边线建立层级，D1.1统计卡MAY用克制浅阴影；检查器/dialog用 `0 8px 28px #25323a14`，不逐层套卡片。
主按钮与触控有效目标 MUST 至少 `44×44px`；图标可小于触点，目标不得相互覆盖。
