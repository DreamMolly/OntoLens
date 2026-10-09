# OntoLens Nexent 初始导入

`scripts/import_nexent_agent.py` 默认检查当前构建包和平台；显式 `--apply` 才在 Agent 不存在且依赖相符时创建。已准备实例日常使用启动入口，不重复导入。

## 检查合同

- Agent ZIP 必须与当前 `nexent/` 的模板和 Skill 字节相符。
- MCP 地址、服务、工具目录和三项 Skill 内容/权限逐项核对，同名冲突拒绝覆盖。
- 文件锁防止并行导入，提交前保留本机 pending 状态；超时未知结果不盲目重发创建请求。
- 初始模板不配置模型或调用模型；已有自定义绑定的 Agent 不视作空模板。
- 工具扫描与模型绑定分别由平台操作和对应检查完成。

```powershell
.venv/Scripts/python.exe scripts/build_nexent_package.py
.venv/Scripts/python.exe scripts/import_nexent_agent.py
.venv/Scripts/python.exe scripts/import_nexent_agent.py --apply
.venv/Scripts/python.exe -m pytest -q tests/test_nexent_import.py
```

创建、冲突、附加权限、部分失败和并发分支由隔离测试验证。实际平台响应只证明该次实例行为，不替代独立新机安装或模型编排；当前平台结果见 `artifacts/nexent-integration-report.json`。
