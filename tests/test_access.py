"""Local account/session contracts; all credentials are disposable test fixtures."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

import ontolens.access as access
from ontolens.access import AccessController, AccessError, authorize, hash_password, read_accounts, update_account, verify_password

PASSWORD = "TEST-FIXTURE-only-密码-482"
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def configured(tmp_path):
    auth_file = tmp_path / "accounts.json"
    update_account(auth_file, "测试账户", name="测试操作员", role="operator", password=PASSWORD, create=True)
    database = tmp_path / "sessions.sqlite3"
    controller = AccessController(auth_file, database)
    return controller, auth_file, database


def test_password_hash_is_salted_and_no_plaintext_stored(configured):
    controller, auth_file, _ = configured
    account = read_accounts(auth_file)["accounts"]["测试账户"]
    assert PASSWORD not in auth_file.read_text(encoding="utf-8")
    assert account["password_hash"] != hash_password(PASSWORD)
    assert verify_password(PASSWORD, account["password_hash"])
    assert not verify_password("wrong", account["password_hash"])
    assert not verify_password(PASSWORD, "unknown$hash")


def test_session_identity_csrf_hash_only_and_no_sliding_expiry(configured, monkeypatch):
    controller, _, database = configured
    now = [1_800_000_000.0]
    monkeypatch.setattr(access, "time", SimpleNamespace(time=lambda: now[0]))
    session = controller.login("测试账户", PASSWORD, "test-client")
    assert session["actor"] == {"name": "测试操作员", "role": "operator", "username": "测试账户"}
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT token_hash,expires_at FROM access_sessions").fetchone()
    assert row[0] == hashlib.sha256(session["session_token"].encode()).hexdigest()
    assert row[1] == now[0] + 8 * 60 * 60
    assert session["session_token"].encode() not in database.read_bytes()
    now[0] += 60
    resolved = controller.resolve(session["session_token"])
    assert "session_token" not in resolved
    assert resolved["expires_at"] == session["expires_at"]
    assert resolved["csrf_token"] == session["csrf_token"]
    assert session["session_token"] != session["csrf_token"]


def test_returned_or_forged_identity_cannot_modify_trusted_actor(configured):
    controller, _, _ = configured
    session = controller.login("测试账户", PASSWORD, "test-client")
    session["actor"].update(name="冒名管理员", role="admin")
    resolved = controller.resolve(session["session_token"])
    assert resolved["actor"] == {"name": "测试操作员", "role": "operator", "username": "测试账户"}
    assert not authorize(resolved["actor"]["role"], "/api/candidates/id/publish", "POST")
    with pytest.raises(AccessError) as error:
        controller.resolve("{" + json.dumps({"actor": {"role": "admin"}}) + "}")
    assert error.value.status == 401


def test_absolute_expiry_revokes_and_removes_session(configured, monkeypatch):
    controller, _, database = configured
    now = [1_800_000_000.0]
    monkeypatch.setattr(access, "time", SimpleNamespace(time=lambda: now[0]))
    session = controller.login("测试账户", PASSWORD, "test-client")
    now[0] += access.SESSION_TTL_SECONDS
    with pytest.raises(AccessError) as error:
        controller.resolve(session["session_token"])
    assert error.value.status == 401
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM access_sessions").fetchone()[0] == 0


def test_logout_revokes_only_target_session_and_is_idempotent(configured):
    controller, _, _ = configured
    first = controller.login("测试账户", PASSWORD, "first")
    second = controller.login("测试账户", PASSWORD, "second")
    controller.logout(first["session_token"])
    controller.logout(first["session_token"])
    controller.logout(None)
    with pytest.raises(AccessError):
        controller.resolve(first["session_token"])
    assert controller.resolve(second["session_token"])["actor"]["role"] == "operator"


@pytest.mark.parametrize("change", ["password", "disable", "role", "name", "disable_enable"])
def test_account_changes_invalidate_existing_sessions(configured, change):
    controller, auth_file, _ = configured
    session = controller.login("测试账户", PASSWORD, "first")
    if change == "password": update_account(auth_file, "测试账户", password=PASSWORD + "-new")
    if change == "disable": update_account(auth_file, "测试账户", enabled=False)
    if change == "role": update_account(auth_file, "测试账户", role="viewer")
    if change == "name": update_account(auth_file, "测试账户", name="新名称")
    if change == "disable_enable":
        update_account(auth_file, "测试账户", enabled=False)
        update_account(auth_file, "测试账户", enabled=True)
    with pytest.raises(AccessError) as error:
        controller.resolve(session["session_token"])
    assert error.value.status == 401


def test_other_account_update_does_not_revoke_current_identity(configured):
    controller, auth_file, _ = configured
    session = controller.login("测试账户", PASSWORD, "first")
    update_account(auth_file, "another", role="viewer", password=PASSWORD, create=True)
    assert controller.resolve(session["session_token"])["actor"]["name"] == "测试操作员"


def test_failed_login_response_does_not_disclose_account_existence(configured):
    controller, auth_file, _ = configured
    messages = []
    for username, password in [("测试账户", "wrong"), ("does-not-exist", PASSWORD)]:
        with pytest.raises(AccessError) as error:
            controller.login(username, password, "test-client")
        messages.append((error.value.status, str(error.value)))
    update_account(auth_file, "测试账户", enabled=False)
    with pytest.raises(AccessError) as error:
        controller.login("测试账户", PASSWORD, "test-client")
    messages.append((error.value.status, str(error.value)))
    assert len(set(messages)) == 1


def test_persistent_rate_limit_covers_changed_usernames_and_resets_after_window(configured, monkeypatch):
    controller, auth_file, database = configured
    now = [1_800_000_000.0]
    monkeypatch.setattr(access, "time", SimpleNamespace(time=lambda: now[0]))
    for attempt in range(access.LOGIN_FAILURE_LIMIT):
        with pytest.raises(AccessError) as error:
            controller.login("unknown-" + str(attempt), "wrong", "same-client")
        assert error.value.status == 401
    restarted = AccessController(auth_file, database)
    with pytest.raises(AccessError) as error:
        restarted.login("测试账户", PASSWORD, "same-client")
    assert error.value.status == 429
    assert restarted.login("测试账户", PASSWORD, "different-client")["actor"]["role"] == "operator"
    now[0] += access.LOGIN_WINDOW_SECONDS
    assert restarted.login("测试账户", PASSWORD, "same-client")["actor"]["role"] == "operator"


def test_successful_login_clears_previous_failures(configured):
    controller, _, database = configured
    with pytest.raises(AccessError): controller.login("测试账户", "wrong", "same-client")
    controller.login("测试账户", PASSWORD, "same-client")
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM access_login_failures").fetchone()[0] == 0


def test_concurrent_failed_attempts_cannot_bypass_rate_cap(configured):
    controller, _, database = configured
    def attempt(index):
        try:
            controller.login("unknown-" + str(index), "wrong", "same-client")
        except AccessError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(attempt, range(10)))
    assert statuses.count(401) == access.LOGIN_FAILURE_LIMIT
    assert statuses.count(429) == 10 - access.LOGIN_FAILURE_LIMIT
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count FROM access_login_failures").fetchone()[0] == access.LOGIN_FAILURE_LIMIT


def test_concurrent_account_changes_preserve_both_updates(configured):
    _, auth_file, _ = configured
    def create(username):
        return update_account(auth_file, username, role="viewer", password=PASSWORD, create=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(create, ("concurrent-a", "concurrent-b")))
    assert set(read_accounts(auth_file)["accounts"]) == {"测试账户", "concurrent-a", "concurrent-b"}


@pytest.mark.parametrize("role,path,method,expected", [
    ("viewer", "/api/catalog", "GET", True), ("viewer", "/api/check", "POST", False),
    ("viewer", "/api/auth/logout", "POST", True), ("operator", "/api/check", "POST", True),
    ("operator", "/api/ledger/import", "POST", True), ("operator", "/api/runs/id/review", "POST", False),
    ("reviewer", "/api/runs/id/review", "POST", True), ("reviewer", "/api/check", "POST", True),
    ("reviewer", "/api/evidence/jev", "POST", True), ("reviewer", "/api/runs/id/orchestrate", "POST", True),
    ("operator", "/api/runs/id/orchestrate", "POST", True),
    ("reviewer", "/api/runs/id/explain", "POST", True), ("operator", "/api/candidates/id/publish", "POST", False),
    ("operator", "/api/versions/id/rollback", "POST", False), ("admin", "/api/candidates/id/publish", "POST", True),
    ("admin", "/api/versions/id/rollback", "POST", True), ("operator", "/api/unknown", "POST", False),
    ("operator", "/api/documents", "DELETE", False), ("invented", "/api/catalog", "GET", False),
])
def test_role_permission_matrix(role, path, method, expected):
    assert authorize(role, path, method) is expected


def test_invalid_config_fails_closed_at_startup_and_during_session(configured, tmp_path):
    controller, auth_file, _ = configured
    session = controller.login("测试账户", PASSWORD, "first")
    auth_file.write_text('{"schema":"wrong"}', encoding="utf-8")
    with pytest.raises(AccessError) as error:
        controller.resolve(session["session_token"])
    assert error.value.status == 503
    with pytest.raises(AccessError): AccessController(auth_file, tmp_path / "other.sqlite3")
    with pytest.raises(AccessError): AccessController(tmp_path / "missing.json", tmp_path / "missing.sqlite3")


@pytest.mark.parametrize("username", ["", " padded", "has space", "path/name", "a\\b", "control\x00", "a" * 81])
def test_invalid_account_names_and_short_password_rejected(tmp_path, username):
    with pytest.raises(ValueError): update_account(tmp_path / "accounts.json", username, password=PASSWORD, create=True)
    with pytest.raises(ValueError): hash_password("short")


def test_management_cli_creates_updates_and_lists_without_secrets(tmp_path):
    auth_file = tmp_path / "cli-accounts.json"
    environment = dict(os.environ, ONTOLENS_ACCOUNT_PASSWORD=PASSWORD, PYTHONIOENCODING="utf-8")
    prefix = [sys.executable, str(ROOT / "scripts/manage_access.py"), "--auth-file", str(auth_file)]
    for arguments in (["add", "local-admin", "--role", "admin"], ["set-role", "local-admin", "viewer"],
                      ["disable", "local-admin"], ["enable", "local-admin"], ["set-password", "local-admin"], ["list"]):
        result = subprocess.run(prefix + arguments, env=environment, capture_output=True, text=True, encoding="utf-8", check=False)
        assert result.returncode == 0, result.stderr
        assert PASSWORD not in result.stdout + result.stderr and "password_hash" not in result.stdout
    account = read_accounts(auth_file)["accounts"]["local-admin"]
    assert account["role"] == "viewer" and account["enabled"]


def test_bad_hash_cost_or_plaintext_account_rejected(configured):
    _, auth_file, _ = configured
    payload = json.loads(auth_file.read_text(encoding="utf-8"))
    account = payload["accounts"]["测试账户"]
    account["password"] = "must-never-be-stored"
    auth_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError): read_accounts(auth_file)
    del account["password"]
    account["password_hash"] = "pbkdf2_sha256$99999999999$" + "a" * 32 + "$" + "b" * 64
    auth_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError): read_accounts(auth_file)
