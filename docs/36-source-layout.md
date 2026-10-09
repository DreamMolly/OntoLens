# OntoLens 源码布局

主实现位于 `src/ontolens/`。发布范围按 `scripts/source-release-policy.json` 筛选，离线检查入口为 `scripts/check_source_release.py`。

| 路径 | 用途 |
| --- | --- |
| `src/ontolens/` | 核验、来源、版本、权限、HTTP/MCP 与前端 |
| `data/` | 冻结规则、合成夹具、公开摘录与来源清单 |
| `tests/` | 契约、完整性、权限与浏览器回归 |
| `scripts/` | 启动、验证、部署、打包与交付工具 |
| `skills/ontolens/` / `nexent/` | CLI Skill、平台 Agent/MCP/Skill 模板与固定上游版本 |
| `design/` | 分篇设计合同、唯一基础 token 与资产出处 |
| `docs/` | 架构、资料协议、评测、部署与规划 |
| `submission/` | 当前 Word/PPT、可编辑 SVG/notes、演示与证据矩阵 |
| `artifacts/` | 白名单中的验证收据和报告直接引用的日志 |
| `deploy/` / `Dockerfile` | 容器、持久化与可选 Nexent 网络 |

`.venv/`、`.runtime/`、缓存、本机数据库、账户、密钥、私有台账和导出不进入 Git。上游完整检出在 `third_party/nexent/`，不嵌入源码；获取方式见 `nexent/upstream.json`。

## 交付检查

从仓库根目录运行；Linux/macOS 将 Python 路径换为 `.venv/bin/python`：

```powershell
.venv/Scripts/python.exe scripts/validate_local.py
.venv/Scripts/python.exe scripts/check_source_release.py --snapshot-validation
.venv/Scripts/python.exe scripts/audit_deliverables.py
.venv/Scripts/python.exe scripts/check_source_release.py --paths
.venv/Scripts/python.exe scripts/check_source_release.py --check-staged
```

先完成实现与材料，再验证。日志快照逐字节核对 SHA256，输入指纹、命令和退出码保持可查；交付审计核对材料数字、Agent ZIP和平台证据。压缩包需明确白名单，真实凭据、路径越界、符号链接和暂存区额外文件拒绝。

`.gitattributes` 保留精确文本字节，避免克隆时 CRLF/LF 转换影响指纹。跨机器运行须生成自己的收据，不能把仓库内记录当作新部署已就绪。

## 运行边界

业务入口默认空库，账户与六表资料由本机建立。开发验证使用独立合成夹具。核心资源按项目根目录定位，无需固定盘符；Windows Nexent 路径示例按当前机器调整。

仓库[fulao/OntoLens](https://git.fulao.cc/fulao/OntoLens)公开供查阅与评审，许可证状态以根 README 为准。真实行业效果、专业审核、独立新机、长期运行和正式参赛提交分别验收。
