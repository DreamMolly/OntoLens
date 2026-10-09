# OntoLens 材料一致性

当前原生材料为 `submission/ontolens-development-design-draft.docx` 和 `submission/ontolens-presentation-draft.pptx`。可编辑源在 `submission/ppt-master/ontolens_review_ppt169_20260927/`，包含 SVG、说明图片、设计规范与逐页备注。

| 当前材料 | SHA256 |
| --- | --- |
| `submission/ontolens-development-design-draft.docx` | `84926c206408162396ed84121280185591d70bff4a0499b75b5440003fad0e61` |
| `submission/ontolens-presentation-draft.pptx` | `3990c6181eeffe24a045232f5133022d5751a5db52463e127055fbafed52da3c` |

## 内容合同

软件数字对应 `artifacts/local-validation-report.json`，规则评估对应冻结合成夹具；平台工具、实际模型请求与容器流程引用各自收据。Word/PPT 保留复现命令、SHA256、unavailable 与未验证范围，不将图片或模型自评冒充结果。

P10 是工作台首页结构示意，未运行实际核验；必须保留这条说明。当前界面图片来自实际运行页，不代替业务验证。图像字节和资产出处按 `design/asset-manifest.json` 核对。

## 复现方法

```powershell
officecli validate submission/ontolens-development-design-draft.docx --json
officecli validate submission/ontolens-presentation-draft.pptx --json
officecli view submission/ontolens-development-design-draft.docx issues --json
officecli view submission/ontolens-presentation-draft.pptx issues --json
.venv/Scripts/python.exe scripts/audit_deliverables.py
```

原生渲染按页核对文字、几何、图像比例和备注。schema 通过不是视觉验收；同名编辑源与 Office 内容应一致，导出前重新核对文件 SHA256。正式模板字段、行业效果和正式提交另验。
