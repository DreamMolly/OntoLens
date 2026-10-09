# 品牌与生成图像资产

D1.0 · 2026-10-09 · 品牌素材已生成并接入页面；完整资产与小尺寸验收以清单和变更状态为准。

[返回设计规范目录](README.md)。MUST/SHOULD/MAY 强度见[产品原则](01-product-principles.md)。

## 已生成资产

2026-10-08 已用供应商的 `gpt-image-2.5-flare` 与 `gpt-image-2.5-sunburst` 实际取得 PNG；采用 Sunburst 的观察视窗/关系索引轮廓，保留真实 alpha、清边、统一墨色并导出网页尺寸。Flare 生成的来源、关系、版本三枚说明图标已去底、裁切并检查；它们只说明结构，不表示业务核验完成。

[资产清单](asset-manifest.json)保存实际请求 prompt/哈希、原图尺寸、处理步骤和最终文件 SHA-256。服务实际返回尺寸与请求尺寸不同，清单分别记录；CLI未记录返回模型名，不虚构模型回显。早期原生 SDK 调用收到的 403 作为失败历史保留，之后兼容 Images 调用已验证成功。

主标志使用 `ontolens-symbol-d1-64.png`，favicon 使用32px PNG；256px PNG/WebP用于高密度或导出。深色背景必须使用浅墨版，不把深石墨轮廓放到相同底色。16px保留可辨轮廓，完整分支细节以32px以上显示为准。HTML字标与功能SVG图标保持独立。

## 资产分层

品牌mark识别产品，HTML字标提供正确文字，功能SVG解释操作，生成说明资产辅助空状态/概念。角色 MUST分开，栅格素材不能承担真实关系数据。
标志 SHOULD在不闭合视窗/镜头与有限关系点之间形成清楚轮廓；“已通过”“安全”“专家审定”不能作为图形含义。
颜色以[基础规范](02-foundations.md)为准，业务状态留在真实HTML组件；品牌可单色降级，不依赖红绿区分身份。

## 10 品牌与图像资产

方向已锁定后才生成品牌资产；用户授权当前 provider 的 `gpt-image-2.5-flare` / `gpt-image-2.5-sunburst` 实际别名，名称来自provider模型发现，不能称官方OpenAI文档已验证的型号。
Logo MUST 表达开口关系索引/观察视窗/镜头中的简洁关联，1–2墨色，清楚负空间；不得使用安全盾牌、认证章、审核勾、业务ALLOW或文字符号作背书。
字标 MUST 使用可选择的真实 HTML 文本“格物镜”“OntoLens”；生成图不承担导航标题、数据、证据原文和交互文案。
少量生成栅格图标 MAY 用作品牌/说明资产；常用功能图标 MUST 统一24×24 SVG线框网格、1.5–1.75 stroke、round cap/join，并带文字或可访问名称。
AI位图 MUST NOT 以PNG内嵌SVG冒称可无限缩放矢量；最终选中PNG/WebP进入本地static，生成原图/废弃稿只保留本地构建区，不作为应用运行依赖。
透明 MUST 检查真实alpha极值/透明像素，RGBA或棋盘图不等于透明；不支持原生透明时记录纯色生成、后处理去背、边缘修正，禁止假称原生透明。
MUST 检查裁切bbox、主体完整、留白/清晰区、深浅背景白晕，以及16/32/64px实际显示可辨；favicon另验证16/32/48px。
资产清单 MUST 记录role/path/mime/dimensions/sha256、requested/returned model、生成时间/prompt/reference hashes、处理步骤/crop/alpha和小尺寸检查；不记录key/header或私有原文。
新版本 SHOULD 用版本化文件名和稳定最终引用以便回滚；MUST 提供功能图标的aria-hidden或有意义的alt，装饰图像alt为空。

## 生成、选择、处理与接入

1. MUST确认素材角色确需生成；表单、真实关系、locator、数字和操作控件用代码。
2. Prompt MUST明确asset用途、主体、1–2墨色、轮廓、留白和禁止项；参考图标明reference/edit-target，不强制保留旧logo。
3. 使用用户已授权的实际provider模型，记录requested/returned；未支持参数不猜，不偷偷切模型。
4. 输出 MUST检查主体完整、无额外文字/水印/安全seal；针对关键缺陷迭代，有输出不等于最终。
5. 保留原图/hash/prompt，非破坏性裁切、去背和优化；每步记录工具/参数及前后hash。
6. MUST检查真实alpha及深浅底边缘；去背不能误删主体负空间和细关系线。
7. MUST做16/32/64px实际显示对照，favicon另测16/32/48px；小尺寸手工简化版准确记录处理来源。
8. 选中PNG/WebP接入local static，设置width/height/alt；功能SVG保持grid/currentColor，不用大图填按钮。
9. MUST在最终页面和mobile背景复查，清单相对路径/hash一致；原图/废弃稿不随源码白名单发布。

原生image_gen未暴露，CLI/API fallback已获授权，不把没有调用的内置工具写进收据。无真alpha或小尺寸不可辨的候选不接入，MAY保持文字品牌和规范功能图标继续可用。
授权生成不等于授权上传私有资料、购买素材或发布仓库；prompt不带凭证和私有原文。

业务v0.4.0继续使用已生成/验收的D1品牌资产，current角色由实际账号/模式表达；logo不代表专业背书或业务ALLOW，六概念空态图仍是未运行结构示意。
