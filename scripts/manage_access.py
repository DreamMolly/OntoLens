"""Manage local accounts without password command-line arguments or plaintext storage."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from peiwu.access import ROLES, read_accounts, update_account


def _password():
    configured = os.environ.get("PEIWU_ACCOUNT_PASSWORD")
    if configured is not None:
        return configured
    password = getpass.getpass("新密码（至少 12 个字符）：")
    if password != getpass.getpass("再次输入新密码："):
        raise ValueError("两次密码输入不一致")
    return password


def main(argv=None):
    parser = argparse.ArgumentParser(description="管理工作台本地账户；密码使用交互输入或 PEIWU_ACCOUNT_PASSWORD")
    parser.add_argument("--auth-file", type=Path, default=Path(os.environ.get("PEIWU_AUTH_FILE", ".runtime/accounts.json")))
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("username")
    add.add_argument("--name")
    add.add_argument("--role", choices=ROLES, default="viewer")
    for command in ("set-password", "disable", "enable"):
        commands.add_parser(command).add_argument("username")
    role = commands.add_parser("set-role")
    role.add_argument("username")
    role.add_argument("role", choices=ROLES)
    commands.add_parser("list")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            result = [{"username": username, "name": account["name"], "role": account["role"], "enabled": account["enabled"]}
                      for username, account in read_accounts(args.auth_file)["accounts"].items()]
        else:
            changes = {}
            if args.command == "add":
                changes = {"create": True, "name": args.name, "role": args.role, "password": _password()}
            elif args.command == "set-password":
                changes["password"] = _password()
            elif args.command == "set-role":
                changes["role"] = args.role
            else:
                changes["enabled"] = args.command == "enable"
            result = update_account(args.auth_file, args.username, **changes)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, EOFError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
