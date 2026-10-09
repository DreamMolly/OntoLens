# 来源核对

核对日期：2026-09-22。外部赛制、仓库状态和部署要求会变化；正式报名和提交前由队员再次核对。

## 赛事规则

- 华为 ICT 大赛中国区创新赛页面：
  https://e.huawei.com/cn/talent/#/ict/innovation-details?zoneCode=027425&zoneId=98269700&compId=85132021&divisionName=%E4%B8%AD%E5%9B%BD%E5%8C%BA&type=C002&isCollectGender=N&enrollmentDeadline=2026-11-30%2023%3A59%3A59

2026-09-22 从该页核对到：赛题 3 面向医疗、金融、先进制造、政务等行业；要求多模态异构数据资产认知、低资源本体半自动构建、Nexent MCP/Skills 检索推理、跨文档多跳推理与决策溯源。赛题 3 初赛按四项技术能力评分；中国总决赛技术 60%、答辩 40%，另列多行业迁移与真实脱敏数据评测附加分。赛题 3 赛程为初赛—中国总决赛，国赛线上答辩为 15 分钟展示加 5 分钟问答。页面所列中国总决赛最高奖项名额为一等奖 4、二等奖 6、三等奖 8，实际名额由组委会按成绩确定。

- 北京工业大学计算机学院通知：
  https://cs.bjut.edu.cn/info/1076/4323.htm
- 大连理工大学创新创业学院通知：
  https://chuangxin.dlut.edu.cn/info/1020/16867.htm

以上学校通知只用于交叉核对赛题名称、3 名学生加 1 名指导教师和报名组织方式；冲突时以华为官网为准。

## 开源参考

- Nexent： https://github.com/ModelEngine-Group/nexent
  2026-09-22 查询到公开仓库采用 MIT 许可证；README 写有 Skills、MCP、记忆和编排能力，也给出 Docker/Kubernetes 部署要求。它是平台参考，不是本项目数据或算法证据。
- Docling： https://github.com/docling-project/docling
  2026-09-22 查询到 MIT 许可证；README 写有多格式文档、PDF 版面与表格、OCR 和 MCP 集成。用于界定文档解析能力，不把解析库当作创新。
- GraphRAG： https://github.com/microsoft/graphrag
  2026-09-22 查询到 MIT 许可证；README 将其描述为图结构 RAG 研究项目，并提示处于维护状态。用于图检索对照思路，不把组件拼装当作原创。
- automatic-KG-creation-with-LLM： https://github.com/fusion-jena/automatic-KG-creation-with-LLM
  2026-09-22 查询到 Apache-2.0 许可证，包含 competency questions、本体、知识图谱生成和评测。用于低资源本体流程参考。
- pySHACL： https://github.com/RDFLib/pySHACL
  2026-09-22 查询到 Apache-2.0 许可证，用于 RDF 图的 SHACL 约束校验。是否采用取决于数据格式、依赖和复现成本。

## 使用边界

搜索结果没有证明没有同类作品，也没有证明本项目会获奖。真正复用代码前，重新核对具体版本、许可证、依赖和署名要求。外部项目的星标数、学校通知和平台能力不能代替本项目的实测结果。

## 可追踪的证据记录

### ER-20260922-huawei-track3-01

- 来源类型：官方规则网页，已读取赛事内容、评分与奖项表，不是搜索摘要。
- 支持：初赛四项各 25%；国赛技术 60%（四项各 15%）、答辩 40%（展示/问答各 20%），另列附加分 10 分；赛题 3 无全球总决赛。
- 限制：这是 2026-09-22 网页版本，不能代表后续不会调整，也不能用最高奖项名额推算获奖概率。
- 允许措辞：按当前官网要求规划。禁止更强措辞：满足清单即可得奖、晋级必获奖。

### ER-20260922-nexent-readme-01

- 来源类型：Nexent 仓库 README_CN.md，已读取；当次文件标识 d3bcf3eefd43d028e5e59d1f0da034e6f97638f6。
- 支持：平台提供本地 Docker 部署说明、MCP 和 Skill 能力；README 列 Docker 最低 4 核/8 GiB、推荐 8 核/16 GiB，要求 Docker 24+ 和 Compose v2+。
- 限制：资源是上游一般要求，不是本项目性能实测；CPU/内存满足也不等于模型端点、依赖与工具配置已验证。
- 允许措辞：可作为平台基础。禁止更强措辞：本项目已成功接入或已稳定部署。

### ER-20260922-ontology-prior-01

- 规范文献记录：https://arxiv.org/abs/2403.08345 ，DOI https://doi.org/10.48550/arXiv.2403.08345 。
- 核验元信息：Vamsi Krishna Kommineni、Birgitta König-Ries、Sheeba Samuel；2024；From human experts to machines: An LLM supported approach to ontology and knowledge graph construction；arXiv 预印本 v1，2024-03-13 提交。
- 来源类型：abstract-only，已核验题名、作者、日期和摘要；HTML 全文请求超时，不能称全文审读。关联开源仓库 README 已读取，标识 f69883ee601ff0f6573f6b5fc3383327b0eabea0。
- 用途：已有半自动本体/图谱构建方向的查重线索，提示要比较 competency questions → 本体 → 图谱的既有流程。
- 限制：尚未核验全文实验与结果，不据此写其算法优劣；更不能据一篇文献声称完成系统性创新性检索。
- 下一步：取得全文并逐项比对候选产生、人工预算、排序、约束、版本和评测，再决定可声称的原创范围。

### ER-20260923-typesafe-jev-01

- 来源类型：TypeSafe 官方文档和重排 cookbook： https://docs.typesafe.ai/llms.txt 、 https://docs.typesafe.ai/cookbooks/rerank_typesafe.md 。
- 支持：Jev/System One 可用 Noul 返回候选支持关系的概率；代码可对候选排序，Choice/Score 置信度可用于人工复核分流。Noul 本身只返回概率，项目不伪造独立置信度。官方文档要求保留代码对工作流的控制，并按目标数据校准阈值。
- 项目使用：JEV 只接在 evidence_lookup 后做证据重排，不读取或修改 decision_check 的四种决定；未配置 TYPESAFE_API_KEY 时返回 unavailable 并保留普通检索。
- 限制：本地已安装 TypeSafe SDK 0.7.1，已用一条合成查询验证请求链路；尚未在独立领域资料上校准阈值，官方 cookbook 的准确率和成本数字不是本项目结果。

### ER-20260923-huawei-track3-supplement-01

- 来源类型：用户于 2026-09-23 提供的赛题 3官方原文，和当前已打开赛事页互相核对。
- 支持：赛题要求多模态异构资产识别、低资源本体半自动构建/动态更新、Nexent MCP/Skill 的检索—推理协同、跨文档多跳溯源和可复用工作流；入围中国总决赛后需开源至 GitCode 或 GitHub。
- 限制：当前项目只完成合成资料的文本/表格/手工图片摘录来源路径、目录资产识别基线和 MCP 模板；真实行业标准对齐、自动图像理解、低资源方法对照和真实资料验证仍待完成。

## AI取得的公开制度资料

首批6份来源、原文条号/页码、版本与用途见 `35-public-data-pack.md` 和 `data/public/official-lab-safety/manifest.json`。采集读取了官方正文和PDF，搜索摘要只用于发现。原件/转换正文留存与摘录各有SHA256。政府转载法律注明原颁布机关与转载承载机构；历史规范和现行法的特定保存期限差异保留为开发复核案例，不直接修改教学规则。
