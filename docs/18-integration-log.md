# 本机 Nexent 联调记录

核验日期：2026-09-24。仅合成演示，队员/导师资料待补，专业审核人为空。未调用付费模型、未提交材料或发布仓库。

## 本轮实际完成

- 源码目录 third_party/nexent 是导出包，不是 Git 工作树；.pinned-commit 记录 9317cd39ae1ea9cd6ad82047fd1e1ef7a7d87ac1，VERSION 为 v2.6.0。实际容器镜像 ID 与挂载信息另存于 artifacts/nexent-integration-report.json，不推定镜像与源码逐字一致。
- 修正 agent_info 的字符串 ID 索引和 Skill 子 ZIP 格式。旧版包备份于 .runtime/package-backups；打包结果 SHA256：9db87c630c2068b7ff0f85c7d93b5df47261a9d4a7945d759c7b8600695befb0。复现：nexent/package.ps1。
- 运行中配置容器的官方 AgentImportRequest 校验通过。首次导入 HTTP 500（工具尚未进入目录），三个 Skill 已创建；执行工具扫描后复用已有 Skill，导入 HTTP 200，Agent ID 1。没有重复注册 MCP/重复创建 Agent。
- 修复 .env 空值覆盖进程令牌；工作台非回环绑定无令牌时拒绝启动。Nexent Authorization 改为完整 Bearer 值。无凭证 MCP 请求 HTTP 401。令牌值不写入日志。
- JEV 默认入口即使有密钥也返回 live_not_authorized；私有来源及非布尔授权均拒绝外发。只有显式 --live 才可能请求，未配置时仍 unavailable。

## 可复现证据

| 命令 | 退出码 | 实测结果与边界 |
| --- | --- | --- |
| .venv/Scripts/python.exe -m pytest -q tests/test_nexent_package.py | 0 | 8 passed；格式、子包、稳定字节、旧文件保留与错误依赖 |
| nexent/package.ps1 | 0 | 生成可导入 ZIP，不删除旧文件 |
| .venv/Scripts/python.exe scripts/verify_nexent.py | 0 | 平台 API 七工具、四种决定、needs_review、逐条 quote/locator/SHA256、同输入决定一致；模型编排未验证 |
| .venv/Scripts/python.exe scripts/validate_local.py | 0 | 内含下列七项真实检查；独立数据库、临时目录和浏览器目录均位于 F 盘 |
| .venv/Scripts/python.exe -m pytest -q | 0 | 66 passed；项目回归，不是行业准确率 |
| .venv/Scripts/python.exe tests/browser_smoke.py --url http://127.0.0.1:临时端口 | 0 | 桌面、移动端、四种决定、来源、上传、候选发布/回滚通过 |
| .venv/Scripts/python.exe tests/mcp_smoke.py --url http://127.0.0.1:临时端口/mcp/ | 0 | SDK 协议测试通过；与真实 Nexent 平台报告分开 |
| .venv/Scripts/python.exe scripts/evaluate_assets.py --output artifacts/asset-recognition-report.json | 0 | 仅已有合成资产夹具的基线回归 |
| .venv/Scripts/python.exe scripts/verify_jev.py | 0 | preflight，live_request_sent=false |
| .venv/Scripts/python.exe -m pip check | 0 | No broken requirements found |
| node --check src/peiwu/static/app.js | 0 | JavaScript 语法通过 |

真实端口、完整命令和逐项日志路径见 artifacts/local-validation-report.json。独立测试不会清空常用工作台。

## 提交草稿同步

Word/PPT 已同步 Agent 名称、平台工具通过/模型未配的边界、JEV 显式外发开关和复现命令；旧二进制保留在 .runtime/material-backups。材料检查发现旧 Word 存在重复样式、缺失底纹属性/默认样式、编号枚举错误，旧 PPT 存在 notesMasterIdLst 顺序错误和图片拉伸；本轮修正这些问题，没有重建整份文档。

- officecli validate submission/peiwu-development-design-draft.docx：初次退出 1，修复后退出 0，no errors found。
- officecli validate submission/peiwu-presentation-draft.pptx：初次退出 1，修复后退出 0，no errors found。
- officecli view submission/peiwu-presentation-draft.pptx issues：修复图片比例后报告 0 issues。
- PPT 逐页截图复核：标题/正文/命令无重叠、截断；截图页改为保持比例的局部放大并注明边界。产物为 artifacts/slides-review-*.png 与 artifacts/nexent-integration-slide.png。最终命令 officecli validate submission/peiwu-presentation-draft.pptx 退出 0。
- Word/PPT 的 HTML 预览在 artifacts/peiwu-design-preview.html 与 artifacts/peiwu-slides-preview.html；Word 原模板的空段/缩进和最终分页仍需版式确认。不能把 schema 校验通过写成最终视觉审核通过。

## 上一阶段遗留项

以下为上一阶段的记录；本轮新增诊断与复测结果见 `19-deployment-review.md`。

1. Elasticsearch unhealthy/red：只读 allocation/explain 显示 disk_threshold 拒绝分配分片。容器 df 显示 /dev/sde 128 MB、可用约 2 MB；Windows F 盘同时仍有大量剩余空间。Docker Desktop 把 /mnt/f/... 当作内部 Linux 路径，不能据目录名字认定它就是 F 盘。此前“残留锁文件是根因”的说法不成立。下一项须保留现有数据和配置，修正 Windows 挂载；不移动 Docker Desktop 全局数据目录、不清理镜像/卷。
2. Web /api/agent/export 返回 204 空响应，但配置容器内同一路由返回 200 application/zip。验证脚本记录了实际后备读取方式，不能说网页下载已通过。
3. nexent-data-process 镜像尚未完成拉取，服务未运行；不把核心服务启动冒充全部组件验收。
4. 2026-09-25 已在 Nexent 创建并健康检查模型记录，绑定 `model_id=1` 到 Agent；真实 Agent/run 使用 `reasoning_effort=auto` 调用 evidence_lookup、graph_query、decision_check，返回合成 `ALLOW`。运行摘要见 `artifacts/nexent-agent-run-20260924.json`。这只验证合成链路，不代表行业效果、独立审核或部署健康。
5. 真实资料、专业审核、官方最终模板和队员录屏仍待补。完整目标未完成。
