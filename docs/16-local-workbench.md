# OntoLens 工作台

工作台由 FastAPI、SQLite 与本地静态前端组成。业务入口默认空库，合成演练显式选择独立数据库；启动见[业务部署](38-operational-deployment.md)，设计见[规范索引](../design.md)。

## 能力

来源支持文本、Markdown、JSON、CSV、YAML 和带文本 PDF，图片保留预览与人工摘录。上传资料不自动成为业务事实，未配置自动 OCR。

六类台账保存原始与规范化来源，候选检查通过后由管理员确认发布。核验从快照加载授权、库存、已领类别和规则，返回四种决定或缺件状态。人工复核追加跟进，不改原决定。

版本发布与回滚需要 `expected_active`；历史申请始终绑定原快照。导出带原始字节、来源定位与规则，可以脱库重新计算。SQLite 审计通过 API 追加，不能证明数据库管理员无法篡改。

## 来源与模型

每份来源记录 `external_model_allowed`，默认本地处理，私有资料不能开启外发。在线 JEV 需要显式许可和获准来源；支持概率只影响复核提示。解释接口支持 `chat_completions`、`responses`、`messages`，由 `ONTOLENS_MODEL_PROTOCOL` 选择，不能改决定。

## 启动与验证

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[workbench,jev,test]"
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-operational.ps1 -Bootstrap
```

已准备的 Nexent 本机环境使用 `start-demo.ps1`，令牌保存在 `.runtime/ontolens-mcp-token.txt`。工作台单独启动使用 `start-workbench.ps1`；非回环绑定必须有 MCP 令牌与明确可信主机。

完整验证运行 `scripts/validate_local.py`，使用隔离数据库。验证覆盖来源完整性、四决定、缺件、发布/回滚、并发、HTTP/MCP 与真实浏览器操作。软件回归、平台编排、独立冷启动和行业效果分别记录。
