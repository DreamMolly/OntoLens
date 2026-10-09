# 本地工作台建设约定

2026-09-23 用户明确要求队员、指导老师、审核人留空，并立即完成软件。该要求取代此前把人员/试点资料作为开发阻断的安排。报名、专业验证和真实部署仍单独验收，人员资料缺失不阻止本地软件建设。

## 本次交付

在原 Python 判定器外新增 FastAPI + SQLite 本地工作台与静态网页，不增加 peiwu CLI 子命令。使用 uvicorn 启动网页，标准 MCP 通过同服务的 HTTP 端点提供工具。原 v1/v2/v3 与 H 集保持冻结。

- 源文件导入：文本、Markdown、JSON、CSV、带文本的 PDF；图片可保存预览和人工摘录，明确未配置自动 OCR。来源文本均按数据处理，不自动成为有效业务事实。
- 外发权限：每份来源记录 external_model_allowed，默认仅本地处理；私有资料不能开启。JEV 只接收当前版本中已经明确允许外发的文本片段。
- 合成演示空间：从原教学目录构造带文件哈希、行号/JSON 路径的来源快照。初始授权、库存与领用事件明确标“合成”。没有任何专家审核人。
- 决定链路：使用版本快照内的授权、库存、已领类别和原规则判定，保留查询路径、证据和决定；缺失、过期或冲突的证据停在 needs_review。
- 变更流程：用户明确选择授权字段、来源与有效日期，创建候选；对已记录申请做前后比较，运行冻结回归检查，再在合成空间发布或回滚。发布不算专业审核，不改变原规则文件。
- 审计：SQLite 保存不可通过 API 编辑的运行、候选、版本和事件，可导出复现包。它不是抵御本机数据库管理员篡改的系统。
- MCP：只暴露证据检索、图路径、判定、候选检查和候选提取等工具；不向模型提供发布/回滚或任意路径读写。
- 候选提取：从明确的人物 ID、类别别名和授权句式提出 proposed 候选，保留 quote、locator、替换/追加语义和方法标记；只提取原文明确出现的类别，不把快照中的旧授权重复当作新事实。这是确定性低资源基线，不是自动批准或完整本体生成。
- JEV 可选层：使用 TypeSafe 的 Noul 对证据候选与查询的支持关系评分，代码按概率重排并标记复核优先级；JEV 不生成四种决定，未配置 API 时明确返回 unavailable。
- 引用复核：决定下可输入待复核的事实性陈述，逐项核对该历史快照的来源、原文件 SHA256、定位和完整引文。字面匹配结果独立显示，不证明陈述正确；支持/矛盾概率目前只通过模拟测试，未做在线语义验证。错误引用不请求模型，不改历史决定，不新增 MCP 工具。
- 模型：默认离线确定性检索；可通过环境变量接入模型做带引用解释，`PEIWU_MODEL_PROTOCOL` 支持 `chat_completions`、OpenAI `responses` 和 Anthropic 风格 `messages`。它们只生成解释，不能改写程序决定；无配置时准确报告未连接，不伪造推理或成绩。协议契约与边界见 `docs/23-model-protocols.md`。

## 启动

现有 Nexent 本机环境优先运行 `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-demo.ps1`，一次恢复工作台与平台；`-CheckOnly` 只预检。它读取已保存的 `.runtime/peiwu-mcp-token.txt`，拒绝错挂目录和被其他程序占用的工作台端口。以下命令保留为仅运行工作台或首次准备依赖的方式，详见 [日常启动](30-demo-startup.md)。

~~~powershell
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -e ".[workbench,test]"
.\\start-workbench.ps1
~~~

推荐直接运行 .\\setup-local.ps1。它把虚拟环境、pip 缓存、临时目录和 SQLite 运行文件放在项目的 F 盘 .venv/ 与 .runtime/；不会把项目依赖安装到 C 盘。Python 本体和 Docker Desktop 仍由系统安装位置管理，本项目不搬动它们。

默认监听 127.0.0.1:8765，可用 .\\start-workbench.ps1 -Port 8766 改端口。工作台禁止非本机 API 访问；MCP 在本机不要求令牌。若把 MCP 通过容器或代理暴露给其他进程，设置 PEIWU_MCP_TOKEN，使用 Authorization: Bearer ...，并保留可信主机配置。

当 Nexent 运行在 Docker 容器中时，使用 -BindHost 0.0.0.0 让容器通过 host.docker.internal 访问工作台，并同时设置 PEIWU_MCP_TOKEN；令牌只保存在本机运行环境，不写入仓库。

2026-09-24：Docker Desktop 已启动，Nexent 已实际注册并调用工作台工具；稳定部署仍有待修项，见 `18-integration-log.md`。JEV SDK 已安装，并已用一条合成相关性查询验证在线请求；这不是准确率或行业效果。网页/MCP 即使有密钥也不会发起 JEV 请求，只有显式执行 scripts/verify_jev.py --live 才允许请求。

启动脚本保留已设置的进程环境变量，不让 .env 的空值覆盖 MCP 令牌；非回环绑定缺少令牌时直接拒绝启动。MCP 冒烟客户端也支持 PEIWU_MCP_TOKEN。推荐运行 `.venv/Scripts/python.exe scripts/validate_local.py`，在独立 F 盘数据库执行浏览器测试，不修改或清空日常演示历史。

JEV 当前只接收文本状态：PDF 文本、CSV/JSON 字段和图片的人工摘录先由本地来源层提供，JEV 不读取图片二进制，也不构成 OCR 或多模态模型效果。上传图片没有摘录时，系统保留来源但不生成资产事实。data/demo/synthetic-asset-label.png 是本地模板生成的合成图像，配套摘录文件明确标为人工摘录。

2026-09-24 修复来源外发权限：只有内置合成种子显式授权，上传的合成资料仍默认仅本地处理，重启不自动开启。对旧逻辑误授权的来源，依据原导入审计恢复并记录 source_permission_restored；重启前的 SQLite 备份和验证命令见 `22-citation-review.md`。

## 页面设计

单一任务是让库管/演示者看懂一条申请的依据和变更影响。采用淡蓝灰底 #EDF3F6、白纸 #FFFFFF、海军蓝 #17384B、深青 #087F8C、警示橙 #B66320、错误红 #AA3845。中文标题用本机微软雅黑/苹方的中等字重，正文用系统无衬线，编号和 JSON 用等宽字体。桌面左右两栏为申请表与证据链，移动端顺序堆叠；视觉重点是一条可点开来源的证据路径，不用无数据的统计大屏。

## 验收

测试导入与引用、ALLOW/DENY/LIMIT/ISOLATE、未知或不可信资料停判、版本发布/回滚、旧记录不随新版本改变、并发候选防覆盖、MCP 协议与浏览器真实操作。平台工具调用与完整模型编排分别验收；最新本机部署状态见 `19-deployment-review.md`。真实数据、领域金标准和本体算法对照仍未完成，不能用本地演示冒充。

交付前可运行 `.venv/Scripts/python.exe scripts/audit_deliverables.py`，检查最近一次七项验证、Word/PPT 中的复现数字、Agent ZIP 与证据矩阵是否一致；审计通过不等于模型编排或行业验证完成。
