# OntoLens 材料质量检查

材料为初赛草稿，面向代码评审与项目展示。当前文件为[Word 开发设计稿](../submission/ontolens-development-design-draft.docx)与[PPT 答辩稿](../submission/ontolens-presentation-draft.pptx)，可编辑源见 `submission/ppt-master/ontolens_review_ppt169_20260927/`。

## 检查内容

原生 Word 为四页、PPT 为十一页。重点核对文字、分页、几何、图像比例、备注、命令和数字；schema 通过不是视觉验证。每份材料保留 SHA256、unavailable 与未验证范围，软件测试数对应 `artifacts/local-validation-report.json`。

P10 展示 D1.1 首页结构，caption 明确“尚未核验”，不能当作当前 ALLOW 或真实业务效果。模型和容器调用引用各自收据，不用界面截图代替行业实验。

## 验证入口

```powershell
officecli validate submission/ontolens-development-design-draft.docx --json
officecli validate submission/ontolens-presentation-draft.pptx --json
officecli view submission/ontolens-development-design-draft.docx issues --json
officecli view submission/ontolens-presentation-draft.pptx issues --json
.venv/Scripts/python.exe scripts/audit_deliverables.py
```

原生截图按页检查后保存在本机 QA 目录；最终 SHA256 与交付一致性结果见 `artifacts/deliverable-consistency-report.json`。Word 模板的空段、缩进或技术标点提示应分别评估，不把提示数量当作错误数量。

实际行业资料、独立专业审核、外部新机、长期稳定性和正式提交仍各自待验。官方姓名、认证和最终模板字段不能自行填入。
