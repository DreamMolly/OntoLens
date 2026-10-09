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

若要演示人工补件，在工作台点击“资料缺失”，逐条选择本次查看的引用，追加跟进记录，再导出复现包。人工记录不改变原核验结果；验收命令见 `docs/34-human-review-workflow.md`。
