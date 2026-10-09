# OntoLens 答辩材料

- Canvas format: ppt169
- Created: 20260927

## Directories

- `svg_output/`: raw SVG output
- `svg_final/`: self-contained SVG visual preview; may be inserted manually as an SVG image, but PowerPoint Convert to Shape is unsupported
- `images/`: runtime image pool; converter assets keep their original short filenames when possible
- `icons/`: project icon set — selected library icons copied in (via icon_sync.py) plus any custom icons you add; embedded from here at export
- `notes/`: speaker notes
- `templates/`: project templates
- `live_preview/`: browser preview runtime files and history (lock.json, server.log, edits.jsonl, annotations.jsonl)
- `sources/`: source materials and normalized markdown
- `analysis/`: machine-extracted intermediate analysis (PPTX intake, image_analysis.csv) — the pipeline's canonical must-read source/asset facts
- `validation/`: cold workflow audit log, SVG quality reports, and PPTX postflight audit reports
- `exports/`: final native DrawingML pptx deliverables only (timestamped); `_native_charts_tables.pptx` name with `--native-charts-and-tables`, `_narrated.pptx` name when narration audio is embedded
- `backup/<timestamp>/`: svg_output/ archive (always written in default-flow mode; safe to delete old timestamps)


本轮 v0.4.0/D1.1-7 保留原生 11 页主题和数值几何，采用 officecli DOM 修改现有正文、备注、计数和第10页图片，不重新生成整套幻灯片。六台账业务导入、账户权限、候选检查/管理员发布、核验/复核/导出已实现，行业适用与独立专业验收另记。当前首页图不表示实际核验结果；最新原生 QA 收据见 `.runtime/material-public-ontolens-20261009/receipt.json`，历史 exports/validation 保留原范围。


公开与命名迁移验收：464 个测试、七阶段通过、158 项输入指纹一致；最终耗时与日志目录以 `artifacts/local-validation-report.json` 为准。新 OntoLens Docker 收据 `artifacts/operational-deployment-20261009-ontolens.json` 为 35 项检查通过。PPT 第 8 页可见 Agent/Skill 名称使用 OntoLens 与职责词，实际平台旧 ID 留在备注作兼容说明；未重新登记。QA 收据 `.runtime/material-public-ontolens-20261009/receipt.json`；旧 exports/validation 保留历史。
