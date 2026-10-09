# JEV 社区用法调研与 OntoLens 拓展候选

日期：2026-09-24。用户明确要求：不局限官方示例，重点看 GitHub 开发者实际探索。

本页保留2026-09-24调研的范围与结果，产品文案统一为格物镜 · OntoLens；旧录制协议和原档案名仍按[品牌与兼容说明](39-brand-compatibility.md)保留。本页的社区阅读及历史合成调用不代表今天的在线状态或真实行业效果。

## 当前状态，先说清楚

最初调研时本项目仅有 Noul 证据重排。2026-09-24 已实现第一项拓展：引用字面核验、可选支持/矛盾信号和人工复核提示，验证记录见 `22-citation-review.md`。本地引用核验已经通过浏览器、MCP 与真实 Nexent 工具调用；普通相关性重排已用一条合成查询在线验证，引用支持/矛盾概率仍未在线验证。其余玩法仍是设计候选。没有运行社区项目或安装其插件/数据库扩展；该轮只请求了一次项目固定的合成查询。

官方资料仅用来核对 SDK、模型和字段含义；玩法发现来自社区原始项目。合集只作线索，README 自报成绩、Star 数或代码存在都不等于 OntoLens 已经取得同样效果。

## 社区实现与可迁移思路

| 原始仓库 | 实际看到的实现 | OntoLens 可以怎样借鉴 | 明确限制 |
| --- | --- | --- | --- |
| chenmingtang830/jevgraph | 本地实体候选和类型约束先缩小实体对，Jev 在封闭关系集合中选择；代码做 schema 与证据校验，输出 proposed/review/rejected | 给“人员—授权类别”“批次—物料”等候选关系补语义支持信号，保留原文位置，供人审核 | 比简单重排更宽，需要先确认 JEV 角色扩展；不能把关系候选自动写入有效本体 |
| MarissaFamularo/citation-verifier | 将被引用句与来源片段交给 Choice，区分支持、矛盾、不涉及；人工裁定单独保存 | 检查 Nexent 解释中的每项主张是否得到引用支撑，不让“有引用”冒充“引用支持结论” | 不照搬浏览器存钥和自动重试；OntoLens 必须先通过精确 quote/locator/SHA 校验，不接受模型编造引文 |
| mizchi/jev-test-filter | 将 diff 作为共享状态，逐个测试做影响程度 Score；代码保留直接改动及缺失回答的保守路径，阈值可离线重放 | 对制度/授权材料变更后的历史申请做复核优先级排序；先由程序确定直接受影响集合，再用语义信号提示遗漏风险 | 只能影响复核队列，不能因此跳过完整冻结回归或 H 集，不能更改决定 |
| devagrawal09/jev-review | Noul 多维初筛，再做证据片段选择、问题类型、影响程度与评审路由；编排在代码里 | 把候选审核拆成“证据是否支持、是否存在冲突、上下文是否足够”等明确维度，再有限跟进高优先项 | 模型分数是复核提示，不是已证实的缺陷、领域合规或风险结论 |
| browser-use/jev-ultrafast | 将可观察对象转成有限编号候选；并行判断操作及候选目标，执行器只消费与选中操作匹配的分支并复核新鲜度 | 借有限候选空间与并行多问题的组织方法，减少无约束文本输出；可用于证据候选评审 | 暂不让 JEV 自行操作领用页面、发布版本或决定放行；其浏览器性能不能平移成项目成绩 |
| thruwire/foreman | 独立观察循环将多个职责拆成 Noul 问题，代码仲裁继续、验证、升级给人等动作 | 研究审核过程的证据完整性和重复失败提醒，而不是让模型自报“工作完成” | 不安装来接管当前助手；不让 JEV 自动花钱、停止用户目标或替代真实测试结果 |
| qkal/Canny | 程序根据实际账本作门禁；Jev 仅提供语义建议；请求按内容哈希缓存，结果可重放 | 记录证据/问题/模型版本与支持信号，比较不同复核策略时重放已授权记录，减少重复调用 | 原实现允许无密钥时读取缓存；不能照搬为 OntoLens 的在线 available。无密钥仍返回 unavailable，重放必须另标 recorded/replay |
| realZachi/pg-jev | 用语义谓词筛选/排序数据库行，便宜的精确条件先过滤，按行内容缓存、批处理并限制调用 | 在程序先筛出的、明确允许外发的片段上做“哪项需要复核”的语义筛选；保留数量/日期等确定性检查 | 不直接安装 PL/Python 扩展，不让 SQL 扫描自动外发整表或消耗额度 |

另查看了 kitfunso/hippo-memory 的可选 Jev 重排与评测说明，以及 jaredpalmer/kev 的本地类型化模型路线。前者把检索提升与回答质量分开报告，这种评测边界值得借鉴；后者是 Jev-like 替代模型，不是 TypeSafe Jev，不能混为同一个模型或共用成绩。它们的线上/性能数据本轮未复现。

## 适合 OntoLens 的组合

建议主线：资料变更 → 程序定位影响范围 → 候选知识与证据审查 → 复核队列 → 人工确认 → 确定性重放。变更影响复核目前已实现离线信号契约，在线和真实资料验证仍待补。

### 优先候选一：解释—引用支撑核验

程序先校验引用存在、定位与 SHA 一致，再让 JEV 只判断“片段是否支持指定主张”。支持不足或互相冲突仅作为人工复核提示。不得用模型分数认证法规，也不得替换 decision_check 的 action/approved_quantity/reason_code。

### 优先候选二：变更影响复核排序

旧/新资料的确定性字段差异和图路径先形成候选集合；JEV 对候选审查问题提供语义支持信号。直接受影响、证据缺失和模型错误的对象不得被排序器静默排除。所有既有回归照常完整运行。

### 有条件候选三：本体关系候选审查

先由程序给出实体、允许的关系和精确来源片段，再用 JEV 判断支持与不足。当前已实现关系候选的离线支持信号契约，仍只产生 proposed/review，不生成已审核事实。不把 Noul 的概率当作 Choice/Score 的 confidence。若要让 JEV 选择关系类型或生成新的领域候选，需要明确修订此前“只做证据重排和复核优先级”的限制。

### 辅助：多问题批处理与录制/重放

先测小规模分组再决定批量大小，不抄别人的批量阈值。缓存键应包含来源快照、原文、问题正文/版本、模型与参数；权限撤销后不允许新外发。OntoLens 保留显式 `peiwu-jev-replay-1` 录制/重放协议；重放 `request_count=0`，不能把缓存或模拟答案当作一次新的 JEV 请求。

## 不能照搬的内容

- citation-verifier 的 selectPassage 有引用未定位时仍使用传入 quote 的后备分支；OntoLens 必须拒绝未通过本地引用校验的文本，不仅依靠上游模型保证。
- JevReview、Foreman、JevGraph 等使用的默认阈值只属于各自实验，不能当 OntoLens 的安全阈值。
- 不采用社区样例中的自动重试、无界预取、浏览器存钥、最新模型别名或全库外发默认值。
- 本体候选、低概率冲突与解释支持度不写回库存、授权或规则；模型不输出四种业务决定。
- 仍只有显式 scripts/verify_jev.py --live 可发请求；本轮只验证了一条合成相关性请求，不能声称在线功能在真实资料上完成。

## 阅读证据与复现等级

原始 API 文件快照在 artifacts/jev-research/，保留路径和 Git blob SHA；这是文件级阅读证据，不是完整仓库的统一 commit 锁定。未执行其中的安装/运行指令。

| 仓库 | 读过的关键文件 | 代表文件 blob SHA |
| --- | --- | --- |
| jevgraph | src/jevgraph/builder.py、providers/gateway.py、tests/test_core.py | 1eed58bb24f13e054acf21512dce7bd7a7d59777 |
| citation-verifier | src/lib/typesafe.js、sourceLocate.js、review.js | 25e31164909c85ba827473dc8b73aea31d6becde |
| jev-test-filter | src/questions.ts、src/gate.ts | 71547ce3ee80fa5cf2889e22fccde7ecfc116ae6 |
| jev-review | src/review/workflow.ts、src/review/judgments.ts | 5ebd38842ae030af527b223a393ab98051738ddd |
| jev-ultrafast | jev_ultrafast/model.py | d31174749e1451dbbd2a05f255f6f87fe296b122 |
| Foreman | src/foreman/foreman/jev.py | 4e84b45dbdb3bfa95d6703ba1992c9c7ab936bb0 |
| Canny | src/jev.ts、test/jev.test.ts | f2d5fe4bd7fe34f4185cd5d35a11cf6bc0863726 |
| pg-jev | sql/jev--0.2.0.sql | 2a7f4fe22c088a3bed56d893a2fcb5008e1717a1 |

阅读源码不等于证明效果。移植前还要核对许可证、外发范围、依赖与失败行为；线上验证必须有明确授权，并用与调参分离的资料评测。不增加或改写冻结 H01–H60，不把社区 benchmark、自报准确率或示例账单写成 OntoLens 结果。
