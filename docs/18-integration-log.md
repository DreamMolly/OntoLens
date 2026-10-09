# OntoLens 集成验证方法

平台与软件的验证范围必须明确。完整软件收据见 `artifacts/local-validation-report.json`，Nexent 平台收据见 `artifacts/nexent-integration-report.json`；数字、时间与源码指纹以各自报告为准。

## 检查层次

| 检查 | 入口 | 证明的范围 |
| --- | --- | --- |
| 软件与浏览器 | `scripts/validate_local.py` | 隔离夹具中的契约、完整性、交互及依赖 |
| Nexent 工具与绑定 | `scripts/verify_nexent.py` | 本次平台健康、七工具、Skill、来源和导出 |
| 模型运行 | `scripts/probe_nexent_live.py` | 本次真实请求、模型/Agent、工具轨迹与结果 |
| 部署状态 | `scripts/audit_nexent_deployment.py` | 当前容器、挂载、端口与服务健康 |
| 交付一致性 | `scripts/audit_deliverables.py` | 软件、原生材料、模板和证据矩阵相互对应 |

## 执行条件

工具与模型调用用明确合成或获准资料，不向外部模型发送私有台账。业务决定必须由 `decision_check` 返回，缺件/工具错误不能被解释成放行。模型绑定或健康检查不等于完成真实编排。

验证在独立数据库执行，保留实际命令、退出码、日志和源输入指纹。失败报告记录本次失败，不用过去的成功状态覆盖。跨机器部署应生成自己的新收据；单机即时健康不证明持续稳定或行业效果。
