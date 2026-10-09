# 源码布局与交接发布边界

本项目保持现有模块位置。核心、测试和证据引用依赖这些目录，整理通过明确纳入范围实现；历史交付物和运行数据保留在本机。源码发布策略见 `scripts/source-release-policy.json`，离线检查入口为 `scripts/check_source_release.py`。

唯一搬迁的是根目录内无源码引用的 GitHub API 临时响应 `github-result-ce909d70.json`，已保存到 `.runtime/archive/`，搬迁前后 SHA256 一致。未搬迁测试夹具、交付证据或历史备份。

| 目录或文件 | 队友用途 | Git 纳入范围 |
| --- | --- | --- |
| `src/peiwu/` | 决策、证据、Web/MCP 与静态前端实现 | Python 与前端源码 |
| `data/` | 规则、合成案例、评估集、公开文件摘录与清单 | 当前数据文件；公开摘录及合成台账的性质见 `docs/35-public-data-pack.md` |
| `tests/` | 契约、回归、完整性与边界测试 | 测试源码及固定测试夹具 |
| `scripts/` | 验证、部署、打包与源码发布工具 | 源码与发布策略；运行输出不纳入 |
| `skills/`、`nexent/` | Skill、Agent/MCP 模板、上游版本描述 | 配置模板、Skill 与固定版本引导信息 |
| `docs/` | 设计说明和历史记录 | Markdown；本机官方 Office 原模板和历史备份不纳入 |
| `submission/` | 当前开发文档、答辩 PPT、证据矩阵、演示流程 | 明确列出的当前草稿，PPT 的 SVG、备注、设计规范与必要图片 |
| `artifacts/` | 支持当前证据矩阵和交付审计的记录 | 逐文件白名单；验证日志仅纳入报告直接引用的副本 |
| `.env.example`、启动脚本、根Dockerfile及deploy/ | v0.4.0业务启动、容器与可选Nexent网络 | 模板/定义/源码；实际账户、env和volume留本机；最终以发布白名单检查为准 |
| `.venv/`、`.runtime/`、`tmp/` | 本机环境、数据库、缓存、备份和临时文件 | 不纳入 |
| `third_party/nexent/` | 独立上游检出 | 不纳入；按 `nexent/upstream.json` 与 `scripts/bootstrap_nexent.py` 引导获取 |

`submission/ppt-master/` 内的 `backup`、`analysis`、`exports`、`live_preview`、`validation`、重复 `sources` 及中间 `submission` 属于本机制作过程。最终 DOCX/PPTX 保存在 `submission/` 顶层，队友能继续编辑的 SVG、备注和设计规范保留在白名单内。旧版本的 `.pre-*`、`.backup*` 均不删除，但不发布。

## 发布前操作

使用 Python 3.11 或更新版本。Windows 示例采用项目环境 Python；Linux 将 `.venv/Scripts/python.exe` 替换为 `.venv/bin/python`，所有命令从仓库根目录执行。

```powershell
.venv/Scripts/python.exe scripts/validate_local.py
.venv/Scripts/python.exe scripts/check_source_release.py --snapshot-validation
.venv/Scripts/python.exe scripts/audit_deliverables.py
.venv/Scripts/python.exe scripts/check_source_release.py
.venv/Scripts/python.exe scripts/check_source_release.py --paths
# 按以上输出的路径暂存，不使用 git add -f 绕过忽略规则。
.venv/Scripts/python.exe scripts/check_source_release.py --check-staged
```

先完成源码与材料修改，再执行完整验证。`--snapshot-validation` 将本轮七阶段日志逐字节复制到 `artifacts/source-validation/<run>/`，先验证全部原日志 SHA256，再只更新验证报告中的 `run_dir` 和每项 `log` 路径；原报告备份保存在 `.runtime/source-release-backups/`。命令、退出码、日志哈希与输入指纹保持不变。相同快照可重复执行，已有不同内容会拒绝覆盖。之后交付审计即可引用 Git 中的日志，无需发布本机数据库或运行目录。

默认检查只生成 `.runtime/source-release-manifest.json`，记录相对路径、字节数和 SHA256。它拒绝路径越界、符号链接或目录联接、敏感文件名、非白名单压缩包以及常见真实凭据格式；Nexent Agent ZIP 还必须与 Agent/Skill 源模板一致。`--check-staged` 检查暂存区是否含有白名单外路径。检查不会连接网络、读取真实 `.env`，也不会输出文件内容或凭据。离线筛查不能证明所有秘密均已排除，发布者仍须审阅暂存差异。

`.gitattributes` 使用 `* -text` 保留 Git 中的精确文本字节。交付验证会哈希源码，自动 CRLF/LF 转换可能让另一台电脑的历史输入指纹失配；因此跨平台克隆保持原字节，新一轮编辑后重新验证。

## 克隆后的可移植性与证据边界

核心 Python 通过项目根目录定位资源，无需固定 `F:` 盘。PowerShell 包装脚本服务 Windows，Linux按README的Python安装与run_operational入口启动。Nexent 的 Windows 路径示例代表原开发机，部署前替换为当前机器实际路径；容器数据、登录信息、数据库和原部署 `.env` 都需要本机建立。

当前白名单里的验证、平台、模型、迁移与启动报告记录的是对应时间和机器的状态。它们保留合成数据、历史 Agent 运行、公开来源以及未验证项的边界，不能作为队友的新部署已就绪、真实行业效果或独立冷启动已通过的证明。克隆后应运行自己的验证并产出新的报告，避免把旧时间戳当作当前状态。旧文档中不在白名单内的本机调试截图和归档报告不随源码交付。

未新增或推断项目许可证。上游 Nexent 的许可证、固定提交及获取方式按上游仓库处理，不把嵌套 `.git`、第三方完整 vendor 树或本机私有配置嵌入本项目。

## v0.4.0发布门槛与运行状态排除

v0.4.0/D1.1软件默认业务空库、带账户、六表候选检查发布，不能再把全部能力写作local demo。2026-10-09 可实用业务流程、`gpt-6-sol` 配置绑定与Agent2无工具解释、456 passed七阶段和隔离业务容器30项收据均通过；7 MCP与Agent1工具编排属于10-08历史运行。源码已推送到私有 Gitea `fulao/OntoLens`；首个源码发布提交为 `92f2c2c8c17647082227e9209efc2a7f0cf14d04`，当前 `main` 见仓库链接。Linux新机冷启动、长期稳定性、真实行业效果和正式参赛提交仍单独待验。

`.runtime/operational/accounts.json`、initial-admin.txt、access.sqlite3/workbench.sqlite3、所有私有原始/规范化台账、登录cookie/token、真实.env、Dockervolume与私有导出 MUST排除。账户文件仅哈希也不发布；密码不可写入镜像/README/命令行参数。源码里的schema/模板及明确合成测试资料可按白名单纳入。

默认create_app新库operational；Workspace库类seed默认是旧脚本兼容，不意味着业务入口自动演示。所有写入验证显式synthetic隔离，不能用真实业务库更新软件验收收据。Dockerbuild、健康、业务流程、当前平台与真实研究效果是不同证据层。

真实行业评测/独立领域审核/长期运行/正式比赛提交仍待完成，不由源码可部署或一次平台成功证明；也不把未完成研究误绑定为软件发布的全部前置条件。
