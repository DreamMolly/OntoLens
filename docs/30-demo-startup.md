# OntoLens 本机 Nexent 启动

本入口用于已经准备好的本机 Nexent 环境。首次安装、恢复备份与模型配置按[配置包](17-nexent-package.md)和[部署检查](19-deployment-review.md)完成；同机恢复不等于独立新机验收。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1 -CheckOnly
```

Python 核心入口 `scripts/start_demo.py` 默认只预检，显式 `--apply` 启动。已通过检查的服务复用，报告保存实际时间与本次状态。

## 检查范围

- `.runtime/ontolens-mcp-token.txt`、工作库与 PostgreSQL `PG_VERSION` 确认实例已准备，缺失不初始化假空库。
- `.runtime/nexent-desktop-data`、`.runtime/nexent-home` 与解析后的 Compose 持久化挂载逐项匹配。
- 工作台端口属于本项目；其他进程占用时拒绝。MCP 还须从容器侧使用令牌核验。
- 模型与 Agent、MCP、Skill 绑定符合当前记录；不创建重复模型或实例，不删除持久化卷。
- PostgreSQL 就绪后才启动数据处理服务；`/tasks` 探针只证明 API 和任务查询可用，不代表 OCR 或实际文件效果。

`running` 不够证明服务可用。Docker 不可达、挂载漂移、配置不足或工具健康失败时保留本次错误；不以旧 ready 状态代替当前探测。恢复后运行 `scripts/audit_nexent_deployment.py` 和 `scripts/verify_nexent.py` 取得当前证据。

长期稳定性、跨机器安装、备份实际恢复、真实资料效果和专业审核另有验收条件。
