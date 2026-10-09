"""Local password accounts and revocable, absolute-lifetime browser sessions."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time

SCHEMA = "peiwu-access-1"
ROLES = ("admin", "operator", "reviewer", "viewer")
PASSWORD_ITERATIONS = 600_000
SESSION_TTL_SECONDS = 8 * 60 * 60
LOGIN_WINDOW_SECONDS = 300
LOGIN_FAILURE_LIMIT = 5


class AccessError(ValueError):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


def validate_username(username: str) -> str:
    if (not isinstance(username, str) or username != username.strip() or not 1 <= len(username) <= 80
            or any(character.isspace() or ord(character) < 32 for character in username)
            or any(character in "/\\:" for character in username)):
        raise ValueError("用户名须为 1 至 80 个字符，不含空白、控制字符或路径符号")
    return username


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise ValueError("密码须为 12 至 1024 个字符")
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${derived.hex()}"


def _password_parts(encoded: str):
    if not isinstance(encoded, str):
        raise ValueError("账户密码哈希格式无效")
    parts = encoded.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        raise ValueError("账户密码哈希格式无效")
    iterations = int(parts[1])
    if not 200_000 <= iterations <= 2_000_000 or not re.fullmatch(r"[0-9a-f]{32}", parts[2]) or not re.fullmatch(r"[0-9a-f]{64}", parts[3]):
        raise ValueError("账户密码哈希参数无效")
    return iterations, bytes.fromhex(parts[2]), bytes.fromhex(parts[3])


def verify_password(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or len(password) > 1024:
        return False
    try:
        iterations, salt, expected = _password_parts(encoded)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("账户配置有重复字段")
        result[key] = value
    return result


def read_accounts(path: Path) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("无法读取账户配置") from error
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA or not isinstance(payload.get("accounts"), dict):
        raise ValueError("账户配置 schema 无效")
    for username, account in payload["accounts"].items():
        validate_username(username)
        if (not isinstance(account, dict) or account.get("role") not in ROLES
                or not isinstance(account.get("enabled"), bool)
                or not isinstance(account.get("name"), str) or not 1 <= len(account["name"].strip()) <= 100
                or not isinstance(account.get("revision"), str) or not account["revision"]):
            raise ValueError("账户记录格式无效")
        _password_parts(account.get("password_hash"))
        if "password" in account:
            raise ValueError("账户配置禁止保存明文密码")
    return payload


def _fingerprint(account: dict) -> str:
    return hashlib.sha256(json.dumps(account, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authorize(role: str, path: str, method: str) -> bool:
    """Conservative route permissions; identity always comes from resolve()."""
    if role not in ROLES:
        return False
    method = method.upper()
    if role == "admin":
        return True
    if method in ("GET", "HEAD", "OPTIONS"):
        return True
    if method != "POST":
        return False
    if path == "/api/auth/logout":
        return True
    if path in ("/api/check", "/api/evidence/jev") or re.fullmatch(r"/api/runs/[^/]+/(explain|orchestrate)", path):
        return role in ("operator", "reviewer")
    if re.fullmatch(r"/api/runs/[^/]+/review", path):
        return role == "reviewer"
    return role == "operator" and path in {
        "/api/check", "/api/documents", "/api/candidates", "/api/evidence/jev",
        "/api/ledger/import", "/api/workspace/import", "/api/ledger/bundle", "/api/ledger-bundles",
    }


class AccessController:
    def __init__(self, auth_file: Path, session_database: Path, secure_cookie: bool = False):
        self.auth_file = Path(auth_file).resolve()
        self.session_database = Path(session_database).resolve()
        self.secure_cookie = bool(secure_cookie)
        self.enabled = True
        self._accounts()  # Invalid or missing configuration fails closed at startup.
        self.session_database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS access_sessions (
                    token_hash TEXT PRIMARY KEY, username TEXT NOT NULL,
                    account_fingerprint TEXT NOT NULL, csrf_token TEXT NOT NULL,
                    created_at REAL NOT NULL, expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS access_login_failures (
                    client_hash TEXT PRIMARY KEY, count INTEGER NOT NULL,
                    window_started REAL NOT NULL
                );
            """)
        # Unknown and disabled usernames perform the same password derivation.
        self._dummy_hash = hash_password(secrets.token_urlsafe(32))

    def _accounts(self):
        try:
            return read_accounts(self.auth_file)["accounts"]
        except (ValueError, TypeError, RecursionError) as error:
            raise AccessError("账户配置不可用", 503) from error

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.session_database, timeout=15)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _public_session(account: dict, csrf_token: str, expires_at: float, username: str):
        return {"csrf_token": csrf_token, "actor": {"name": account["name"], "role": account["role"], "username": username},
                "expires_at": datetime.fromtimestamp(expires_at, timezone.utc).isoformat()}

    def login(self, username: str, password: str, client_key: str) -> dict:
        if not isinstance(client_key, str) or not client_key or len(client_key) > 300:
            raise AccessError("登录来源无效", 400)
        if not isinstance(username, str) or not isinstance(password, str):
            raise AccessError("用户名或密码无效")
        client_hash = _hash_token(client_key)
        now = time.time()
        # Serialize attempts so concurrent requests cannot bypass the failure cap.
        with self._connect() as connection:
            connection.execute("DELETE FROM access_sessions WHERE expires_at<=?", (now,))
            connection.execute("DELETE FROM access_login_failures WHERE window_started<=?", (now - LOGIN_WINDOW_SECONDS,))
            failure = connection.execute("SELECT count FROM access_login_failures WHERE client_hash=?", (client_hash,)).fetchone()
            if failure and failure["count"] >= LOGIN_FAILURE_LIMIT:
                raise AccessError("登录失败次数过多，请稍后重试", 429)
            account = self._accounts().get(username) if len(username) <= 80 else None
            encoded = account["password_hash"] if account and account["enabled"] else self._dummy_hash
            valid = verify_password(password, encoded) and account is not None and account["enabled"]
            if not valid:
                connection.execute("""INSERT INTO access_login_failures VALUES(?,1,?)
                    ON CONFLICT(client_hash) DO UPDATE SET count=count+1""", (client_hash, now))
                # Commit the counter before reporting failure; raising inside rolls back.
                connection.commit()
                raise AccessError("用户名或密码无效")
            session_token = secrets.token_urlsafe(32)
            csrf_token = secrets.token_urlsafe(32)
            expires_at = now + SESSION_TTL_SECONDS
            connection.execute("DELETE FROM access_login_failures WHERE client_hash=?", (client_hash,))
            connection.execute("INSERT INTO access_sessions VALUES(?,?,?,?,?,?)", (
                _hash_token(session_token), username, _fingerprint(account), csrf_token, now, expires_at))
        return {"session_token": session_token, **self._public_session(account, csrf_token, expires_at, username)}

    def resolve(self, session_token: str) -> dict:
        if not isinstance(session_token, str) or not 20 <= len(session_token) <= 200:
            raise AccessError("请登录后继续")
        token_hash = _hash_token(session_token)
        now = time.time()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM access_sessions WHERE token_hash=?", (token_hash,)).fetchone()
            account = self._accounts().get(row["username"]) if row else None
            if (not row or row["expires_at"] <= now or not account or not account["enabled"]
                    or not hmac.compare_digest(row["account_fingerprint"], _fingerprint(account))):
                connection.execute("DELETE FROM access_sessions WHERE token_hash=?", (token_hash,))
                connection.commit()
                raise AccessError("会话已失效，请重新登录")
            return self._public_session(account, row["csrf_token"], row["expires_at"], row["username"])

    def logout(self, session_token: str) -> None:
        if not isinstance(session_token, str) or len(session_token) > 200:
            return
        with self._connect() as connection:
            connection.execute("DELETE FROM access_sessions WHERE token_hash=?", (_hash_token(session_token),))


@contextmanager
def _account_file_lock(auth_file: Path):
    """Serialize local management processes; never read half-written accounts."""
    lock_file = auth_file.with_name(auth_file.name + ".lock")
    with lock_file.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        acquired = False
        deadline = time.monotonic() + 15
        try:
            while not acquired:
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except (BlockingIOError, OSError):
                    if time.monotonic() >= deadline:
                        raise ValueError("账户配置正在修改，请稍后重试")
                    time.sleep(0.05)
            yield
        finally:
            if acquired:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def update_account(auth_file: Path, username: str, *, name: str | None = None, role: str | None = None,
                   password: str | None = None, enabled: bool | None = None, create: bool = False) -> dict:
    """Atomic local account update; fresh revision revokes old sessions."""
    auth_file = Path(auth_file).resolve()
    validate_username(username)
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    with _account_file_lock(auth_file):
        return _update_account_locked(auth_file, username, name=name, role=role,
                                      password=password, enabled=enabled, create=create)


def _update_account_locked(auth_file: Path, username: str, *, name: str | None = None, role: str | None = None,
                   password: str | None = None, enabled: bool | None = None, create: bool = False) -> dict:
    """Atomic local account update; fresh revision revokes old sessions."""
    auth_file = Path(auth_file).resolve()
    validate_username(username)
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    payload = read_accounts(auth_file) if auth_file.exists() else {"schema": SCHEMA, "accounts": {}}
    exists = username in payload["accounts"]
    if create and exists:
        raise ValueError("账户已存在")
    if not create and not exists:
        raise ValueError("账户不存在")
    if create and password is None:
        raise ValueError("新增账户需要密码")
    account = dict(payload["accounts"].get(username, {"name": username, "role": "viewer", "enabled": True}))
    if name is not None:
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError("显示名称须为 1 至 100 个字符")
        account["name"] = name.strip()
    if role is not None:
        if role not in ROLES:
            raise ValueError("账户角色无效")
        account["role"] = role
    if password is not None:
        account["password_hash"] = hash_password(password)
    if enabled is not None:
        if not isinstance(enabled, bool):
            raise ValueError("enabled 必须为布尔值")
        account["enabled"] = enabled
    account["revision"] = secrets.token_hex(16)
    payload["accounts"][username] = account
    temporary = auth_file.with_name(auth_file.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            temporary.chmod(0o600)
        os.replace(temporary, auth_file)
    finally:
        temporary.unlink(missing_ok=True)
    return {"username": username, "name": account["name"], "role": account["role"], "enabled": account["enabled"]}
