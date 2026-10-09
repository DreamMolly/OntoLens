# 可安全重跑的 Nexent 初始导入

日期：2026-09-24。本项在用户转入 JEV 社区用法调研前完成，未触碰待授权的数据目录切换。

## 已实现

scripts/import_nexent_agent.py 默认只检查当前源码构建包与目标环境。显式 --apply 时，仅在 Agent 不存在且依赖匹配时创建；同名 Agent 的提示词、模型、工具或 Skill 不一致时拒绝覆盖。

- 包必须与当前 nexent/ 源码重建出的字节一致，过期/改动的包不能上传。
- 检查 MCP 地址、目录中的工具和同名冲突，不自动扫描其他服务。
- 核对已有 Skill 的正文/说明及附加工具权限，相符才 use_existing。
- 使用本地文件锁防止脚本并发导入，提交前写 pending 记录；响应超时且结果不明时不盲目重试 POST。
- 不配置模型、不调用模型、不自动重命名、删除或更新已有资源。已手工配置模型的 Agent 不再属于未配置模型的初始模板，脚本会拒绝覆盖。

~~~powershell
.venv/Scripts/python.exe scripts/import_nexent_agent.py
.venv/Scripts/python.exe scripts/import_nexent_agent.py --apply
~~~

当前只在本机官方 speed 用户模式实际验证；受鉴权保护的平台需先落实合法会话，不读取浏览器 Cookie 或猜测凭证。

## 实测结果

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| .venv/Scripts/python.exe -m pytest -q tests/test_nexent_import.py | 0 | 16 passed，包含冲突、附加权限、超时、部分 Skill 成功和并发锁 |
| .venv/Scripts/python.exe scripts/import_nexent_agent.py --apply --output artifacts/nexent-import-replay-first.json | 0 | already_present，agent_id=1，import_posts=0，model_calls=0 |
| .venv/Scripts/python.exe scripts/import_nexent_agent.py --apply --output artifacts/nexent-import-replay-second.json | 0 | 相同 ID，未新增 Agent/Skill，未发创建请求 |
| .venv/Scripts/python.exe scripts/validate_local.py | 0 | pytest 96 passed；浏览器、MCP、资产回归、JEV 预检、pip check 和 JS 语法均退出 0 |

创建/部分失败路径有模拟 HTTP 测试；真实环境验证的是已有资源安全复用。2026-09-26 已完成同机数据迁移、逻辑备份恢复、模型重建和平台复测，但这不是另一台机器上的完整冷启动，仍不能冒充独立复现成功。
