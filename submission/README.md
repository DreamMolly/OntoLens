# 格物镜 · OntoLens 初赛材料工作区

本目录为第十一届华为 ICT 大赛创新赛赛题 3 的材料草稿，报名已完成。v0.4.0 软件支持角色登录、空业务库、六台账导入/候选检查/管理员发布、旁路核验、追加复核和证据导出；D1.1-7 首页与侧栏、九个单选控件已有隔离交互验收。实际行业字段适用、专业审核、独立评测、新机冷启动、长期稳定性与正式提交分别待完成，不执行真实出库。

## 文件

- `design-document.md`：设计说明与软件/研究边界。
- `demo-runbook.md`：独立演练库和当前 Nexent 展示路径。
- `evidence-matrix.yaml`：对外主张、证据、命令与限制。
- `peiwu-development-design-draft.docx`：保留原生四页版式的开发设计草稿。
- `peiwu-presentation-draft.pptx`：保留原生十一页主题、几何和可编辑文字，带当前首页结构图与备注。
- `ppt-master/peiwu_review_ppt169_20260927/`：同步的 editable SVG、图片、spec 与备注；历史 exports/validation 保留其历史范围。

## 状态与证据

DONE 表示主张的指定软件范围有代码或测试支撑；PARTIAL 表示尚有该主张的未验证条件；PENDING 表示所需资料或外部验收未完成。SYNTHETIC 明示演练台账/规则的性质，不能写成行业效果。未完成研究不会自动否定软件可部署性，软件成功也不会关闭研究门槛。

2026-10-09 当前 gpt-6-sol（model_id=2）配置收据通过，见 `artifacts/nexent-model-configuration-20261009.json`；Docker 业务部署收据 `artifacts/operational-deployment-20261009.json` 为 passed，30 项检查覆盖模型解释、容器连接、私有原文不外发、健康与重启持久化。解释 Agent 的 `tool_calls={}` 与 `memory_retrieval_disabled=true` 属于该收据边界。外部冷启动、真实行业资料和专业审核仍待。

P10 为 D1.1-7 当前首页结构示意，尚未运行实际核验，不能当作本轮 ALLOW 100 mL 截图。图片由真实 1440×1230 viewport 捕获，收据 `.runtime/ontolens-D1.1-final-capture-receipt.json`；材料最终原生 QA 见 `.runtime/material-final-456-20261009/receipt.json`。

软件启动、账户、授权声明、私有资料和备份操作见 `docs/38-operational-deployment.md`；当前规划见 `docs/37-teammate-handoff.md`。最终软件回归见 `artifacts/local-validation-report.json`：456 passed、7 stages exit 0、154 项输入指纹一致。源码已推送到私有 Gitea `fulao/OntoLens`，材料不代替正式提交。官方姓名、认证与行业效果不得自行填入。

公开资料演示 `public-data-demo.md` 使用六份官方制度加合成台账，不是实际校内台账、独立盲测或法律合规认证。
