# 复核历史基准与模型

D1.0 · 2026-10-09 · 历史、复核与模型边界已在当前实现中保留；专项和完整交互验收状态以D1.1变更记录为准。

[返回设计规范目录](README.md)。MUST/SHOULD/MAY 强度见[产品原则](01-product-principles.md)。

## 人工跟进是追加，不是改判

needs_review记录 MUST 展示reason_code、阻塞字段、requested_evidence与下一步；复核区域紧邻缺件内容，不靠用户去历史页发现。
复核状态/说明真实输入，业务reviewer来自登录actor；queued/in_review/evidence_requested/closed_no_decision四状态保留，closed不表示ALLOW或专业通过。
当前run引用 MUST 逐条呈现source/locator/hash/quote或缺失标记，默认不勾；没有选择也可保存真实补件说明，不伪称已检查全部引用。
原文待补件允许合法quote:null/unresolved:true；定位/哈希不完整的引用不能伪补足后发送。
追加成功后原决定、版本、原证据 MUST不变，新增review_history条目显示实际服务器时间/内容/引用；不能改成绿色安全结果。
写入失败保留reviewer/note/勾选，未知状态先查看run保存记录；切另一run有独立草稿，旧响应不清空新输入。详见[核验证据](04-verification-evidence.md)。

## 解释、检索与检证层的区分

程序决定是确定性业务结果；模型解释是对指定run的派生说明；JEV是可选引用辅助信号。MUST从视觉位置、标题和状态都保持区分。
模型未配置/不可用时允许核验、普通检索、原文查看与导出；禁用按钮旁MUST有可见原因，不以title作为唯一说明。
模型请求pending不得伪打字或改变允许数量；返回必须匹配run，保留模型响应的notice；失败保留程序证据并给解释重试入口。
JEV按钮显式live=true，仅获准非private来源在线；普通离线检索可用，一次配置/概率不能当语义或行业评测。
复制/外发流程MUST显示真实范围，private资料不外发；解释内容不执行来源内指令，派生文字安全输出。

## 历史与基准的阅读关系

历史是那一次申请的不可变快照；选历史run不会修改当前draft，查看/导出是读取，追加review才是明确写入。
基准是冻结案例与实际报告，MUST显示数据范围/分母，不用装饰性chart替代错误样例和限制。
表格数值、图标记和摘要 MUST共用同一报告；图中的坐标/单位/类别应可读，有完整文字或表格替代，不凭颜色判断。
MAY用简单SVG/chart展示真实比较，但不增加在线图表依赖和实时假指标；Office导出时相应表/图需可编辑而非截图冒充。

### 6.4 基准实验

MUST 保留 `[data-view="evaluation"]`、`#view-evaluation`、`#evaluate-button`、`#evaluation-content`。
顺序 SHOULD 为数据规模与冻结范围→实际报告/比较→错误与限制；读取失败与零结果 MUST 分开。
“重新运行基准”不得添加虚构完成百分比；目前 API 为实际 `/api/evaluation` 读取，文案与行为若调整必须明确真实执行范围。
数据表与图 MUST 保留数量、单位、分母、日期和来源；合成规则成绩不能叫行业准确率、本体算法成绩或专业验证。

### 6.5 运行记录

MUST 保留 `[data-view="history"]`、`#view-history`、`#run-list`、`#audit-log`；记录按时间、申请、版本、决定及未解决项可扫描。
历史查看 MUST 进入 viewing_history，与当前草稿隔离；必须显示该次申请摘要和快照，不用新 active 版本重画旧依据。
从记录返回 MUST 恢复列表选择/滚动与原草稿；导出仍对应历史 run；追加复核仍绑定历史 run，不覆盖程序原决定。
审计 JSON SHOULD 按需展开；未签名的哈希与追加序列只能说明内部一致，不能称不可篡改或来源认证。

### 6.6 连接与人员

MUST 保留 `[data-view="setup"]`、`#view-setup`、`#mcp-address`、`#model-status`、`#jev-config-status`。
顺序 SHOULD 为本地工作模式→人员未填值→服务配置/最近实测→可选接入说明；人员未知显示“未填写/—”，不生成审核背书。
配置/请求中/成功/失败/未验证分开；Nexent按当前observed_at。2026-10-08本轮7MCP及真实Agent已有成功回执，不能永久写未完成或使用历史ready。
MUST NOT 显示密钥、令牌、数据库私有路径或外发原文；核心核验不依赖 Docker、模型账户和额度。

## v0.4.0认证与最小外发

登录/退出/session actor是真实状态；8小时Strict/HttpOnly会话、CSRF与角色服务端强制，改账户revision撤销旧会话。登录不是专业身份认证。
普通模型遇private/未允许外发只接status/action/reason_code/evidence_count及模式标记，不发ID/quote/quantity/date；全部获准非private才permitted_evidence，显示context_scope/source_text_sent。
产品Nexent用专用无工具/无技能/无子Agent解释实例，只发去标识摘要；与合成比赛Agent7工具演示分开，不能把私有业务原文带入MCP编排。
