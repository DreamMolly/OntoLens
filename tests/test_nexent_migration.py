from pathlib import Path

import pytest

from scripts import migrate_nexent_windows_data as migration


def test_tree_record_is_stable_and_covers_nested_files(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "b.txt").write_text("two", encoding="utf-8")
    (tmp_path / "nested" / "a.txt").write_text("one", encoding="utf-8")
    first = migration.tree_record(tmp_path)
    second = migration.tree_record(tmp_path)
    assert first == second
    assert first["files"] == 2
    assert first["bytes"] == 6
    assert first["directories"] == 1
    assert first["symlinks"] == 0


def test_windows_path_normalizes_slashes_and_case():
    assert migration.windows_path("F:/Projects/2026ICT/data") == migration.windows_path("f:\\Projects\\2026ICT\\data")


def test_preflight_rejects_existing_target(tmp_path, monkeypatch):
    target = tmp_path / ".runtime" / "nexent-desktop-data"
    target.parent.mkdir()
    target.mkdir()
    monkeypatch.setattr(migration, "ROOT", tmp_path)
    monkeypatch.setattr(migration, "TARGET", target)
    monkeypatch.setattr(migration, "BACKUP", tmp_path / "backup.json")
    with pytest.raises(ValueError, match="already exists"):
        migration.preflight()


def test_preflight_rejects_target_outside_runtime(tmp_path, monkeypatch):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    backup = tmp_path / "backup.json"
    backup.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(migration, "ROOT", tmp_path)
    monkeypatch.setattr(migration, "TARGET", tmp_path / "outside")
    monkeypatch.setattr(migration, "BACKUP", backup)
    with pytest.raises(ValueError, match="inside .runtime"):
        migration.preflight()
