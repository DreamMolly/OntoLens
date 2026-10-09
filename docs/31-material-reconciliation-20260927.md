# 交付材料对账 QA（2026-10-09）

本记录区分 v0.4.0/D1.1 当前原生材料、历史生成导出与交付审计，不证明模型效果、行业安全性、正式提交资格或专业审核完成。

## v0.4.0/D1.1 最终对账更新（2026-10-09）

当前 Word/PPT 已更新为本轮全量 **456 passed**，PPT 第 9 页同步 456，SVG、notes 与可编辑 spec 同步；旧 356/286 导出继续保留为历史记录。

`artifacts/local-validation-report.json` 为 passed，7 个阶段全部 exit 0，154 项输入指纹一致；日志快照为 `artifacts/source-validation/20261009-052126-c6f21459/`。`artifacts/operational-deployment-20261009.json` 为 Docker 业务部署 passed，30 项 checks 通过，`real_industry_data_used=false`；`artifacts/nexent-model-configuration-20261009.json` 为当前 gpt-6-sol/model_id=2 配置 passed。

`artifacts/workbench-select-interaction-report.json` 与 `artifacts/workbench-date-interaction-report.json` 各 6/6 passed，均为隔离合成浏览器控件验证。P10 仍是“D1.1 当前首页结构示意 · 尚未核验”，不表示 ALLOW 或真实业务结果。外部冷启动、真实行业资料、专业审核、长期稳定性和正式提交仍待验证。

最终材料 QA 收据：`.runtime/material-final-456-20261009/receipt.json`。

当前原生文件哈希：Word `A978F8A33019EE9552EB23E0ACA6D9CE1727E55D0F98403EB251D16941D68B35`（4页，48段，174词，2675字符，Word issues 26）；PPT `B40C0A15EC620B48E8DBD1FE163A592169CD04D7A12335122E9ADE8E64D51304`（11页，PPT issues 0）。本次Word仅将31项检查改为30，PPT仅修正notes8/9的检查数、156.97秒与正式日志目录；所有幻灯片内容及几何字节未变。原生接触表为 `.runtime/material-final-456-20261009/word/contact-after-doc-fix.png` 与 `.runtime/material-final-456-20261009/ppt/contact-after-doc-fix.png`，已检查无新增溢出或重叠。

本节之后的 2026-10-08 内容属于历史对账，不绑定当前 Word/PPT 哈希或 456 收据。

## 历史 v0.4.0/D1.1 对账（2026-10-08）

当前材料采用空业务库、账户角色、六原始/六规范化台账、候选检查/管理员发布、旁路核验、复核和导出等实际软件口径。D1.1 P10 使用当前首页结构示意，不冒充 ALLOW 100 mL 当前运行；行业字段适用、独立评测、专业审核、长期稳定性和正式提交仍待完成。

`artifacts/operational-deployment-20261008.json` 为隔离测试 fixture 的 `passed`，实际 26 项 checks，`real_industry_data_used=false`；后续专用 Agent 2 的 `memory_retrieval_disabled=true`、`tool_calls={}` 与 `source_text_sent=false` 仅属于该收据。早先 Nexent 收据的自动 `search_memory` 保留历史说明，不能用旧空 tool_calls 推断绝对零工具。

源码全量最新 run `.runtime/validation/20261008-124910-3fecd725` 失败（pytest/browser exit 1），不填 v0.4.0 全suite 通过数；根任务应在最终回归后一次更新 Word/PPT 计数和收据。

本段保留为2026-10-08历史材料快照：Word 4 页、48 段、176 词、2567 字符，Word issues 26；P10 使用 1440×1230 首页结构示意，媒体 SHA256 `D89B08BAC3D0C6D611C3B5DCD14099A9DF802B1E580D239BC78BEEC38FC4FBBB`，没有改变原图片框几何。当前全suite结果见上方2026-10-09章节，旧356只作历史基线。

## 历史 D1.0-6 权威对象（2026-10-08 19:01）

| 对象 | 实际结果 |
| --- | --- |
| `officecli` | `1.0.155`，`OFFICECLI_NO_AUTO_RESIDENT=1` |
| `submission/peiwu-development-design-draft.docx` | SHA256 `a5d537e7541aede1f590527ab69f50cf82b7f1b81205995ec2b372a680a52140`；该阶段原生稿，回读 `356 passed` |
| `submission/peiwu-presentation-draft.pptx` | SHA256 `785054a30713b762ef3274bbd4097c7fefcd57b95e522cdcd42e595906b1046e`；该阶段原生稿，第 9 页 `356 passed` |
| 该阶段材料 QA | `.runtime/material-ontolens-D1-snapshot-qa-20261008/receipt.json` 绑定上述哈希；Word 哈希未变，沿用品牌 QA；PPT 第 10 页及全 11 页接触表原生渲染、已查看 |
| 该阶段本地验证 | run `artifacts/source-validation/20261008-104853-561a21f6`；356 passed（97.34 秒），7 checks 退出码均 0，128 个输入指纹匹配该阶段实现；仅本地隔离验证 |
| `artifacts/deliverable-consistency-report.json` | 既有 passed 收据验证的是品牌修订前文件；当前品牌文件哈希已变化，当前冻结材料待根任务重新审计，不能沿用旧 passed 当作本轮完成 |

## 历史 D1.0-6 复核结果（2026-10-08 19:01）

| 检查 | 结果 | 边界 |
| --- | --- | --- |
| Word/PPT schema | 各退出码 0、0 errors | 当前原生文件通过 |
| PPT issues | 0 issue | 当前结构/格式检查通过 |
| Word issues | 24 条提示 | 3 个空段、16 个首行缩进、5 个标点提示，原模板未改 |
| Word stats/native PNG | 4 页、48 段、180 词、2676 字符；4/4 查看 | 该阶段截图前后哈希一致，第 4 页 `356 passed` 可见 |
| PPT native PNG | 11/11 查看 | 第 9 页数字 356；未见新截断、重叠、越界或低对比度 |
| 逐页结果 | 见 `docs/24-material-qa.md` 与 receipt | Word 封面大留白为建议；工作台截图是界面示意 |
| 当前冻结材料交付审计 | 待根任务 snapshot 后执行一次 | 本材料子任务未运行 full validation 或 audit；当前材料/源码已冻结，不能沿用旧材料哈希的 passed 收据 |

## 原生修订与生成导出边界

历史生成文件 `submission/ppt-master/peiwu_review_ppt169_20260927/exports/peiwu_review_20261007_154647.pptx` 的 SHA256 是 `703e3a5463cdaf3bcd6f5d9e9f2761dca990d84f2c99ea5e59201204ccf024a7`，当时实际回读第 9 页为 `286 passed`，不是后续 356 或当前 456 原生稿。

`validation/peiwu_review_20261007_154647.report.json` 的 11/11 quality pass，以及旧 `validation/peiwu-presentation-draft.delivery.json` / `readback.md` 都属于当次生成/回读记录。旧 readback 包含 286，不能改说明后声称它们验证了当前原生修订。2026-10-08 的可编辑 SVG/notes 曾同步 356，当前这些编辑源已经同步 456；这不表示旧时间戳的导出 PPTX 已重新生成。

## 数字与事实边界

- 旧原生稿回读 `356 passed` 仅作历史阶段基线；v0.4.0 当前全suite 为首节的 456。217、218、271、276、284、286 等旧数字仍为各阶段记录，不全局替换。
- `docs/22-citation-review.md` 的 29、132、115、121 保留原样，不改写成全量结果。
- `60/60`、`unsafe_release=0`、7 个 MCP 工具、一次历史 Agent/run 保留合成、平台回放或历史证据范围，不改写成行业或模型准确率、独立冷启动结果。
- 官方字段、队员确认、真实资料、领域审核、独立冷启动、长期稳定性和正式提交仍需各自证据；材料 QA 不关闭这些边界。

## 可复现命令

```powershell
$env:OFFICECLI_NO_AUTO_RESIDENT='1'
officecli validate submission/peiwu-development-design-draft.docx --json
officecli validate submission/peiwu-presentation-draft.pptx --json
officecli view submission/peiwu-development-design-draft.docx issues --json
officecli view submission/peiwu-presentation-draft.pptx issues --json
officecli view submission/peiwu-development-design-draft.docx screenshot --render native --grid 2 -o .runtime/material-ontolens-brand-qa-20261008/word/contact.png
officecli view submission/peiwu-presentation-draft.pptx screenshot --render native --grid 3 -o .runtime/material-ontolens-D1-snapshot-qa-20261008/ppt/contact.png
```

逐页 PNG 另以单页 `--page N` 实际生成，路径与哈希在 receipt。以下为品牌/UI 修订前的历史审计记录：材料 QA 阶段只运行一次 `.venv/Scripts/python.exe scripts/audit_deliverables.py`；原生稿哈希与两份材料 356 数字已核对一致。后续 v0.3.0 代码更新重新执行了隔离验收，356 个测试与全部 7 项检查通过，112 个输入指纹对应当前实现。7 份原始日志已按字节快照到 `artifacts/source-validation/20261008-071821-75b93edb`，再运行交付审计通过，当前收据为 `artifacts/deliverable-consistency-report.json`。审计继续引用已有平台/模型历史证据，未重新探测当前平台在线状态；`goal_complete=false` 所表示的真实行业、领域审核、独立冷启动、长期稳定性与正式提交依赖不因交付一致性通过而消失。v0.3.0 是未推送的本地候选，不作为实际应用或完整参赛展示已经验收的依据。



## 历史品牌修订边界（2026-10-08）

当时 Word/PPT 与 editable SVG/spec/notes 的产品名称已同步；文件名、peiwu 工程引用和历史 generated 记录保留。两份 schema 均 0 errors，PPT 0 issues，Word 24 原有提示；新名称对应的变化页已原生渲染检查，数值与几何不变。品牌 QA 的 Word 为 `a5d537…`、PPT 为 `c97f1e…`，旧 UI 图片当时等待替换，见 `.runtime/material-ontolens-brand-qa-20261008/receipt.json`。随后 D1.0-6 快照阶段使用下节 `050e8e…` 合成 ALLOW 截图；再后续 D1.1 替换为 `D89B08…` 尚未核验的首页示意。

既有全量及交付审计属于品牌/UI 修订前证据，旧 356/7 检查/128 输入验证属于历史范围，不绑定当前 v0.4.0；当前最终 audit 已在源码推送前通过。源码已推送到私有 Gitea，真实行业应用、完整专业评测、独立冷启动和正式参赛提交仍未验收；无分工/责任表新增。

## 历史 D1.0-6 截图冻结 QA（2026-10-08）

当时 PPT 第 10 页图片、editable `images/image-8-1.png` 与 `svg_final/10_demo.svg` 嵌入媒体均为 `.runtime/ontolens-D1-material-1440x1230.png` 的精确字节，SHA256 `050e8e661c29448d61a5c8927eded0305e245099650b3e007f603228ead06d50`。该图绑定 `run_5b16db52eb994522b2c8`、合成 ALLOW 100 mL 与 stu01 原文，依据 `.runtime/material-ontolens-D1-snapshot-qa-20261008/receipt.json`。变化仅限该页图片/caption/notes 与对应 editable 资料；其它幻灯片及 notes 字节未变，数值几何与 356 未变。Word 仍 4 页、24 条提示，PPT 11 页、0 issues；两份 schema 0 errors。此描述不适用于后续 D1.1 的 `D89B08…` 首页示意。

该历史阶段隔离验证 run 为 `artifacts/source-validation/20261008-104853-561a21f6`，356 passed（97.34 秒）、7 项检查均退出 0，128 个输入指纹匹配该阶段实现；材料子任务只核对已有报告，没有重跑全量验证或交付审计。当前 2026-10-09 材料、源码推送与 456 最终结果见首节；真实行业资料、专业审核、外部冷启动、长期稳定性与正式参赛提交仍待各自验证。
