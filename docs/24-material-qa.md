# 格物镜 · OntoLens 初赛材料版式 QA

日期：2026-10-09。当前材料已按最终 v0.4.0/D1.1 收据更新，并随源码推送到私有 Gitea；不是官方最终模板或实际行业验收材料。检查范围为现行 Word/PPT、D1.1 首页结构示意截图和可编辑来源。

## v0.4.0/D1.1 当前更新

本轮保留 Word 4 页、PPT 11 页、主题和可编辑几何。正文改为实际软件范围：空业务库、角色登录、六原始/六规范化台账、候选检查/管理员发布、业务核验、追加复核和证据导出。行业字段适用性、独立评测、专业审核、长期稳定性和正式提交仍未完成；不执行真实出库。

PPT 第 10 页使用 `.runtime/ontolens-D1.1-final-home-1440x1230.png`（1440×1230，SHA256 `D89B08BAC3D0C6D611C3B5DCD14099A9DF802B1E580D239BC78BEEC38FC4FBBB`），caption/alt 明确“D1.1 当前首页结构示意 · 尚未核验”，不表示当前 ALLOW 100 mL。`images/image-8-1.png` 与 `svg_final/10_demo.svg` 已同步。

最终收据已到位：`artifacts/local-validation-report.json` 为 `passed=true`，`.venv/Scripts/python.exe -m pytest -q` 返回 **456 passed in 156.97s**；browser、MCP、assets、JEV、pip、JavaScript 与 pytest 共七阶段 exit 0，`artifacts/source-validation/20261009-052126-c6f21459/` 保留日志，154 项输入指纹一致。

当前 Docker 业务部署 `artifacts/operational-deployment-20261009.json` 为 `passed`，30 项检查通过，覆盖空卷、账户/权限、导入发布、四种决定、needs_review、导出重算、模型边界、非 root、健康和重启持久化；`real_industry_data_used=false`。当前模型配置 `artifacts/nexent-model-configuration-20261009.json` 为 `passed`，持久绑定 gpt-6-sol/model_id=2。

日期与选择控件分别由 `artifacts/workbench-date-interaction-report.json`、`artifacts/workbench-select-interaction-report.json` 记录，均为 6/6、0 页面错误、0 外站请求；范围是隔离合成 Playwright，不是实际读屏、真实设备或行业验证。

## 2026-10-09 最终材料 QA

| 检查 | 当前结果 | 证据 |
| --- | --- | --- |
| Word/PPT schema | 各 0 errors | `officecli validate` |
| Word issues | 26 条模板排版提示，未将提示写成失败 | `officecli view ... issues` |
| PPT issues | 0 issue | `officecli view ... issues` |
| 软件全量回归 | 456 passed；7 阶段 exit 0；154 项输入指纹一致 | `artifacts/local-validation-report.json` |
| Docker 业务部署 | 30 checks passed；合成私有测试夹具 | `artifacts/operational-deployment-20261009.json` |
| 当前首页图片 | D1.1 结构示意，尚未核验，不表示 ALLOW | `.runtime/ontolens-D1.1-final-home-1440x1230.png` |

当前原生文件收据：Word SHA256 `A978F8A33019EE9552EB23E0ACA6D9CE1727E55D0F98403EB251D16941D68B35`，4 页、48 段、174 词、2675 字符、Word issues 26；PPT SHA256 `B40C0A15EC620B48E8DBD1FE163A592169CD04D7A12335122E9ADE8E64D51304`，11 页、PPT issues 0。最新原生接触表为 `.runtime/material-final-456-20261009/word/contact-after-doc-fix.png` 与 `.runtime/material-final-456-20261009/ppt/contact-after-doc-fix.png`，已检查4页/11页无新增溢出或重叠。相对前次发布，Word正文只将31项改为30，PPT仅修正notes8/9数字、时间和日志目录，全部幻灯片内容与几何字节未变。

以下 2026-10-08 章节保留为历史 QA，不代表当前材料哈希、计数或收据。

## 历史文档 QA 状态（2026-10-08）

| 原生文件 | SHA256 | 当前结果 |
| --- | --- | --- |
| Word 开发设计稿 | `873744E91D27A0B6B0740AF96D1680D11258B4BF43155D0F29DD4CE821E22A43` | schema 0 errors；4 页、48 段、176 词、2567 字符；Word issues 26（3 空段、17 首行缩进、6 标点提示） |
| PPT 答辩稿 | `2198E9F047DAB00AEBEA2819F18BC36DDC27E373305E41B66279927CA5832C03` | schema 0 errors、PPT issues 0；11 页；P10 图片框 439.05×375 pt |
| P10 viewport | `D89B08BAC3D0C6D611C3B5DCD14099A9DF802B1E580D239BC78BEEC38FC4FBBB` | 1440×1230；当前首页结构示意，明确尚未核验；与 SVG 内嵌媒体、images/image-8-1.png 一致 |

页图位于 `.runtime/material-ontolens-D1.1-release-qa/render/`。Word 的 26 条 issues 保留模板空段/缩进和技术名混排标点提示；不宣称全部消除。旧历史章节中的 356 只作历史基线，当前全suite计数以本页和 `artifacts/local-validation-report.json` 为准。

## 历史 D1.0-6 快照对象（2026-10-08 19:01）

使用 `officecli 1.0.155`，`OFFICECLI_NO_AUTO_RESIDENT=1`。本历史阶段由 `.runtime/material-ontolens-D1-snapshot-qa-20261008/receipt.json` 记录，与上节 D1.1 release QA 是不同阶段。

| 原生文件 | SHA256 | 数字 / 页数 |
| --- | --- | --- |
| `submission/peiwu-development-design-draft.docx` | `a5d537e7541aede1f590527ab69f50cf82b7f1b81205995ec2b372a680a52140` | `356 passed`，4 页；该快照阶段哈希未变 |
| `submission/peiwu-presentation-draft.pptx` | `785054a30713b762ef3274bbd4097c7fefcd57b95e522cdcd42e595906b1046e` | `356 passed`，11 页 |

工程文件名、peiwu 引用及历史 generated 记录保留。Logo 为模型生成并处理的品牌位图，来源 `design/asset-manifest.json`；不称手绘 SVG，不称模型生成整个工作台界面。

## 历史 D1.0-6 实际结果（2026-10-08 19:01）

| 检查 | 结果 | 证据范围 |
| --- | --- | --- |
| Word/PPT schema | 各退出码 0、0 errors | 当前原生文件通过 |
| PPT issues | 退出码 0、0 issue | 当前结构/格式检查通过 |
| Word issues | 24 条原有提示 | 3 空段、16 首行缩进、5 CJK/Latin 标点提示；没有宣称全消除 |
| Word stats | 4 页、48 段、180 词、2676 字符 | 当前哈希与 `.runtime/material-ontolens-brand-qa-20261008/receipt.json` 相同，沿用该阶段实际原生页图与接触表 |
| PPT 第 10 页 | 原生单页 PNG 已生成、查看 | 当前目录 `ppt/slide-10.png`，无新增拉伸、裁切、重叠或越界 |
| PPT 全 11 页 | 当前原生 3 列接触表已生成、查看 | 当前目录 `ppt/contact.png`，没有新增版式退化 |
| 结构差异 | 其它幻灯片及 notes 字节未变 | 所有 PPT/SVG 数值几何不变；第 9 页 356 数字未变，见 `mutation-scope.json` |
| 本地验证回读 | 356 passed（97.34 秒）、7 checks 退出码均 0 | 当时 run `artifacts/source-validation/20261008-104853-561a21f6`，128 个输入指纹匹配该阶段实现；本材料子任务未重复运行测试 |
| 最终交付审计 | 待根任务 snapshot 后执行一次 | 本子任务未运行 audit，旧 passed 收据不能绑定新的 PPT 哈希 |

Word 封面新名称保持两行完整，概述无溢出；原模板大面积留白为既有版式建议。其它品牌变化页的实际原生检查在 `.runtime/material-ontolens-brand-qa-20261008`，本轮其它幻灯片字节未变。截图细字仅作界面示意，详细阅读仍应打开实际工作台。

## 历史 D1.0-6 第 10 页截图与来源

该历史阶段源图为 `.runtime/ontolens-D1-material-1440x1230.png`，精确 1440×1230 viewport，SHA256 `050e8e661c29448d61a5c8927eded0305e245099650b3e007f603228ead06d50`。截图来自 D1.0-6 工作台，运行记录 `run_5b16db52eb994522b2c8`，合成申请日期 2026-09-28，ALLOW 100 mL，选中 stu01 来源及原文同屏；捕获收据为 `.runtime/ontolens-D1-final-screenshot-receipt.json`。

当时 PPT 图片位置 `/slide[10]/group[@id=6]/picture[@id=5]` 保留原 x/y/width/height；该阶段的 `images/image-8-1.png` 和 `svg_final/10_demo.svg` 内嵌 PNG 与上述 `050e8e…` 源图同字节。后续 D1.1 已替换为 `D89B08…` 首页结构示意，尚未核验；不能把本历史 run 或 ALLOW 100 mL 归给 D1.1 源图。

该历史截图只证明当时本地合成资料运行的 UI 状态。旧 286 generated 导出及此前 QA 收据均保留其历史范围，不改称当前导出。当前源码已推送；实际行业资料、专业审核、外部冷启动、长期稳定性与正式参赛提交仍需各自验证。
