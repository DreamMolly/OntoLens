# 格物镜 · OntoLens v0.4.0 演示脚本

只在独立演练库操作，明示资料性质；不要对日常业务库运行写入 smoke，不执行真实出库。账户身份不等于专业资质，正式模板个人字段仍由队员确认。

## A. 业务空库与登录

按 `docs/38-operational-deployment.md` 首次准备账户和独立数据库；业务入口 `powershell -NoProfile -ExecutionPolicy Bypass -File .\start-operational.ps1 -Bootstrap`，默认 `http://127.0.0.1:8768/`，Nexent 本机宿主 `http://127.0.0.1:13000/`、容器内部 3000。Bootstrap 会创建账户/会话文件，不能称无写入。初始密码只在本机读取，不截图或提交。准备过的历史合成工作台恢复仍用 start-demo.ps1，实际端口以启动收据为准。

## B. 六台账到版本

1. 登录管理员，确认 operational_empty，没有 demo-initial 事实。
2. 在原始资料按模板准备 people、chemicals、lots、cabinets、issues、rules，明确用途、授权声明和演练性质。
3. 导入后检查六原始/六规范化来源、hash/定位/版本以及字段、引用、单位、日期错误；上传只创建候选。
4. 预览影响，以 confirm_publish=true 和 expected_active 显式发布；遇到 active 改变应刷新重做预览，不能强行覆盖。
5. 切换 operator 展示可核验/导入但不能发布；reviewer 可追加跟进，viewer 只读。演练角色实际权限由服务端核对。

## C. 核验、原文、复核与导出

按演练台账依次展示正常、冲突、超量、过期批次和缺件；程序返回 ALLOW、DENY、LIMIT、ISOLATE 或 needs_review/decision=null。缺件不猜业务决定。

打开 source_id/locator 原文，核对 quote 和 SHA256；改申请立即 dirty/stale，历史切换保持当前草稿。追加复核的 actor 来自登录账户，记录不改变旧决定；补齐资料后要新核验。导出固定当时 run/快照，用 verify_evidence_export.py 离线重算，不能当作来源真实性认证。

演练授权变化时先提候选、预览、确认发布，再核验并回滚。过去运行保持原快照；图像只保存预览/人工摘录，不称 OCR 或自动图像理解。

## D. 当前 Nexent 和可选模型

当前 gpt-6-sol（model_id=2）与 Nexent Agent 2 解释收据见 `artifacts/nexent-model-configuration-20261009.json`；Docker 业务部署见 `artifacts/operational-deployment-20261009.json`，30 项检查通过。七工具逐项成功不等于模型一次用了全部七个；`memory_retrieval_disabled=true`、`tool_calls={}` 和私有原文不外发只在对应收据范围内成立。2026-10-08 的七 MCP 工具与 Agent 1/model 1 编排是历史收据。外部冷启动、真实行业资料和专业审核另验。

展示当前 observed_at、model_bound 与实际生成结果；不从历史 ready 推当前可用。私有或未获准来源只给模型固定枚举/计数，JEV 必须 live=true 且来源获准、非 private；服务失败不改变程序核验。Responses/JEV 单次真实调用只证明该次连通性，不是全协议、稳定性或行业准确率。

## E. 界面与答辩口径

D1.1-7 品牌旁折叠图标、边缘拖动/键盘调宽，九个单选控件与四个日期控件各 6/6 隔离测试通过、0 页面错误、0 外站请求；证据为 `artifacts/workbench-select-interaction-report.json` 与 `artifacts/workbench-date-interaction-report.json`。真实设备/读屏另验。P10 图片是当前首页结构示意，未运行核验；现场演练须用实际结果页面，不能将首页或保存的历史 ALLOW 伪作当前核验。

最终回归收据 `artifacts/local-validation-report.json`：456 passed、7 stages exit 0、154 项输入指纹一致；软件导入/核验/复核/导出可用，不表示实际行业字段适用、专业审核、独立评测、外部冷启动、长期稳定性或正式提交完成。Gitea 是否发布以根任务最终结果为准。
