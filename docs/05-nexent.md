# Nexent 调用边界

Nexent 是平台，OntoLens 是其业务核验与证据工作台。接入模板见 `nexent/`，安装与导入方法见[配置包](17-nexent-package.md)。

## 调用原则

1. 接收申请后先获取来源与版本关系，调用 `decision_check`。
2. 原样展示程序的决定、批准数量、原因、版本与证据。
3. 资料缺失或工具失败时保留 `needs_review` / `tool_error`，不猜测放行。
4. 解释与程序结果冲突时以 JSON 为准，并复核来源。
5. 候选只由 `candidate_review` 预览，发布和回滚由授权管理员操作。
6. 不读取留出案例来调整规则，不以模型自评代替独立标签。

## 可复用入口

`skills/ontolens/SKILL.md` 规定 CLI 调用方式。Nexent 的三项 Skill 在 `nexent/skills/`，Agent ZIP由 `scripts/build_nexent_package.py` 构建。模板本身不证明已经联通。

核心 CLI 可独立运行：

```powershell
.venv/Scripts/python.exe -m ontolens decide --rules data/rules/v2.yaml --request <申请JSON文件>
```

实际申请 JSON 路径由操作者填写。相同快照与申请的确定性决定应一致；模型解释不要求逐字一致，但必须有来源且不能改判。

## 验收

在已准备环境中运行 `scripts/verify_nexent.py`，核对服务健康、七工具、Skill 绑定、来源与导出。模型绑定与真实 Agent 运行另有收据，不把工具测试冒充模型编排。演练资料、专业适用与真实行业结果分别标明。
