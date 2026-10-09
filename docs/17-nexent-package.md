# OntoLens Nexent 配置包

模板位于 `nexent/`，固定上游版本见 `nexent/upstream.json`。核心工作台可独立运行；Nexent 接入需要实际平台、模型配置与 MCP 联通。

## 内容

- `agent.json`：`ontolens_compliance_review`、七工具和三项 Skill；模型 ID 不固化。
- `mcp-service.local.json` / `mcp-service-docker.json`：同机或 Docker 地址与凭证占位。
- `skills/ontolens-intake/SKILL.md`：申请与可信事实边界。
- `skills/ontolens-evidence/SKILL.md`：来源、定位与关系路径。
- `skills/ontolens-decision/SKILL.md`：程序决定及候选预览。
- `package.ps1` / `scripts/build_nexent_package.py`：生成 `artifacts/ontolens-nexent-agent.zip`，内含 Agent JSON 与 `skills/<name>.zip`。

## 准备与导入

1. 启动独立工作台；同机 MCP 为 `http://127.0.0.1:8765/mcp/`。Docker 平台使用 `host.docker.internal`，工作台非回环绑定须有 `ONTOLENS_MCP_TOKEN`。
2. 添加 `ontolens-local` MCP 服务，使用完整 `Authorization: Bearer <令牌>`；模板占位符不能用于实际调用。
3. 扫描平台工具目录，确认七工具可用；只刷新 MCP 计数不足以导入 Agent。
4. 构建并导入 ZIP，三项 Skill 一起绑定。`scripts/import_nexent_agent.py` 默认检查，显式 `--apply` 才写入；同名内容冲突拒绝覆盖，不重复创建。
5. 在模型管理页填写真实 provider、模型与端点，健康检查后绑定返回的 model_id，见[模型配置](29-nexent-model-inputs.md)。
6. 用明确合成申请实际运行，先查来源与关系，再调用 `decision_check`；保留模型、工具轨迹和结果。

```powershell
.venv/Scripts/python.exe scripts/build_nexent_package.py
.venv/Scripts/python.exe scripts/import_nexent_agent.py
.venv/Scripts/python.exe scripts/verify_nexent.py
```

已经准备好的本机环境用 `start-demo.ps1` / `-CheckOnly` 恢复或预检，方法见[日常启动](30-demo-startup.md)。新环境须独立验证，不能使用其他机器的 ready 状态。

## 可选 JEV

JEV 只用于获准文本的相关性、引用支撑、变更影响和关系候选复核，不参加四种决定计算。`TYPESAFE_API_KEY`、`TYPESAFE_MODEL` 和端点只放本机配置。在线调用要求显式许可，私有或未获准来源不发送；模型概率不认证事实。

```powershell
.venv/Scripts/python.exe scripts/verify_jev.py
.venv/Scripts/python.exe scripts/verify_jev.py --task citation_review
.venv/Scripts/python.exe scripts/verify_jev.py --live
```

默认预检不发请求；真实调用、录制回放和离线测试分别标明。引用不完整不请求模型，解释不改决定。独立语义评测与阈值校准见[评测协议](13-evaluation-protocol.md)。

## 验收

Nexent 平台证据包含版本、MCP 服务、Skill、模型、申请、快照、决定、引用与失败场景。工具验证、Agent 模型编排和无工具解释各报实际结果；软件数字、容器部署、真实行业效果和专业审核也分别验收。
