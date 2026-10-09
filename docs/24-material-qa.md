# 格物镜 · OntoLens 初赛材料版式 QA

日期：2026-10-09。当前材料已按最终 v0.4.0/D1.1 收据更新，仍是未推送的本地候选，不是官方最终模板或实际行业验收材料。检查范围为现行 Word/PPT、D1.1 首页结构示意截图和可编辑来源。

## v0.4.0/D1.1 当前更新

本轮保留 Word 4 页、PPT 11 页、主题和可编辑几何。正文改为实际软件范围：空业务库、角色登录、六原始/六规范化台账、候选检查/管理员发布、业务核验、追加复核和证据导出。行业字段适用性、独立评测、专业审核、长期稳定性和正式提交仍未完成；不执行真实出库。

PPT 第 10 页使用 `.runtime/ontolens-D1.1-final-home-1440x1230.png`（1440×1230，SHA256 `D89B08BAC3D0C6D611C3B5DCD14099A9DF802B1E580D239BC78BEEC38FC4FBBB`），caption/alt 明确“D1.1 当前首页结构示意 · 尚未核验”，不表示当前 ALLOW 100 mL。`images/image-8-1.png` 与 `svg_final/10_demo.svg` 已同步。

最终收据已到位：`artifacts/local-validation-report.json` 为 `passed=true`，`.venv/Scripts/python.exe -m pytest -q` 返回 **456 passed in 156.97s**；browser、MCP、assets、JEV、pip、JavaScript 与 pytest 共七阶段 exit 0，`artifacts/source-validation/20261009-052126-c6f21459/` 保留日志，154 项输入指纹一致。

当前 Docker 业务部署 `artifacts/operational-deployment-20261009.json` 为 `passed`，31 项检查通过，覆盖空卷、账户/权限、导入发布、四种决定、needs_review、导出重算、模型边界、非 root、健康和重启持久化；`real_industry_data_used=false`。当前模型配置 `artifacts/nexent-model-configuration-20261009.json` 为 `passed`，持久绑定 gpt-6-sol/model_id=2。

日期与选择控件分别由 `artifacts/workbench-date-interaction-report.json`、`artifacts/workbench-select-interaction-report.json` 记录，均为 6/6、0 页面错误、0 外站请求；范围是隔离合成 Playwright，不是实际读屏、真实设备或行业验证。

## 2026-10-09 最终材料 QA

| 检查 | 当前结果 | 证据 |
| --- | --- | --- |
| Word/PPT schema | 各 0 errors | `officecli validate` |
| Word issues | 26 条模板排版提示，未将提示写成失败 | `officecli view ... issues` |
| PPT issues | 0 issue | `officecli view ... issues` |
| 软件全量回归 | 456 passed；7 阶段 exit 0；154 项输入指纹一致 | `artifacts/local-validation-report.json` |
| Docker 业务部署 | 31 checks passed；合成私有测试夹具 | `artifacts/operational-deployment-20261009.json` |
| 当前首页图片 | D1.1 结构示意，尚未核验，不表示 ALLOW | `.runtime/ontolens-D1.1-final-home-1440x1230.png` |

当前原生文件收据：Word SHA256 `886389DE49DD4AE547E47229DEE6C58C03CD5A9CC60EF6B5D149681178D048CC`，4 页、48 段、179 词、2705 字符、Word issues 26；PPT SHA256 `8348BFA3B449D3A19D6FB4CD1DB57CBF07FB56B8B01D1A9012C3364856A0E242`，11 页、PPT issues 0。最终渲染接触表为 `.runtime/material-final-456-20261009/word/contact.png` 和 `.runtime/material-final-456-20261009/ppt/contact-final.png`；PPT 第 10 页为 `.runtime/material-final-456-20261009/ppt/slide-10.png`。

以下 2026-10-08 章节保留为历史 QA，不代表当前材料哈希、计数或收据。

## 历史文档 QA 状态（2026-10-08）

| 原生文件 | SHA256 | 当前结果 |
| --- | --- | --- |
| Word 开发设计稿 | `873744E91D27A0B6B0740AF96D1680D11258B4BF43155D0F29DD4CE821E22A43` | schema 0 errors；4 页、48 段、176 词、2567 字符；Word issues 26（3 空段、17 首行缩进、6 标点提示） |
| PPT 答辩稿 | `2198E9F047DAB00AEBEA2819F18BC36DDC27E373305E41B66279927CA5832C03` | schema 0 errors、PPT issues 0；11 页；P10 图片框 439.05×375 pt |
| P10 viewport | `D89B08BAC3D0C6D611C3B5DCD14099A9DF802B1E580D239BC78BEEC38FC4FBBB` | 1440×1230；当前首页结构示意，明确尚未核验；与 SVG 内嵌媒体、images/image-8-1.png 一致 |

页图位于 `.runtime/material-ontolens-D1.1-release-qa/render/`。Word 的 26 条 issues 保留模板空段/缩进和技术名混排标点提示；不宣称全部消除。全suite 计数待根任务最终收据到位后再写入，不沿用旧 356。

## 历史对象（2026-10-08）

使用 `officecli 1.0.155`，`OFFICECLI_NO_AUTO_RESIDENT=1`。历史收据：`.runtime/material-ontolens-D1-snapshot-qa-20261008/receipt.json`；最终收据：`.runtime/material-final-456-20261009/receipt.json`。

| 原生文件 | SHA256 | 数字 / 页数 |
| --- | --- | --- |
| `submission/peiwu-development-design-draft.docx` | `886389DE49DD4AE547E47229DEE6C58C03CD5A9CC60EF6B5D149681178D048CC` | `456 passed`，4 页；当前最终材料哈希见最终收据 |
| `submission/peiwu-presentation-draft.pptx` | `8348BFA3B449D3A19D6FB4CD1DB57CBF07FB56B8B01D1A9012C3364856A0E242` | `456 passed`，11 页 |

工程文件名、peiwu 引用及历史 generated 记录保留。Logo 为模型生成并处理的品牌位图，来源 `design/asset-manifest.json`；不称手绘 SVG，不称模型生成整个工作台界面。

## 历史实际结果（2026-10-08）

| 检查 | 结果 | 证据范围 |
| --- | --- | --- |
| Word/PPT schema | 各退出码 0、0 errors | 当前原生文件通过 |
| PPT issues | 退出码 0、0 issue | 当前结构/格式检查通过 |
| Word issues | 24 条原有提示 | 3 空段、16 首行缩进、5 CJK/Latin 标点提示；没有宣称全消除 |
| Word stats | 4 页、48 段、180 词、2676 字符 | 当前哈希与 `.runtime/material-ontolens-brand-qa-20261008/receipt.json` 相同，沿用该阶段实际原生页图与接触表 |
| PPT 第 10 页 | 原生单页 PNG 已生成、查看 | 当前目录 `ppt/slide-10.png`，无新增拉伸、裁切、重叠或越界 |
| PPT 全 11 页 | 当前原生 3 列接触表已生成、查看 | 当前目录 `ppt/contact.png`，没有新增版式退化 |
| 结构差异 | 其它幻灯片及 notes 字节未变 | 所有 PPT/SVG 数值几何不变；第 9 页 356 数字未变，见 `mutation-scope.json` |
| 本地验证回读 | 456 passed（156.97 秒）、7 checks 退出码均 0 | 最新 run `.runtime/validation/20261009-052126-c6f21459`，154 个输入指纹匹配当前实现 |
| 最终交付审计 | 待根任务 snapshot 后执行一次 | 本子任务未运行 audit，旧 passed 收据不能绑定新的 PPT 哈希 |

Word 封面新名称保持两行完整，概述无溢出；原模板大面积留白为既有版式建议。其它品牌变化页的实际原生检查在 `.runtime/material-ontolens-brand-qa-20261008`，本轮其它幻灯片字节未变。截图细字仅作界面示意，详细阅读仍应打开实际工作台。

## 第 10 页截图与来源

源图 `.runtime/ontolens-D1.1-final-home-1440x1230.png` 是实际存在、核对并查看的精确 1440×1230 viewport，SHA256 `D89B08BAC3D0C6D611C3B5DCD14099A9DF802B1E580D239BC78BEEC38FC4FBBB`。截图来自 D1.0-6 工作台，运行记录 `run_5b16db52eb994522b2c8`，合成申请日期 2026-09-28，ALLOW 100 mL，选中 stu01 来源及原文同屏；捕获收据为 `.runtime/ontolens-D1-final-screenshot-receipt.json`。

PPT 图片位置 `/slide[10]/group[@id=6]/picture[@id=5]` 保留原 x/y/width/height。可见 caption 为“D1.1 当前首页结构示意 · 尚未核验”。`images/image-8-1.png` 和 `svg_final/10_demo.svg` 内嵌 PNG 均与源截图字节完全相同，`svg_output/10_demo.svg` 保留原工程图片路径。该截图替换真实完成，没有以说明改字或旧图替代新版证据。

当前截图只证明本地合成资料运行的 UI 状态。实际行业应用、完整 Nexent 参赛演示、独立冷启动、长期稳定性及生产验收仍未完成；Gitea 暂缓，无推送或正式发布。本轮未添加分工表或队友责任安排。旧 286 generated 导出及此前 QA 收据均保留其历史范围，不改称当前导出。

