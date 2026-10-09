# 格物镜 · OntoLens

**可追溯的实验室危化品领用核验工作台 · v0.4.0 · D1.1**

格物镜把申请、人员授权、批次、柜位、库存和规则放进同一次核验。确定性程序给出 `ALLOW / DENY / LIMIT / ISOLATE`；资料缺失、授权失效或单位不一致时保持 `needs_review`、`decision=null`，显示补件建议。每次记录绑定申请、快照和原文，可回查、追加复核及导出离线重算。

v0.4.0已加入带账户的业务工作区：新库为空，不自动填演示事实；获授权的六类台账经导入、预览检查和管理员显式发布后可用于实际业务资料核验。软件记录核验结果，实际出库仍遵循本单位审批流程。操作者填写的用途/授权说明不等于来源真实性或专业审核证明。

**发布状态：已推送到 Gitea。** 私有仓库：[fulao/OntoLens](https://git.fulao.cc/fulao/OntoLens)，`main` 提交 `92f2c2c8c17647082227e9209efc2a7f0cf14d04`。当前业务流程、456 项全量回归、隔离容器和 `gpt-6-sol` Nexent 收据均已通过；真实行业效果、独立专业审核、Linux 新机冷启动和比赛正式提交单独保持未完成，不将这些研究门槛误称已满足。

## 快速启动业务工作区

要求Python 3.11+，使用完整源码目录。默认仅监听本机 `127.0.0.1:8768`；核心核验不需要Docker或模型账户。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[workbench,jev,test]"
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-operational.ps1 -Bootstrap
```

首次 `-Bootstrap` 只在账户文件不存在时创建随机管理员。用户名为 `admin`，密码仅写本机 `.runtime/operational/initial-admin.txt`，不会打印或进入源码。打开 [业务工作台](http://127.0.0.1:8768/)，在本机查看该文件登录，然后用交互命令改密码；确认新密码可登录后删除初始密码文件。

```powershell
.\.venv\Scripts\python.exe scripts/manage_access.py --auth-file .runtime/operational/accounts.json set-password admin
```

以后启动省略 `-Bootstrap`；连接当前本机Nexent可加 `-NexentUrl http://127.0.0.1:13000`。只检查条件用 `start-operational.ps1 -CheckOnly`；改变端口用 `-Port`。默认数据库、账户、会话位于 `.runtime/operational/`。业务入口拒绝复用当前active为合成演示的数据库，保留原库；不删除或重置旧演示数据。

Linux/macOS使用同一个Python入口；以下是跨平台命令，当前实测平台为Windows，Linux独立安装及Docker新机冷启动仍需新验收。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[workbench,jev,test]'
.venv/bin/python scripts/run_operational.py --bootstrap --host 127.0.0.1 --port 8768
```

详细首次启动、账户、台账格式、备份和Docker步骤见[业务部署说明](docs/38-operational-deployment.md)。Docker定义在[deploy](deploy/README.md)，容器实际构建状态以本轮新收据为准。

## 导入并发布六类业务台账

登录后进入“原始资料”→“导入业务台账”，先查看/下载模板，再提供以下六份资料及用途、授权依据、授权方、记录日期和本地处理确认。

| 文件组 | 内容 | 格式 |
| --- | --- | --- |
| people | 人员、角色、停权、类别及授权有效期/依据 | JSON/YAML/CSV |
| chemicals | 危害类别、单位和单次领用上限 | JSON/YAML/CSV |
| lots | 物料批次、库存和批次状态 | JSON/YAML/CSV |
| cabinets | 柜位及允许类别 | JSON/YAML/CSV |
| issues | 尚未归还或同会话已领用类别 | JSON/YAML/CSV |
| rules | 规则版本、学生比例、冲突类别与制度开关 | JSON/YAML |

每份为1–2,000,000字节。系统保留六份原始字节与六份规范化来源，核对schema、引用、日期、单位、hash及候选不变量。导入先形成候选，不直接生效；管理员预览影响、确认发布，使用 `expected_active` 防冲突。业务发布/回滚使用 `confirm_publish=true`，合成兼容路径才使用 `confirm_demo`。

六类台账导入均不授予模型外发权限；非合成people固定为private。公开制度文本不能自行授予某个人业务权限。单份资料上传、公开条款检索、OCR/人工摘录和候选建议分别保留其真实性质。

## 已实现的软件能力与边界

| 能力 | 当前行为 |
| --- | --- |
| 业务空工作区 | 新HTTP工作区默认operational；发布有效台账前引导导入，不填假人员/库存 |
| 账户与操作权限 | admin/operator/reviewer/viewer，PBKDF2-SHA256 600,000次，8小时会话、CSRF、撤销与账户审计绑定 |
| 核验和证据 | 四种决定与缺件状态；source/locator/hash、快照、申请及复核绑定 |
| 数据版本 | 六表候选、原文与规范化检查、影响预览、管理员CAS发布/回滚 |
| 复核与复现 | 引用默认未选，追加不改判；原始来源闭包导出，脱库重算 |
| D1.1界面 | 展示首页、真实四统计、拖动/键盘侧栏；品牌旁44px折叠图标，去除无用侧栏卡和宽度按钮 |
| 模型辅助 | 私有/未获准来源只发送枚举与计数最小摘要，不发送ID、引文、数量、日期 |
| Nexent与JEV | 专用无工具Nexent解释实例、实时观察状态；JEV显式live仅对获准来源，不改业务决定 |

角色是操作级权限，当前不是多租户或按每份文档分配ACL。普通业务窗口使用带认证的业务入口；直接启动未配置账户的裸HTTP应用只允许本机，不作为共享部署入口。

## 模型、JEV与当前Nexent

模型配置留在本地 `.env`/环境变量：`PEIWU_MODEL_BASE_URL / PEIWU_MODEL_NAME / PEIWU_MODEL_API_KEY / PEIWU_MODEL_PROTOCOL`。全部证据获准且非private时可发获准证据；否则固定最小摘要白名单，模型不能读取原文，也不能改判。

JEV按钮显式在线调用 `live=true`；只有明确允许外发且非private来源才可发送。离线普通检索继续可用。配置齐全、一次调用成功和概率信号不等于语义准确率评测。

Nexent产品解释使用 `ontolens_result_explainer` 专用实例，要求无工具、无技能、无协作Agent；只发送去标识结果摘要。状态来自 `/api/integrations/nexent` 的当前观察与 `observed_at`，历史ready报告不参与判就绪。宿主Web端口本轮从受Windows保留限制的3000改为13000，容器内仍3000；2026-10-08 12:02–12:04 UTC已通过当前7个MCP调用、专用Agent2无工具真实解释及Agent1真实模型/工具编排，active未改变。证据是本轮合成链路，不是行业效果。

## 验证、规划和源码发布

本轮专项账户/台账/HTTP流程结果分别记录，互有重叠，不能相加当完整测试数。2026-10-09 完整七阶段通过：456 passed；browser、MCP、资产、JEV离线预检、pip、全前端 JS 语法检查均退出 0，收据见 `artifacts/local-validation-report.json` 与 `artifacts/source-validation/20261009-052126-c6f21459/`。旧356是D1.0历史基线。

```powershell
.\.venv\Scripts\python.exe scripts/validate_local.py
.\.venv\Scripts\python.exe scripts/check_source_release.py --snapshot-validation
.\.venv\Scripts\python.exe scripts/audit_deliverables.py
.\.venv\Scripts\python.exe scripts/check_source_release.py
```

验证使用显式synthetic隔离数据库；不向业务账户/私有台账库跑写入测试。导出可用 `scripts/verify_evidence_export.py` 校验与重算；未签名包证明内部一致，不能认证来源或全部历史未被删除。

[规划与里程碑](docs/37-teammate-handoff.md)集中列出已完成、未完成、验收条件和拓展方向；[源码交付规范](docs/36-source-layout.md)规定白名单、日志和排除项。Gitea 推送仅代表源码交付完成，不代表真实行业效果或正式参赛提交完成。

[design.md](design.md)是唯一设计入口，[design/](design/README.md)按基础、首页、交互、动效、无障碍和验收拆分。当前视觉按用户参考删繁，功能兼容与dirty/stale保护继续有效；资产出处见[清单](design/asset-manifest.json)。

## 目录与兼容

`src/peiwu`为内核、HTTP/MCP和前端；`data`含规则/测试资料和公开摘录；`tests/scripts`用于验证及启动；`deploy`提供容器定义；`nexent`提供接入模板；`docs/design`为交接规范；`submission`为参赛草稿；`.runtime`仅本机状态。

产品叫“格物镜 · OntoLens”，Python包、环境变量和 `peiwu-replay-1` 等协议保留peiwu兼容。`.env`、accounts、会话、数据库、上传和私有导出不入库。不要仅复制静态网页或Python包代替完整资源检出。变更见[CHANGELOG](CHANGELOG.md)。
