# 合成反事实与变形评测

本评测检查单个事实变化是否满足事先声明的结果与变化/不变关系。夹具位于
`data/evaluation/counterfactuals.yaml`，独立于冻结的 `data/cases` gold；没有为提高分数修改
regression、incidents 或 heldout。预期由开发者编写，不能视为独立专家标签。

当前 21 个案例覆盖：

- 单位错误进入 `needs_review/UNIT_MISMATCH`；人员、批次或柜位未知进入
  `needs_review/MISSING_REFERENCE`，均不生成业务决定。
- 库存降至 20 时 `LIMIT/STOCK_SHORT`，降至 0 时 `DENY/OUT_OF_STOCK`。
- 柜位不兼容与当天未归还不兼容类别分别触发 `CABINET_INCOMPATIBLE`、`SESSION_INCOMPATIBLE`。
- 数量恰为学生单次上限 250 与超过单次上限 1 单位（251）的变化，触发 `ISSUE_CAP`。
- 内部 checker 对数量 0 返回 `DENY/INVALID_QUANTITY`。
- 授权有效期开始和结束日期各自的前一天、当天、后一天，共 6 例；起止当天均有效，
  窗口外分别进入 `AUTHORIZATION_NOT_ACTIVE` 或 `AUTHORIZATION_EXPIRED`。
- 仅将批次状态从 available 改为 expired 或 damaged，均触发 `ISOLATE/LOT_NOT_ISSUABLE`。
- 改请求编号、改无关批次库存、提高已经足够的本批次库存，决定保持不变。

## 评测层与合成基线

所有案例调用内部 `Workspace._calculate` 和确定性 checker，未通过 HTTP 路由，
`evaluation_layer` 标为 `internal_calculation`。HTTP 的 `CheckRequest` 要求 quantity > 0，
会在计算之前拒绝 0；内部 `INVALID_QUANTITY` 不是 API 响应证据。针对性测试验证请求模型
确实拒绝 0，但本评测不声称覆盖 HTTP 状态码、网络传输或端到端交互。

演示快照初始 `validity` 为空。日期案例通过显式 `setup` 声明 stu01 的合成授权窗口
2026-09-25 至 2026-09-30，以及用途说明 `reason`。setup 只允许为已有人员设置唯一的
`validity.<person>`，必须提供合法且顺序正确的 from/until 字符串日期。它先对基线生效，
然后复制成变形状态；比较时只改变一次 `request.as_of`。这不是导入或验证真实授权材料。
普通变形仍要求路径和叶子已经存在，不允许静默增加事实。

记录中的 `setup`、`observed_setup_paths` 可追溯基线构造；`input_hash` 包含案例声明、
构造后的完整基线状态与变形状态。setup 用途说明改变也会改变输入哈希。
`expected_relation` 默认为 `changed`；`invariant` 要求完整结果保持一致。

## 执行与结果解释

需要刷新正式评测产物时运行：

```powershell
.venv/Scripts/python.exe scripts/generate_counterfactual_evaluation_report.py
```

该入口输出 `artifacts/synthetic-counterfactual-report.json`；主评测收据生成入口也会嵌入
同一份 `counterfactual` 节。修改代码/夹具并不会自动刷新已有产物，应按文件哈希判断其版本。

每次评测在项目 `tmp/counterfactual-evaluation-<唯一后缀>/` 下创建私有数据库，成功或异常
退出都只清理自己的临时目录，保留旧同名数据库和其他并行评测目录。临时路径、数据库 ID
和时间戳不参与结果，相同输入的并行报告应完全一致。

每条结果包含：

- 规范化案例及输入状态的 SHA-256、setup、单事实路径和实际差异路径；
- 基线/变形的 status、decision、批准量、单位及复核原因 `review_reason_code`（如适用）；
- 预设结果、变化/不变关系、各项检查与 `passed`；
- fixture、catalog、v2 rules 的文件 SHA-256 与字节数。

通过要求同时满足：恰好一个声明事实发生变化、基线预期正确、变形预期正确、关系正确。
`decision_changed` 和 `status_changed` 仅作诊断。例如数量限制仍可保持 ready；不变性案例
的 decision_changed 应为 false。复核原因也要精确匹配，不能只因决定都为 null 而通过。

`scope.mode` 固定为 `synthetic_demo`。本评测不估计行业准确率、安全率、真实资料效果，
不代替专业审核；尚未覆盖模型推理、真实来源真实性、完整规则组合、全部数量边界、
HTTP 端到端行为、外部运行环境以及任意时区/时间戳的有效期语义。

针对性验证命令：

```powershell
.venv/Scripts/python.exe -m pytest tests/test_counterfactual.py -q
```

测试验证可重复性、并行一致性、旧文件保留、构造/计算异常清理、有效期和批次边界，
并注入错误预期、错误复核原因与错误关系，确认报告失败。隔离测试项目不含 data/cases，
同时核对现有 gold 字节哈希，避免把读写冻结 gold 当作本评测的前提。
