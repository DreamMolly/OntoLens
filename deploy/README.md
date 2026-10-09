# OntoLens v0.4.0 业务容器部署

根Dockerfile与compose定义面向带认证的空业务工作区。2026-10-09 已用隔离业务卷实际 build、启动并完成业务流程、重建/重启持久化与模型解释检查，共30项通过；这不是Linux新机冷启动、长期负载或行业验证。命令仍是其他机器上的操作入口。完整账号/台账/隐私说明见[业务部署](../docs/38-operational-deployment.md)。

## 准备账户

在源码根目录先安装源码环境，创建业务初始管理员。这个步骤写本机账户/会话文件，但不启动服务：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-operational.ps1 -Bootstrap -CheckOnly
.\.venv\Scripts\python.exe scripts/manage_access.py --auth-file .runtime/operational/accounts.json set-password admin
```

密码只由本机initial-admin.txt或交互getpass管理，不进入.env模板、镜像或命令参数。确认更改成功后删除initial-admin.txt；accounts.json仅哈希，但仍按私有配置处理。

## 构建启动

```powershell
docker compose -f deploy/compose.yaml config
docker compose -f deploy/compose.yaml build ontolens
docker compose -f deploy/compose.yaml up -d ontolens
docker compose -f deploy/compose.yaml ps
```

浏览器打开127.0.0.1:8768登录。默认image tag为ontolens:0.4.0，build使用根Dockerfile和完整src/data。ONTOLENS_PORT可改变宿主端口。healthcheck访问auth/session只证明HTTP响应，不证明台账已发布/模型可用/行业核验通过。

业务workbench/access在ontolens-state命名volume，账户配置目录 `.runtime/operational` 整体只读bind到/config，实际读取/config/accounts.json；实际volume名由compose project生成。Linux部署要核对容器UID10001读accounts的受控权限与/state写权限，不以关闭认证或改root绕过权限失败。停止用 `docker compose -f deploy/compose.yaml stop ontolens`，不要把 `down -v` 当常规停止。

## 账户与反代

主机manage_access修改账户后，目录bind可即时看到原子替换后的新文件；服务读取新的revision即撤销旧会话，不要求force-recreate。配置目录不通过Web静态暴露；/state仍是独立持久业务/会话库。

对外服务使用TLS反向代理，设置PEIWU_COOKIE_SECURE=true与PEIWU_ALLOWED_HOSTS具体域名；维持loopback端口映射，代理处理实际外部入口。默认不信任proxy headers，Host/Origin必须按实际部署一致配置，不使用通配允许Host。

## 可选Nexent联动

先准备实际Nexent环境和nexent_network，配置本地token/专用Agent，再执行：

```powershell
docker compose -f deploy/compose.yaml -f deploy/compose.nexent.yaml up -d ontolens
```

覆盖层连接外部nexent_network，容器内用nexent-web:3000；宿主Web本轮用13000。专用产品解释Agent无工具，只接结果摘要；当前就绪和生成按observed_at/实际调用验证，不加载历史报告。2026-10-09 当前配置收据记录 `gpt-6-sol` 绑定与Agent2无工具解释；容器业务流中的模型解释也通过。7 MCP调用与Agent1工具编排属于2026-10-08历史运行，不能并入本轮 `gpt-6-sol` 验收。

## 备份与验收边界

停止后备份volume中的/state、主机accounts.json及关联SQLite文件，在独立实例恢复并验证active/来源/历史/账户。不要将volume、账户、初始密码、私有上传/导出或.env提交Git。

当前隔离容器30项检查已通过，实际build、业务流程、force-recreate、restart后数据/导出和会话持久化均有[验收收据](../artifacts/operational-deployment-20261009.json)。真实Linux新机安装、长时间运行、真实设备/领域评测和比赛正式提交各自保留未完成，不由Docker定义或healthcheck证明。

## 基础镜像与网络

根Dockerfile的PYTHON_IMAGE默认python:3.11-slim。默认registry不可获取时，可以受控来源传 `docker compose -f deploy/compose.yaml build --build-arg PYTHON_IMAGE=<镜像地址/摘要> ontolens`，不改产品源码。镜像tag不是不可变证据；实际来源/digest/build与运行验收分别记新收据。2026-10-09隔离验收镜像为 `ontolens:qa-20261009-final`，镜像ID及源码哈希记录在部署收据；README和材料的后续文字修订不属于当时镜像内容，新机器应重新构建并生成自己的运行收据。
