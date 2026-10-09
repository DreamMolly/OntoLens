# 本机演示启动

此入口用于已经准备好、已迁移到项目 F 盘的 Nexent 演示环境。新机器的依赖安装、数据恢复和模型授权仍需要按部署说明准备，不能把同机恢复写成独立冷启动。

## 使用

在项目根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1
```

只核验启动条件：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1 -CheckOnly
```

Python 核心入口 `scripts/start_demo.py` 默认只预检，显式 `--apply` 启动服务。已有服务通过检查后直接复用；启动日志和报告保存在项目目录。

## 检查范围

- 令牌复用 `.runtime/peiwu-mcp-token.txt`，缺失时报告准备不足。令牌不写入命令行或报告。
- Nexent 数据固定为 `.runtime/nexent-desktop-data`，工作目录固定为 `.runtime/nexent-home`。每个持久化挂载先与解析后的 Compose 配置核对；旧 `/mnt/f/...` 或现有容器的挂载漂移都会阻止启动。
- PostgreSQL 的 `PG_VERSION`、既有工作台数据库和恢复记录用于确认这是已准备的本机实例。缺失时不初始化空库。
- 不下载镜像、不创建模型、不重新导入 Agent、不迁移数据、不删除卷。已有镜像不足时准确报错。
- 8765 已有合法工作台则复用；其他服务占用端口则报错。MCP 还须从容器侧使用既有令牌核验。
- 通过状态和健康检查后才能报告可用，容器 `running` 本身不足以证明数据处理 API 已就绪。

## 2026-09-27 的重启修复

Docker 恢复后，原 data-process 抢先访问尚未可用的 PostgreSQL，随后失败回退尝试导入不存在的 `data_process_service:app`。Windows 覆盖配置改为官方 `start-backend.sh` 的 `wait` 模式，待数据库和迁移就绪后运行主入口；保留 Ray 与 Celery 工作者。

PostgreSQL 增加 `pg_isready` 健康检查；data-process 增加只读 `/tasks` JSON 探针。该探针证明 API 与任务查询可用，不代表 OCR、embedding 或真实行业文件处理效果。

## 2026-09-27 实际恢复验收

统一入口已在当前已准备机器上执行 warm、全停后恢复和二次幂等重跑。warm 运行复用了 10 个 Nexent 容器与既有工作台；随后确认 data-process `/tasks` 返回空列表，并核对 8765 监听进程链确实来自项目 `start-workbench.ps1` 和 `.venv`，再只停止本项目 10 个容器及该工作台进程。

第一次全停恢复发现 Windows 将 TCP 4930-5029 列为排除范围，原宿主端口 5013 因而无法重新绑定。没有删除系统排除项、重启 Docker 全局服务或删除容器/卷；Windows 覆盖配置只把 Northbound 宿主映射改为 `127.0.0.1:15013 -> 5013/tcp`。该变更仅重建一次 Northbound，其他 9 个容器 ID 和全部挂载保持不变。

最终配置下再次全停后，`start-demo.ps1` 成功恢复原 10 个容器，容器 ID 均未变化；工作台重新启动并通过容器侧认证 MCP `initialize`/`tools/list`。紧接着第二次运行全部复用，10 个容器没有创建或重建，工作台监听 PID 保持 41264。两次运行均确认 Agent `1` 仍绑定 `model_ids=[1]`、MCP `1` 为 healthy、active snapshot 为 `demo-initial`、工作台 SQLite SHA256 未变化、data-process 任务数为 0；Northbound 的 15013 根路径返回 404，证明端口可达但根路由不是业务成功断言。

目标测试为 `14 passed`。脱敏基线、端口阻断、修复和两次最终结果见 `artifacts/demo-startup-acceptance-20260927.json`，对应成功报告为 `artifacts/demo-startup-20260927T102106.807622Z-apply.json` 与 `artifacts/demo-startup-20260927T102155.062033Z-apply.json`。该结论只覆盖当前已迁移本机的恢复与幂等重跑，不代表新机安装、长期稳定性、真实资料效果或专业审核。

## 最新恢复状态（北京时间 2026-09-27 21:57:13）

此前本轮只读检查曾观测到 Docker CLI 可用，但 Docker Desktop Linux 引擎不可达，`desktop-linux` 的 API named pipe 不存在，工作台与 Nexent 端口也未监听。当时 `DemoStartup.execute(False)` 按预检门禁返回 `docker_unavailable`，没有启动 Docker、停止/删除容器、迁移数据或改写报告。这次停机观测作为历史保留，不再代表以下恢复完成时的状态。

随后执行 `start-demo.ps1` 成功，权威报告为 `artifacts/demo-startup-20260927T135713.429254Z-apply.json`；报告记录时间为 `2026-09-27T21:57:13.426508+08:00`（北京时间，对应 UTC `2026-09-27T13:57:13.426508+00:00`），结果为 `ready=true`、`status=ready`。入口启动了 Docker Desktop 和工作台，复用原 10 个 Nexent 容器，没有新建或重建容器；全部容器为 running，其中 PostgreSQL、data-process、Redis、Elasticsearch 的健康状态为 healthy。Northbound 宿主映射仍为 `127.0.0.1:15013 -> 5013/tcp`。

工作台恢复为 `synthetic_demo`，active snapshot 为 `demo-initial`；容器侧 MCP 可达并列出七个工具，Nexent Agent `1` 可用且仍绑定 `model_ids=[1]`，MCP `1` 为 healthy。本轮报告没有记录新的模型调用、令牌变更、镜像拉取/构建或数据迁移。上述是该时间点已准备本机的恢复与就绪证据，不等同于新机器独立冷启动、持续负载或长期稳定性验证，也不证明真实资料效果或专业审核；先前的全停恢复与幂等重跑记录继续保留。

## 2026-09-29 当前复核

北京时间 18:32 的一次只读部署审计确实记录了 Docker 引擎不可达（`artifacts/nexent-deployment-audit-20260929-core.json`）；该失败状态没有复用旧成功报告。随后再次运行统一入口，权威报告为 `artifacts/demo-startup-20260929T104316.193534Z-apply.json`，记录时间为北京时间 18:43:16，`ready=true`。本次复用 10 个既有容器，未创建或重建容器；PostgreSQL、data-process、Redis、Elasticsearch 最终健康，工作台 PID 为 36020，容器侧 MCP 列出七个工具，Agent `1` 仍绑定模型 `1`，Northbound 仍为 `127.0.0.1:15013 -> 5013/tcp`。这只证明该时间点本机恢复成功，不能替代独立冷启动或长期稳定性证据。

## 2026-10-02 当前状态

本日只读部署审计观察到 Docker Desktop Linux 引擎不可达，报告为 `ready=false`、`issue_codes=[docker_inspection_failed]`，见 `artifacts/nexent-deployment-audit-20261002-current.json`。该失败报告没有复用 9 月 29 日的成功状态，也没有启动、停止、删除容器或改写持久化数据。此前的 `ready=true` 报告仍只代表对应历史时间点；若要重新取得当前平台证据，应在 Docker 恢复后再次运行统一入口并保留新的时间戳报告。

随后再次运行统一入口已恢复当前环境，权威报告为 `artifacts/demo-startup-20261002T082333.742005Z-apply.json`，结果为 `ready=true`；最新只读部署审计为 `artifacts/nexent-deployment-audit-20261002-live.json`，`ready=true` 且无 issue。此次恢复复用了既有 Nexent 容器并完成工作台、容器侧 MCP 七工具和 Agent/model 绑定复核；这只证明 2026-10-02 该时间点的本机可用性，仍不替代独立冷启动、长期稳定性或真实资料验证。
