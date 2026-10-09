# Windows 部署与导出复核

## 2026-09-26 最终结果

- Docker Engine/Client 更新到 29.8.0 后，旧 `/mnt/f/...` 仍落在约 128 MB 的内部设备；更新本身没有修复挂载。
- 使用 `scripts/migrate_nexent_windows_data.py --apply` 停止本项目容器，冷拷贝当时容器可见状态的 1,812 个文件、约 53.8 MB 到 `.runtime/nexent-desktop-data`，生成目标目录数量、字节数和摘要；首版脚本没有保存源摘要对照，因此不声称字节级连续性。原源与既有备份未删除，未移动 Docker Desktop 全局数据盘。
- Docker 更新后旧容器可见的 ES 目录为空。另在隔离副本中启动同版本 ES 检查保留的宿主目录，只发现 2 个 ES 自身隐藏系统索引、共 4 个系统文档，没有业务或知识库索引；当前集群重建同类系统索引但 UUID 不同。该检查排除了已知用户索引丢失主张，仍不等于更新前字节连续性。
- 更新前空配置库另存 `20260926-post-migration-pre-restore/pre-restore.dump`。经 SHA256 核对后恢复 2026-09-24 逻辑备份，取回 1 条 MCP、Agent 和 3 个 Skill；该备份早于模型配置，因此模型用本地密钥重新健康检查并绑定为 `model_id=1`，报告不保存密钥或端点。
- 拉取并启动官方 `nexent-data-process:v2.6.0`。部署审计当前 `ready=true`、10 个服务、0 个问题；ES 为 green，PostgreSQL 接受连接，Redis 返回 PONG。
- `.venv/Scripts/python.exe scripts/verify_nexent.py` 迁移后退出 0：七工具、四种决定、needs_review、引用哈希、重复决定和 ZIP 导出通过。脚本本次不调用模型；一次模型驱动 Agent/run 仍引用 2026-09-24 的合成运行摘要并单独保存摘要哈希。
- 当前剩余边界为真实资料、领域审核、费用/调用上限、独立冷启动和长期稳定性；不得把本机即时健康写成行业验证。

## 2026-09-26 中间故障记录

- 本机实际 Docker Desktop 安装位于 `C:/Users/leovo/AppData/Local/Programs/DockerDesktop`；启动后服务端返回 29.7.2，Compose 返回 v5.5.0。
- PostgreSQL 反复重启，实际日志为 `could not write to file "pg_wal/xlogtemp.29": No space left on device`。这不是模型绑定或 MCP 令牌错误。
- Elasticsearch 数据目录的 `df -h` 返回 `/dev/sde` 容量 128 MB、已用 116 MB、剩余约 2 MB（99%）。数据库和其他项目数据仍使用 `/mnt/f/...` 错误绑定；没有切换到 Windows F 盘。
- 只读部署审计退出 1，记录 `wrong_host_path`、`service_not_ready` 和 `missing_service`；本次报告为 `artifacts/nexent-deployment-audit.json`。
- Windows 原生 F 盘配置再次解析成功，脱敏预检见 `artifacts/nexent-migration-preflight-20260926.json`。目标 `.runtime/nexent-desktop-data` 尚不存在，未执行复制或切换。
- 用户回复“等我更新一下docker”；因此停止所有 Docker 操作，等待更新完成。此前已询问本项目冷拷贝和挂载切换授权，当前回复不作为迁移授权。
- 修复交付审计遗漏：失败平台报告、缺失检查、错配模型/Agent 运行不能再通过；部署审计在 Docker 不可达时写出脱敏失败报告，避免遗留旧成功。

下面为 2026-09-24 的历史部署记录；模型绑定及合成运行后来已于 2026-09-25 完成，当前运行可用性仍需恢复后复测。

日期：2026-09-24。报告使用 UTC 时间戳。本轮未安装新依赖、未删除数据、未移动 Docker Desktop 数据盘、未调用付费模型。

## 导出问题的真实原因

宿主机原始 HTTP 响应为 `HTTP/1.0 204 Intercepted by the IDM Advanced Integration`；在 nexent-web 容器内部访问同一个 Web 路由返回 `200 application/zip`。因此没有修改 Nexent 前端代码。

`scripts/verify_nexent.py` 现在区分正常导出、明确的 IDM 拦截和未知空响应。仅明确识别 IDM 时，从运行中的 Web 容器访问同一路由，不跳过 Web 直接伪称前端正常。未知 204 返回失败，不自动掩盖。测试见 tests/test_nexent_verification.py。

收紧端口并重新启动对应服务后，宿主机 ZIP 导出复测连续成功；这不证明 IDM 全局行为已永久改变，也没有修改 IDM 设置。原始结果：artifacts/nexent-export-host-recheck.json。正常导出与必要回退均可用 `.venv/Scripts/python.exe scripts/verify_nexent.py` 验证；实际平台导出包为 artifacts/nexent-agent-export.zip，源码构建包仍为 artifacts/peiwu-nexent-agent.zip。

## 已应用的安全变更

- nexent/windows.override.yaml 仅将 Web 3000 和 Northbound 5013 发布到 127.0.0.1；在当前 Compose 版本实际验证。
- 应用前比较了 nexent-web 和 nexent-northbound 的全部绑定源、目标和只读状态，确认与现有容器一致。
- 仅重新创建上述本项目服务，未启动依赖、未拉镜像。现有业务挂载、镜像、卷与其他项目容器未改变。
- 实际应用命令：`docker compose --project-name nexent --env-file third_party/nexent/deploy/env/.env -f third_party/nexent/deploy/docker/compose/docker-compose.prod.yml -f nexent/windows.override.yaml up -d --no-deps --pull never nexent-web nexent-northbound`；执行时 NEXENT_USER_DIR 与 HOME 使用 F:/Projects/2026ICT/.runtime/nexent-home。退出 0。

## 只预检，尚未切换数据

nexent/windows.paths.env.example 为正确的 Windows 原生路径模板，拟使用 F:/Projects/2026ICT/.runtime/nexent-desktop-data。未创建迁移后的数据目录，未将模板应用到现有数据服务。

只读 Compose 预检命令：

~~~powershell
docker compose --project-name nexent --env-file third_party/nexent/deploy/env/.env --env-file nexent/windows.paths.env.example -f third_party/nexent/deploy/docker/compose/docker-compose.prod.yml -f nexent/windows.override.yaml config --quiet
~~~

命令退出 0。只输出目录/端口的脱敏配置证据：artifacts/windows-compose-preflight.json；没有保存完整 Compose 环境变量或密钥。必须先获准复制当前数据、核验复制结果，再考虑切换。不能直接对空目录执行 up 并假装完成迁移。

## 备份范围

已在 `.runtime/nexent-backups/20260924-112816-ec410ebb` 保存本项目 PostgreSQL 逻辑备份、Skill 文件归档和部署环境文件。pg_dump、docker cp、pg_restore --list 均退出 0；manifest.json 保存命令、退出码和文件 SHA256，不打印密钥。

备份包含敏感本机配置，仅供本机恢复准备，不得上传/公开。它不是全部 Nexent 数据的冷备份，未执行恢复测试，未复制/切换运行中的数据挂载。

## 本轮验证

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| .venv/Scripts/python.exe -m pytest -q tests/test_nexent_verification.py tests/test_nexent_deployment.py | 0 | 21 passed；含 IDM 识别、未知错误拒绝、路径与端口门禁 |
| .venv/Scripts/python.exe scripts/verify_nexent.py | 0 | 2026-09-24 当时真实平台七工具、四种决定、来源校验及 ZIP 导出通过；模型驱动编排当时未验证，后续状态见本页顶部更新 |
| .venv/Scripts/python.exe scripts/validate_local.py | 0 | 下列检查均通过，详情 artifacts/local-validation-report.json |
| .venv/Scripts/python.exe -m pytest -q | 0 | 80 passed；项目测试数量，不是行业准确率 |
| .venv/Scripts/python.exe tests/browser_smoke.py --url http://127.0.0.1:临时端口 | 0 | 独立合成数据库浏览器端到端通过 |
| .venv/Scripts/python.exe tests/mcp_smoke.py --url http://127.0.0.1:临时端口/mcp/ | 0 | SDK 协议验证通过 |
| .venv/Scripts/python.exe scripts/evaluate_assets.py --output artifacts/asset-recognition-report.json | 0 | 已有合成夹具回归通过 |
| .venv/Scripts/python.exe scripts/verify_jev.py | 0 | preflight，无在线请求 |
| .venv/Scripts/python.exe -m pip check | 0 | No broken requirements found |
| node --check src/peiwu/static/app.js | 0 | 语法通过 |
| .venv/Scripts/python.exe scripts/audit_nexent_deployment.py | 1 | 如实拒绝部署就绪：wrong_host_path、service_not_ready、missing_service |

只读部署审计从不重启/迁移/删除资源，也不输出容器环境变量。Windows 桌面引擎的 `/mnt/f/...` 不认作 F 盘；已有命名卷保留，不触发搬动或清理。

## 待确认与后续

- 当前 Nexent 项目数据的复制与挂载切换：已向用户请求明确确认，尚未获准。原数据保持不动。
- Elasticsearch 仍为 red/unhealthy，数据处理服务缺失；因此部署未就绪。
 - 2026-09-25 Nexent 模型列表已有 1 条记录，Agent 绑定 `model_id=1` 且可用；一次合成 Agent/run 已通过。模型 capability profile 未声明 reasoning controls，思考强度选项仍不可用；真实行业资料、独立审核和部署健康待补。
- Word/PPT 仍是合成演示草稿；真实资料、专业审核和最终模板待补，不保证国奖。
