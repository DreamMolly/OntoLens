# 格物镜 · OntoLens v0.4.0 演示脚本

只在独立演练库操作，明示资料性质；不要对日常业务库运行写入 smoke，不执行真实出库。账户身份不等于专业资质，正式模板个人字段仍由队员确认。

## 评审主线：同一申请，三个核验结果

评审也可从仓库根目录直接运行以下命令。它使用本机隔离的合成数据执行这条演练，输出目录中保留三次核验的 `report.json`、发布前后两份证据包及离线校验结果。程序无需启动浏览器或 Nexent。

```powershell
.\.venv\Scripts\python.exe scripts/verify_competition_demo.py
```

用合成授权变更演示知识快照如何影响可追溯决策。先按[合成演练](../README.md#合成演练)启动，使用一个新的演练库路径。打开工作台，确认显示“合成演示空间”，当前生效快照为 `demo-initial`。预先保存 UTF-8 文件 `review-demo-policy.md`，内容如下。

```text
# 合成授权调整
stu01 授权仅保留 ACID。
```

| 顺序 | 屏幕操作 | 核对什么 |
| --- | --- | --- |
| 1. 记录基线 | 在“核验申请”点“正常申请”，将日期设为 `2026-09-23`，执行“核验并记录证据” | 得到 `ALLOW`。打开人员授权证据，记下原始快照并下载第一份证据包 |
| 2. 上传变更 | 在“原始资料”选择合成来源并导入上述文件 | 可以回查 `L2` 原文。此时仍是 `demo-initial` |
| 3. 预览影响 | 在“数据版本”选择 `stu01`，只勾选 `ACID`，选择上传文件及 `L2`，填写变更说明并创建候选 | 第一步保存的申请在影响预览中由 `ALLOW` 变为 `DENY`，原因是 `CLASS_NOT_AUTHORIZED` |
| 4. 发布并重算 | 核对来源和预览，勾选合成确认，点“发布演示版本”并确认。保留原申请字段，在“核验申请”重跑 | 当前快照切换，结果显示“本次打回”。旧记录仍引用原快照。下载第二份证据包 |
| 5. 回滚再重算 | 在“数据版本”确认回滚到 `demo-initial`，回到“核验申请”再跑一次 | 结果恢复 `ALLOW`。运行记录中仍可查看新快照下的 `DENY` |

把两份下载的证据包分别传给离线核验器。以下文件名是示例，替换为实际文件路径。

```powershell
.\.venv\Scripts\python.exe scripts/verify_evidence_export.py "before.json"
.\.venv\Scripts\python.exe scripts/verify_evidence_export.py "after.json"
```

两份导出都应返回 `passed: true`。这一段验证的是合成授权事实经人工确认后进入新快照，并影响后续核验。关系类型、属性和行业标准的对齐需要独立演示和验收。

## Nexent 同台展示

平台就绪时，先在 Nexent 对同一组**合成**输入运行 Agent，在执行轨迹打开 Skill 读取、`evidence_lookup`、`graph_query` 和 `decision_check`。向评审展示工具返回的 `action`、`version_id`、`snapshot_hash`，再到工作台看同一生效快照和来源。发布和回滚由工作台操作。平台不可用时仍可完成上面的工作台演练，并将 [2026-10-09 Agent 运行收据](../artifacts/nexent-agent-run-current.json)标为历史记录。

在已完成绑定的演练环境中，[统一启动入口](../docs/30-demo-startup.md)准备工作台与平台。工作台在本机 8765 端口，并需先保留一个源自 `demo-initial` 的合成变更候选，供候选工具检查。Nexent 地址按本机配置读取。

```powershell
.\.venv\Scripts\python.exe scripts/probe_nexent_live.py --agent-run --output artifacts/nexent-live-competition-rehearsal.json
```

验收时核对本次收据的 `observed_at` 和 `agent_run_checks`。开启 `--agent-run` 后，脚本要求本轮成功返回、出现 Skill 读取及三个 MCP 调用，且 Agent 答复与独立 `decision_check` 的决定、版本、快照哈希和证据数一致。缺项或不一致会使退出码非零。评审可以打开平台轨迹核对实际读取的 Skill，单独的工具测试与 Agent 调用轨迹分别留证。

| 赛题能力 | 当前可展示 | 还缺的验收 |
| --- | --- | --- |
| 异构资产认知 | 台账与文本来源，图片加人工摘录，资产及关系候选回指原文 | 自动图文抽取和独立标注评估 |
| 低资源本体与动态更新 | 目录、别名、关系与 schema 候选，[公开制度映射候选](public-data-demo.md#展示一条本体映射候选)，以及上面的合成事实发布流程 | 领域审核、映射上线后的版本治理与决策影响验证 |
| 跨资料决策与追溯 | 固定快照核验、缺件复核、原文定位、离线重算 | 经授权业务资料的盲评与错误放行、误拒统计 |
| Nexent 平台 | MCP 工具、Skill 导入包、历史模型轨迹 | 当前环境从导入到实际 Agent 调用的复验 |

## A. 业务空库与登录

按 `docs/38-operational-deployment.md` 首次准备账户和独立数据库；业务入口 `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-operational.ps1 -Bootstrap`，默认 `http://127.0.0.1:8768/`，Nexent 本机宿主 `http://127.0.0.1:13000/`、容器内部 3000。Bootstrap 会创建账户/会话文件，不能称无写入。初始密码只在本机读取，不截图或提交。准备过的历史合成工作台恢复仍用 start-demo.ps1，实际端口以启动收据为准。

## B. 六台账到版本

1. 登录管理员，确认 operational_empty，没有 demo-initial 事实。
2. 在原始资料按模板准备 people、chemicals、lots、cabinets、issues、rules，明确用途、授权声明和演练性质。
3. 导入后检查六原始/六规范化来源、hash/定位/版本以及字段、引用、单位、日期错误；上传只创建候选。
4. 预览影响，以 confirm_publish=true 和 expected_active 显式发布；遇到 active 改变应刷新重做预览，不能强行覆盖。
5. 切换 operator 展示可核验/导入但不能发布；reviewer 可追加跟进，viewer 只读。演练角色实际权限由服务端核对。

## C. 核验、原文、复核与导出

按演练台账依次展示正常、冲突、超量、过期批次和缺件；程序返回 ALLOW、DENY、LIMIT、ISOLATE 或 needs_review/decision=null。缺件不猜业务决定。

打开 source_id/locator 原文，核对 quote 和 SHA256；改申请立即 dirty/stale，历史切换保持当前草稿。追加复核的 actor 来自登录账户，记录不改变旧决定；补齐资料后要新核验。导出固定当时 run/快照，用 verify_evidence_export.py 离线重算，不能当作来源真实性认证。

演练授权变化时先提候选、预览、确认发布，再核验并回滚。过去运行保持原快照；图像只保存预览/人工摘录，不称 OCR 或自动图像理解。

## D. 当前 Nexent 和可选模型

容器业务、Nexent 七工具、模型编排与无工具解释分别查看当前收据。逐项工具成功不等于模型一次使用全部工具；记忆隔离与私有原文不外发只按实际请求范围报告。独立新机、真实行业资料和专业审核另验。

展示当前 observed_at、model_bound 与实际生成结果；不从历史 ready 推当前可用。私有或未获准来源只给模型固定枚举/计数，JEV 必须 live=true 且来源获准、非 private；服务失败不改变程序核验。Responses/JEV 单次真实调用只证明该次连通性，不是全协议、稳定性或行业准确率。

## E. 界面与答辩口径

D1.1-7 品牌旁折叠图标、边缘拖动/键盘调宽，九个单选控件与四个日期控件各 6/6 隔离测试通过、0 页面错误、0 外站请求；证据为 `artifacts/workbench-select-interaction-report.json` 与 `artifacts/workbench-date-interaction-report.json`。真实设备/读屏另验。P10 图片是当前首页结构示意，未运行核验；现场演练须用实际结果页面，不能将首页或保存的历史 ALLOW 伪作当前核验。

完整软件结果见 `artifacts/local-validation-report.json`；导入、核验、复核和导出功能不表示行业字段适用、专业审核、独立评测、新机、长期稳定性或正式提交已完成。源码入口见根 README。
