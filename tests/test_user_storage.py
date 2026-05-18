from pathlib import Path

from f2.utils.file.nickname_sanitize import sanitize_nickname
from f2.utils.file.user_storage import _create_directory_link, ensure_user_storage


def test_sanitize_nickname_special_chars_and_fallback():
    safe_name = sanitize_nickname("A /B:*?<name>", "douyin", "1001")
    assert "/" not in safe_name
    assert ":" not in safe_name
    assert "*" not in safe_name

    fallback_name = sanitize_nickname("   ", "douyin", "1001")
    assert fallback_name == "douyin_1001"


def test_ensure_user_storage_creates_uid_dir_and_suffix_link(tmp_path: Path):
    kwargs = {"path": str(tmp_path), "mode": "post"}
    mode_path = tmp_path / "douyin" / "post"
    target_uid_1 = mode_path / "_users" / "uid_1"
    target_uid_2 = mode_path / "_users" / "uid_2"
    target_uid_1.mkdir(parents=True)
    target_uid_2.mkdir(parents=True)

    # 先占用昵称链接名称，制造同名冲突。
    (mode_path / "same_name").symlink_to(target_uid_1, target_is_directory=True)

    real_path = ensure_user_storage(
        kwargs=kwargs,
        platform="douyin",
        user_unique_id="uid_2",
        current_nickname="same_name",
    )

    assert real_path == target_uid_2.resolve()
    assert (mode_path / "same_name_1").is_symlink()
    assert (mode_path / "same_name_1").resolve() == target_uid_2.resolve()


def test_legacy_folder_migration_with_conflict_suffix(tmp_path: Path):
    kwargs = {"path": str(tmp_path), "mode": "post"}
    mode_path = tmp_path / "douyin" / "post"
    legacy_path = mode_path / "old_nickname"
    legacy_path.mkdir(parents=True)

    (legacy_path / "same.txt").write_text("legacy", encoding="utf-8")
    (legacy_path / "other.txt").write_text("other", encoding="utf-8")

    real_path = mode_path / "_users" / "uid_2"
    real_path.mkdir(parents=True)
    (real_path / "same.txt").write_text("current", encoding="utf-8")

    resolved_path = ensure_user_storage(
        kwargs=kwargs,
        platform="douyin",
        user_unique_id="uid_2",
        current_nickname="new_nickname",
        legacy_nicknames=["old_nickname"],
    )

    assert resolved_path == real_path.resolve()
    assert legacy_path.is_symlink()
    assert legacy_path.resolve() == real_path.resolve()
    assert (real_path / "same.txt").read_text(encoding="utf-8") == "current"
    assert (real_path / "same_from_old_1.txt").read_text(encoding="utf-8") == "legacy"
    assert (real_path / "other.txt").read_text(encoding="utf-8") == "other"
    assert (mode_path / "new_nickname").is_symlink()


def test_windows_link_fallback_to_junction(monkeypatch, tmp_path: Path):
    link_path = tmp_path / "nickname"
    target_path = tmp_path / "target"
    target_path.mkdir()
    junction_called = {"value": False}

    def raise_symlink_error(self, target, target_is_directory=False):
        raise OSError("symlink unavailable")

    def fake_create_windows_junction(link, target):
        junction_called["value"] = (link, target) == (link_path, target_path)

    monkeypatch.setattr("f2.utils.file.user_storage.os.name", "nt")
    monkeypatch.setattr(Path, "symlink_to", raise_symlink_error)
    monkeypatch.setattr(
        "f2.utils.file.user_storage._create_windows_junction",
        fake_create_windows_junction,
    )

    _create_directory_link(link_path, target_path)

    assert junction_called["value"] is True
