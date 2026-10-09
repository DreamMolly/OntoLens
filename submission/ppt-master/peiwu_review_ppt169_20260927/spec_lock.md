<!-- ppt-master-schema: spec-lock/v1 -->
# Execution Lock

## canvas
- viewBox: 0 0 1280 720
- format: ppt169

## communication
- primary_language: zh-CN
- audience: 华为 ICT 创新赛赛题 3 的技术评委及参赛队员
- objective: 用具体合成案例说明资料、关系、程序决定和复核路径，让评委能定位决定来源并识别当前验证边界。
- core_message: 每个程序决定都绑定当时的来源和规则；当前软件业务操作可用，行业效果另验。
- consumption_mode: balanced

## mode
- mode: custom
- mode_references: instructional
- mode_behavior: 按一次合成申请从输入、证据到程序输出逐层解释，再用候选审核、平台编排、验证和演示收束。

## visual_style
- visual_style: custom
- visual_style_references: swiss-minimal
- visual_style_behavior: 使用清晰对齐、强弱有别的字级和少量大色面；关系图用直接连线与文字说明，青绿强调证据路径，深蓝封面和结束页呼应暖白内容页，真实截图保留原色。

## colors
- background: #F7F9FA
- secondary_bg: #EDF3F6
- primary: #17384B
- accent: #087F8C
- secondary_accent: #B66320
- body_text: #243746
- secondary_text: #526874
- divider: #CCD9DF
- positive: #176B55
- negative: #A33845
- inverse_text: #FFFFFF

## typography
- font_family: Microsoft YaHei, Arial
- title_family: Microsoft YaHei, Arial
- body_family: Microsoft YaHei, Arial
- code_family: Microsoft YaHei, Consolas
- body: 24
- title: 44
- subtitle: 30
- lead: 28
- annotation: 18
- footnote: 16
- code: 18
- display: 72
- cover: 104

## icons
- library: none
- inventory: none

## images
- p10: images/image-8-1.png | source=user | crop=no-crop

## page_rhythm
- P01: anchor
- P02: dense
- P03: dense
- P04: dense
- P05: dense
- P06: dense
- P07: dense
- P08: dense
- P09: dense
- P10: dense
- P11: anchor

## pptx_structure
- mode: flat

## forbidden
- `mask`, `<style>`, `class`, external CSS, `<foreignObject>`, `textPath`, `@font-face`, `<animate*>`, `<set>`, `<script>` / event attributes, `<iframe>`
- HTML named entities in text; write typography as raw Unicode and escape XML reserved characters
- 不得把合成数据写成真实行业数据。 (user)


本轮 v0.4.0/D1.1-7 保留原生 11 页主题和数值几何，采用 officecli DOM 修改现有正文、备注、计数和第10页图片，不重新生成整套幻灯片。六台账业务导入、账户权限、候选检查/管理员发布、核验/复核/导出已实现，行业适用与独立专业验收另记。当前首页图不表示实际核验结果；最新原生 QA 收据见 `.runtime/material-final-456-20261009/receipt.json`，历史 exports/validation 保留原范围。当前全量回归已由最终收据更新为 456 passed；旧 356 仅作历史基线。
