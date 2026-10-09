# OntoLens v0.4.0 业务容器

根 Dockerfile 与 Compose 定义面向带认证的空业务工作区，入口为 `ontolens.web:create_app`，配置为 `ONTOLENS_*`，请求头为 `X-OntoLens-Token`。账户、台账和权限说明见[业务部署](../docs/38-operational-deployment.md)。

## 账户准备

从源码根目录安装项目环境并创建初始管理员，下面步骤不启动服务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-operational.ps1 -Bootstrap -CheckOnly
.\.venv\Scripts\python.exe scripts/manage_access.py --auth-file .runtime/operational/accounts.json set-password admin
```

初始密码仅在本机 `initial-admin.txt`，确认改密码并可登录后删除它。账户文件只有哈希也属于私有配置，密码不能进入镜像、环境模板或命令行。

## 构建和启动

```powershell
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build ontolens
docker compose -f deploy/compose.yaml up -d ontolens
docker compose -f deploy/compose.yaml ps
```

打开 `http://127.0.0.1:8768/` 登录，默认镜像 tag 为 `ontolens:0.4.0`，`ONTOLENS_PORT` 可调整宿主端口。容器非 root、drop ALL 能力、no-new-privileges，仅映射本机端口。健康检查只证明 HTTP 响应，不证明台账、模型或行业核验通过。

工作库与会话库位于持久命名卷的 `/state`；`.runtime/operational` 账户目录只读挂载到 `/config`，读取 `/config/accounts.json`。Linux 核对 UID 10001 的读写权限，避免通过改 root 或关闭认证掩盖错误。日常停止使用 `docker compose -f deploy/compose.yaml stop ontolens`，不删除卷。

## 账户和外部入口

主机管理账户后，目录挂载能读取原子替换的文件；revision 改变使既有会话失效，无需重建容器。配置目录不会作为静态文件暴露。

外部访问经 TLS 反向代理，设置 `ONTOLENS_COOKIE_SECURE=true` 和具体 `ONTOLENS_ALLOWED_HOSTS`，保持本机端口映射。Host/Origin 和代理头按实际部署核对，不采用通配主机。

## Nexent

先准备 Nexent、`nexent_network` 和本机凭证：

```powershell
docker compose -f deploy/compose.yaml -f deploy/compose.nexent.yaml up -d ontolens
```

容器访问 `nexent-web:3000`，宿主平台为 13000。Agent 为 `ontolens_compliance_review`，MCP 为 `ontolens-local`；业务解释实例 `ontolens_result_explainer` 无工具和 Skill，只接受受控结果摘要。当前 observed_at 与实际调用分别验证，模型不能改程序决定。

## 验证和备份

[业务容器收据](../artifacts/operational-deployment-20261009-ontolens.json)列本次隔离业务、权限、导入、四决定、缺件、导出、非 root 和重建/重启持久化检查。平台工具与模型各看对应真实收据；合成夹具、单次请求和容器健康不证明行业效果或持续稳定。

停止后备份关联 `/state`、账户文件和 SQLite 辅助文件，在独立实例恢复并检查 active、来源、历史与会话。卷、账户、密码、私有资料/导出和 `.env` 不进入 Git。独立 Linux 新机、长期负载、实际恢复、真实资料评测和正式提交仍有单独验收。

默认基础镜像为 `python:3.11-slim`，可通过 `PYTHON_IMAGE` 构建参数选择受控源。tag 不是不可变证据，实际镜像 ID、构建输入和运行结果以收据为准；每台机器重新构建并生成自己的运行证据。
