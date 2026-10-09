"""Start the authenticated business workspace, without seeding sample facts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import sqlite3

from peiwu.access import AccessController, update_account

ROOT = Path(__file__).resolve().parents[1]


def load_environment():
    path = ROOT / ".env"
    if path.is_file():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith(("PEIWU_", "TYPESAFE_")) and key not in os.environ:
                os.environ[key] = value.strip().strip("\"'")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--database", type=Path, default=ROOT / ".runtime/operational/workbench.sqlite3")
    parser.add_argument("--accounts", type=Path, default=ROOT / ".runtime/operational/accounts.json")
    parser.add_argument("--nexent-url", default=None, help="Current local Nexent origin (optional)")
    parser.add_argument("--bootstrap", action="store_true", help="Create an initial admin only when the account file is absent")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    load_environment()
    if args.nexent_url:
        os.environ["PEIWU_NEXENT_BASE_URL"] = args.nexent_url
    database = args.database.resolve()
    accounts = args.accounts.resolve()
    if database.exists():
        with sqlite3.connect(database) as connection:
            row = connection.execute("SELECT v.snapshot FROM versions v JOIN settings s ON v.id=s.value WHERE s.key='active'").fetchone()
            if row and json.loads(row[0]).get("mode") == "synthetic_demo":
                parser.error("业务入口需要独立业务数据库；请更换 --database，已有演示库会原样保留")
    if args.bootstrap and not accounts.exists():
        password = secrets.token_urlsafe(24)
        update_account(accounts, "admin", name="项目管理员", role="admin", password=password, create=True)
        credentials = accounts.with_name("initial-admin.txt")
        # This file is local runtime state, excluded from every source release.
        fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write("OntoLens 初始管理员\n用户名：admin\n密码：" + password + "\n请使用账户管理命令更换密码后删除本凭据文件。\n")
        print("初始账户已创建。登录信息保存在本机：" + str(credentials))
    if not accounts.exists():
        parser.error("请先用 scripts/manage_access.py 创建账户，或首次启动时加 --bootstrap")
    AccessController(accounts, accounts.with_name("access.sqlite3"))
    os.environ.update({"PEIWU_ROOT": str(ROOT), "PEIWU_DB": str(database),
                       "PEIWU_AUTH_FILE": str(accounts), "PEIWU_SESSION_DB": str(accounts.with_name("access.sqlite3")),
                       "PEIWU_WORKSPACE_MODE": "operational"})
    if args.check_only:
        print(json.dumps({"ready": True, "mode": "operational", "auth_enabled": True,
                          "database": str(database), "port": args.port}, ensure_ascii=False))
        return 0
    import uvicorn
    uvicorn.run("peiwu.web:create_app", factory=True, host=args.host, port=args.port,
                proxy_headers=False, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
