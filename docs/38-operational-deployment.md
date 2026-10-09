# OntoLens v0.4.0 业务工作区部署与数据边界

迁移后的实际容器与35项业务检查见[新容器收据](../artifacts/operational-deployment-20261009-ontolens.json)，完整464项软件回归、七阶段及158项指纹见 `artifacts/local-validation-report.json`，快照为 `artifacts/source-validation/20261009-094214-e5337f3f/`。下方较早的456/30及10-08模型工具收据只代表对应历史阶段。

本说明面向完整源码目录的实际启动和操作。默认业务库为空、登录后导入六类资料，不用合成数据替代业务事实。Windows业务入口已提供；容器构建、独立Linux/新机冷启动与当前完整Nexent展示以最新验收收据为准，本文提供的命令不表示全部已执行。

当前主实现位于 `src/ontolens/`，新的模型、工作库、账户与部署配置推荐使用 `ONTOLENS_*`；已有 `PEIWU_*` 环境仍兼容，不要求重置账户、数据库或模型配置。优先级及保留的协议标识见[品牌与兼容说明](39-brand-compatibility.md)。

## Windows首次启动

在源码根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[workbench,jev,test]"
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-operational.ps1 -Bootstrap
```

默认监听127.0.0.1:8768；可用 `-NexentUrl http://127.0.0.1:13000`，跨平台Python入口对应 `--nexent-url`。新库为operational_empty；已有合成active库不能混作业务库，入口会要求独立数据库而保留旧资料。自定义数据库/账户用Python入口 `scripts/run_operational.py --database <路径> --accounts <路径>`。

初始admin密码随机，只有本机 `.runtime/operational/initial-admin.txt` 含明文；账户文件只存PBKDF2哈希。不要截图、发送或提交这个文件。登录后以以下命令交互更换密码，确认可用再删除初始文件：

```powershell
.\.venv\Scripts\python.exe scripts/manage_access.py --auth-file .runtime/operational/accounts.json set-password admin
```

后续启动省略Bootstrap；CheckOnly检查配置，首次Bootstrap与CheckOnly结合会创建初始账户/会话库，不能把它称完全无写入。

## 账户与权限

```powershell
.\.venv\Scripts\python.exe scripts/manage_access.py --auth-file .runtime/operational/accounts.json add operator01 --name "业务操作者" --role operator
.\.venv\Scripts\python.exe scripts/manage_access.py --auth-file .runtime/operational/accounts.json add reviewer01 --name "复核记录者" --role reviewer
.\.venv\Scripts\python.exe scripts/manage_access.py --auth-file .runtime/operational/accounts.json list
```

add/set-password用getpass交互输入，不使用命令行明文密码。密码12–1024字符，PBKDF2-SHA256 600,000次随机盐；会话绝对8小时，Cookie为Strict/HttpOnly，Secure由实际TLS部署配置。改密码、角色或启停账户改变revision，使旧会话失效；退出撤销当前会话。

| 角色 | 读取 | 核验/解释/JEV | 导入/候选 | 追加复核 | 发布/回滚 |
| --- | --- | --- | --- | --- | --- |
| admin | 是 | 是 | 是 | 是 | 是 |
| operator | 是 | 是 | 是 | 否 | 否 |
| reviewer | 是 | 是 | 否 | 是 | 否 |
| viewer | 是 | 否 | 否 | 否 | 否 |

权限由服务器验证，不以按钮隐藏代替。资料/操作审计由ContextVar绑定已登录actor，导入操作者和复核人不能用网页随填值伪造登录身份。登录账号不代表获认证专业资质；角色权限是操作级，共享工作区尚未逐文档ACL/多租户隔离。

## 六类台账格式与授权记录

登录后在“原始资料”打开“导入业务台账”，从模板开始准备people、chemicals、lots、cabinets、issues、rules。前五可JSON/YAML/CSV，rules仅JSON/YAML；每份1–2,000,000字节，UTF-8或带BOM，不能上传空文件。

模板来自 `GET /api/ledger-bundles/template`，要通过当前登录会话读取。JSON/YAML按实体ID映射；CSV有唯一id列，classes/allowed_classes用JSON数组文字，banned用true/false，库存/上限为数值。rules遵循模板字段和本单位制度，不复制演示规则当真实适用规则。

| 组 | 最重要的绑定 |
| --- | --- |
| people | student/teacher、banned、classes、authorization_basis、valid_from/valid_until |
| chemicals | hazard_class、unit、per_issue_limit |
| lots | chemical_id引用、on_hand、available/expired/damaged |
| cabinets | allowed_classes |
| issues | 人员ID与已领/未归还危害类别 |
| rules | version、student_fraction、制度开关和incompatible_pairs |

导入要求label、basis、purpose、authorized_by、recorded_at和local_operation_authorized确认。记录的是操作者的授权声明，软件检查不认证签署人、文件真实或领域适用性；这些必须在具体业务接入时核对。

软件同时保留六原始来源与六规范化来源，绑定原hash/定位/版本。拒绝重复字段、非有限数、非法引用/类别/日期/单位等。台账导入所有external_model_allowed=false，非合成people固定private。

## 候选发布与业务核验

导入仅创建候选；查看检查、预览前后影响和来源绑定。admin确认业务发布使用confirm_publish=true及expected_active；active变化时刷新并重新预览，不能自动覆盖。回滚同样指定目标与显式确认，不删除过去记录。

发布后mode为imported_workspace，表单使用本次有效资料。核验结果是规则计算，不自动执行真实出库；补件跟进保持needs_review，必须补齐资料并形成新的核验才能得到新决定。

历史/导出固定当时run与快照，编辑草稿即时stale；上传或复核不会改过去决定。未知写入先查保存状态，查不到近期记录不能推断未写；不自动重复提交。

## 私有资料与模型调用

普通解释模型在任何来源private/未允许外发或上下文超限时，只发送固定枚举/计数摘要：status、action、reason_code、evidence_count及模式标记，不发送姓名/ID/引文/数量/日期。全部证据非private且明确获准外发时才可用permitted_evidence，界面须显示scope。

产品Nexent辅助报告始终用去标识摘要，专用ontolens_result_explainer须无tools、skills、子Agent及聊天metadata，不访问MCP业务资料。模型请求结果不能覆盖程序决定。

JEV在线必须显式live=true，只有获准且非private的来源参与；私有内容不能因勾按钮外发。配置存在或单次概率不证明语义可靠，普通检索/程序核验独立于在线服务。

## Nexent与端口

本机产品Nexent地址用 `ONTOLENS_NEXENT_BASE_URL=http://127.0.0.1:13000`，`ONTOLENS_NEXENT_API_TOKEN` / `ONTOLENS_NEXENT_AGENT_ID` 只放本机环境。宿主3000受Windows排除端口限制，现用13000，容器内部仍3000；容器联动使用nexent-web:3000和nexent_network。

当前状态通过 `/api/integrations/nexent` 真请求，observed_at、model_bound、tool_free、model_verified_at和当前调用结果分别解释，不加载历史ready作为当前状态。[2026-10-09 模型配置收据](../artifacts/nexent-model-configuration-20261009.json)记录同一中转供应商的 `gpt-6-sol` 健康检查与Agent绑定；[容器验收收据](../artifacts/operational-deployment-20261009.json)中30项检查通过，包含隔离业务流和Agent2无工具解释。7 MCP与Agent1工具编排对应单独的2026-10-08历史运行，不能并入本轮gpt-6-sol链路。此前gpt-5.6-terra的provider 404失败收据保留，错误不会再被当作成功回答。断连时核心核验独立可用；持续运行/新机另验。

## Docker与持久化

定义见[deploy/README.md](../deploy/README.md)。业务容器非root、no-new-privileges、drop ALL能力、仅127.0.0.1:8768映射；workbench/access SQLite在持久volume，整个.runtime/operational账户配置目录只读bind到/config，实际账户路径为/config/accounts.json。

先在主机生成账户，再构建启动；账户管理是主机CLI，只读目录bind允许看到主机原子替换后的新文件，账户revision改变立即使旧会话失效，无需为密码变更重建容器。目录不经Web静态暴露；业务DB与session DB另在/state持久volume，不能把/config内其他历史文件当当前业务库。

外部使用应经TLS反向代理，将 `ONTOLENS_COOKIE_SECURE=true`、`ONTOLENS_ALLOWED_HOSTS` 设为具体域名，不用通配符。未经认证的裸create_app只支持本机，不作为共享业务部署。Uvicorn默认不信任转发头；反代配置要与Host/Origin及实际TLS访问一致。

## 备份、恢复与验证

停止业务服务后备份整个关联工作库、access.sqlite3及accounts.json；原始/规范化来源和审计在工作库内。保留相关SQLite辅助文件，避免热拷贝只复制一个.db。初始明文密码文件不是常规备份必需。

恢复先用独立目录/数据库核对active版本、来源hash、历史/复核和账户状态，再切实际工作入口；不要覆盖唯一现有备份或删除演示库。容器volume删除命令不属于日常停止。

开发验证用显式synthetic隔离库，不对私有业务库跑写入smoke。2026-10-09完整七阶段 `456 passed` 且各阶段exit 0，日志快照见 `../artifacts/source-validation/20261009-052126-c6f21459/`；隔离容器build/业务流/重建/重启持久化和模型解释通过。专项结果不能相加当全suite；真实资料、Linux新机、长期运行和行业效果仍单独待验。规划/拓展与发布门槛见[里程碑](37-teammate-handoff.md)。
