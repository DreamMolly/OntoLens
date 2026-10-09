# OntoLens 命名与兼容

项目名称为 **格物镜 · OntoLens**。早期工程名为“配伍 / peiwu”，品牌更新时只改了网页与材料的部分文案，因此旧包名、配置、接入模板和历史文件仍有残留。本次将当前源码和使用入口统一到 OntoLens，同时保留已有数据、部署与外部客户端的兼容读取。

## 当前入口

| 项 | 推荐名称 | 兼容范围 |
| --- | --- | --- |
| Python实现 | `src/ontolens/`，`import ontolens` | `src/peiwu/` 只作兼容别名，不复制另一份实现 |
| 命令行 | `ontolens` / `python -m ontolens` | `peiwu` / `python -m peiwu` 继续调用同一实现 |
| Web工厂 | `ontolens.web:create_app` | `peiwu.web:create_app` 可用于已有启动配置 |
| 环境变量 | `ONTOLENS_*` | 对应 `PEIWU_*` 为回退配置；新名称优先，包括显式空值 |
| 请求头 | `X-OntoLens-Token` | 服务器继续接受旧 `X-Peiwu-Token` |

更新源码后在同一虚拟环境重新运行 `python -m pip install -e '.[workbench,jev,test]'`，重启工作台进程，Docker重新构建。已有数据库、账户、私有台账和模型配置原样保留，不因命名迁移清空或重建。

`.env` 可以继续使用旧变量。设置新变量时避免同时维护两套不同值；程序读取新名字优先。状态隔离、CSRF和来源外发权限不因兼容读取而改变。

## 为什么还会出现旧标识

以下值是数据或外部依赖契约，直接改文字会使旧导出、历史收据或已经安装的Agent无法互认：

- `peiwu-replay-1`、`peiwu-review-1`、账户/本体schema：序列化格式的版本标识，不是当前产品名。
- `peiwu-local`、`peiwu_compliance_review`、`peiwu-intake/evidence/decision`：此前导入的 Nexent 服务、Agent和Skill机器标识。既有联通链路继续使用它们，专用解释实例使用 `ontolens_result_explainer`。
- `artifacts/peiwu-*.json`、`peiwu-nexent-agent.zip`：验证和导入包的既有文件标识；哈希与历史矩阵引用这些精确字节。
- `submission/peiwu-*.docx/.pptx` 与旧PPT制作目录：历史材料路径，正文品牌以格物镜/OntoLens为准。
- 历史日志的 `src/peiwu/...`：当时真实执行路径。当前实现已迁到 `src/ontolens`，旧日志保留当时范围。

历史文件和机器标识集中解释，不全局替换证据或数据库格式。新代码、启动命令和面向评委的项目介绍优先使用 OntoLens。后续若升级导出协议或重新注册 Nexent 工具，需要单独记录版本迁移与实测结果，不能仅凭名称改变宣称联通已验证。

## 验证要求

迁移验证覆盖新旧模块/类型/审计上下文是同一对象、两种命令行入口、配置优先级、两种请求头和同一份导出的离线重算。完整软件与浏览器验收见 `artifacts/local-validation-report.json`，容器运行验收按对应时间戳另报。

公开仓库保留历史路径与协议的原因如上，不将旧命名兼容视为另一份产品，也不把历史验证写成最新代码已经通过。
