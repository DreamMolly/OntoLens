# 公开资料与制度版本演示

目的：让评委从真实公开原文看到项目的来源管理、跨文档检索和不确定性处理。资料范围为公开制度与合成台账，开发问题没有领域金标准。该演示不生成危化品领用业务决定。

## 准备

```powershell
.venv/Scripts/python.exe scripts/verify_public_corpus.py
```

打开 `data/public/official-lab-safety/manifest.json` 与 `artifacts/public-corpus-verification.json`。现场只在命令返回成功时展示报告。命令不访问日常工作台数据库或在线模型；每个资料包在独立临时数据库中导入公开摘录。

## 演示顺序（约三分钟）

1. 展示 manifest 的来源清单：六份文件、三个来源家族、两个开发包、十个开发问题。指出教育部原始PDF与深圳海事局政府转载法律的区别，说明两个包共享固定制度参考。
2. 打开 `PUB-Q06`，显示2023规范第二十五条（PDF第10页）和2026年施行法律第四十一条的条号、短引文、URL与摘录哈希。前者对一种登记资料写至少一年，后者对限定范围的收发记录写至少三年。
3. 查看合成台账 `LEDGER-VERSION-DEMO.csv`。该记录故意沿用旧片段且未确认适用范围。记录类型、品类、数量和适用日期缺证据，因此不能直接把“较新”或“数字较大”作为自动业务规则。
4. 展示报告该题的引用定位与缺失条件。`needs_review/decision=null` 是未审核材料的演示边界；此次没有调用业务 checker，也未运行模型法律判断。
5. 说明20/20个开发引用定位被词法检索找到的具体含义：这里只检查预先指定引用是否出现，不说明十道问题已被语义正确回答。领域标签、独立资料测试和真实台账仍是后续验证工作。

## 可现场复核的证据

| 检查 | 证据 |
| --- | --- |
| 原始文件与提取方式 | `.runtime/public-source-research/official-fetch-manifest.json`；原HTML/PDF只保存在本地采集目录 |
| 引文与保存正文一致 | `artifacts/public-source-quotation-verification.json`：21条规范化字面匹配 |
| 摘录字节、逐行定位与引用闭包 | `scripts/verify_public_corpus.py` 与 `artifacts/public-corpus-verification.json` |
| 台账是否真实 | CSV中 kind=synthetic；manifest明确没有实际校内人员或库存记录 |
| 是否自动改规则 | public-corpus报告 business_checker_called=false、synthetic_ledger_imported=false；冻结规则另有独立合成回归 |

## 展示一条本体映射候选

在核验报告展开 `alignment_candidates`。候选将《高等学校实验室安全规范》第十条（二）的培训与考核要求关联到 `ontolens-ontology-1` 中的 `authorized_for`。映射类型是 `prerequisite_only`，供审核人员判断实验操作准入证据是否应纳入核验。类别授权和有效期仍需依据校内制度单独核对。 [教育部发布页](https://www.moe.gov.cn/srcsite/A16/moe_784/202302/t20230220_1045998.html)

演示时依次打开三处。

1. **概念**。在 `src/ontolens/ontology.py` 查看 `Person → authorized_for → HazardClass`，再看候选绑定的本体版本。
2. **来源**。用报告中的 `PUB-MOE-2023#L1`、原文条号、PDF 页码和摘录 SHA256 回查。报告由核验器按索引找到原文片段并补齐这些字段。
3. **复核**。读出 `review_checks`，核对校内制度、场所、人员、考核记录和类别授权。该候选保持 `proposed`，`decision=null`。核验器会拒绝未知关系、错误定位、过版本记录和带决定的候选。

这一步属于公开制度对齐的待审示例。评委随后可按[合成授权演练](demo-runbook.md#评审主线同一申请三个核验结果)检查人工发布如何影响决定。两段使用各自的来源和数据，公开制度候选尚未经过专业审核或发布验收。

若要演示人工补件，在工作台点击“资料缺失”，逐条选择本次查看的引用，追加跟进记录，再导出复现包。人工记录不改变原核验结果；验收命令见 `docs/34-human-review-workflow.md`。
