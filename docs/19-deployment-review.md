# OntoLens 部署检查与恢复

业务启动见[部署指南](38-operational-deployment.md)，已准备本机 Nexent 的恢复入口见[日常启动](30-demo-startup.md)。当前部署证据以 `artifacts/nexent-deployment-audit.json` 和业务容器收据为准。

## 只读检查

从仓库根目录运行：

```powershell
.venv/Scripts/python.exe scripts/audit_nexent_deployment.py
```

检查容器是否属于本项目、持久化挂载是否对应预期目录、端口是否仅暴露到本机、数据库与数据处理服务是否就绪。`running` 或 Docker CLI 可以执行不足以证明服务可用，Docker 不可达时必须报告失败。

Nexent Windows 覆盖配置位于 `nexent/windows.override.yaml`，本机路径示例在 `nexent/windows.paths.env.example`。当前机器必须核对实际解析后的 Compose 配置，不能对错误或空挂载直接启动并宣称成功。

## 恢复与备份

停止业务服务后备份关联的工作库、会话库和账户文件。SQLite 使用备份 API 或一致冷备份，保留来源原字节与审计。Nexent 还需要 PostgreSQL、Skill 文件、对象存储及部署配置；备份含本机敏感配置，排除公开仓库。

恢复先确认目标目录和备份可读，再核验账户、来源、快照、模型绑定、MCP 健康与实际请求。复用账户、模型和持久化卷，避免无理由创建重复实例。源备份在新环境完整验证前保留。

## 未完成范围

本机恢复、一次容器重启、只读挂载检查与跨机器独立冷启动是不同验收。长期负载、备份实际恢复、真实资料效果和专业适用仍需独立证据。导出完整性检查只能证明内部一致性，不认证文件来源。
