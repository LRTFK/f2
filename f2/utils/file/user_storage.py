import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional, Union

from f2.utils.file.nickname_sanitize import sanitize_nickname


def _ensure_kwargs(kwargs: dict) -> None:
    if not isinstance(kwargs, dict):
        raise TypeError("kwargs 参数必须是字典")


def _build_platform_mode_path(kwargs: dict, platform: str) -> Path:
    base_path = Path(kwargs.get("path", "Download"))
    mode = kwargs.get("mode", "PLEASE_SETUP_MODE")
    return (base_path / platform / mode).resolve()


def _build_real_user_path(platform_mode_path: Path, user_unique_id: Union[str, int]) -> Path:
    real_user_path = (platform_mode_path / "_users" / str(user_unique_id)).resolve()
    real_user_path.mkdir(parents=True, exist_ok=True)
    return real_user_path


def _resolve_collision_path(parent: Path, name: str, suffix_tag: str) -> Path:
    current = Path(name)
    stem = current.stem if current.suffix else current.name
    suffix = current.suffix if current.suffix else ""

    index = 1
    while True:
        candidate = parent / f"{stem}{suffix_tag}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _move_item_to_target(source_path: Path, target_root: Path) -> None:
    target_path = target_root / source_path.name

    if not target_path.exists():
        shutil.move(str(source_path), str(target_path))
        return

    if source_path.is_dir() and target_path.is_dir():
        for child in list(source_path.iterdir()):
            _move_item_to_target(child, target_path)
        if source_path.exists():
            source_path.rmdir()
        return

    conflict_target = _resolve_collision_path(target_root, source_path.name, "_from_old")
    shutil.move(str(source_path), str(conflict_target))


def migrate_legacy_user_directory(legacy_path: Path, target_path: Path) -> None:
    """
    迁移旧昵称目录数据到唯一ID目录，冲突文件追加 `_from_old_n` 后缀。
    """

    if not legacy_path.exists() or not legacy_path.is_dir():
        return

    for item in list(legacy_path.iterdir()):
        _move_item_to_target(item, target_path)

    if legacy_path.exists():
        legacy_path.rmdir()


def _create_windows_junction(link_path: Path, target_path: Path) -> None:
    junction_cmd = f'mklink /J "{link_path}" "{target_path}"'
    subprocess.run(
        ["cmd", "/c", junction_cmd],
        check=True,
        capture_output=True,
        text=True,
    )


def _create_directory_link(link_path: Path, target_path: Path) -> None:
    if os.name != "nt":
        link_path.symlink_to(target_path, target_is_directory=True)
        return

    try:
        link_path.symlink_to(target_path, target_is_directory=True)
    except OSError:
        _create_windows_junction(link_path, target_path)


def _path_points_to_target(path: Path, target_path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    try:
        return path.resolve() == target_path.resolve()
    except OSError:
        return False


def ensure_nickname_link(
    platform_mode_path: Path,
    nickname: Union[str, int, None],
    platform: str,
    user_unique_id: Union[str, int],
    target_path: Path,
) -> Path:
    safe_nickname = sanitize_nickname(nickname, platform, user_unique_id)

    index = 0
    while True:
        suffix = "" if index == 0 else f"_{index}"
        candidate = platform_mode_path / f"{safe_nickname}{suffix}"

        if _path_points_to_target(candidate, target_path):
            return candidate

        if candidate.exists() or candidate.is_symlink():
            index += 1
            continue

        _create_directory_link(candidate, target_path)
        return candidate


def _deduplicate_names(names: Iterable[Union[str, int, None]]) -> list[str]:
    result = []
    seen = set()
    for name in names:
        if name is None:
            continue
        value = str(name).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def ensure_user_storage(
    kwargs: dict,
    platform: str,
    user_unique_id: Union[str, int],
    current_nickname: Union[str, int, None],
    legacy_nicknames: Optional[Iterable[Union[str, int, None]]] = None,
) -> Path:
    """
    确保用户真实目录存在，并按昵称创建链接入口，同时兼容旧昵称目录迁移。
    """

    _ensure_kwargs(kwargs)
    platform_mode_path = _build_platform_mode_path(kwargs, platform)
    platform_mode_path.mkdir(parents=True, exist_ok=True)

    real_user_path = _build_real_user_path(platform_mode_path, user_unique_id)

    names_for_migration = _deduplicate_names(
        [*(legacy_nicknames or []), current_nickname]
    )

    for legacy_name in names_for_migration:
        if legacy_name == str(user_unique_id):
            continue
        legacy_path = (platform_mode_path / legacy_name).resolve()
        if legacy_path == real_user_path:
            continue
        if legacy_path.exists() and not legacy_path.is_symlink() and legacy_path.is_dir():
            migrate_legacy_user_directory(legacy_path, real_user_path)

    link_names = names_for_migration or [current_nickname]
    for link_name in link_names:
        ensure_nickname_link(
            platform_mode_path=platform_mode_path,
            nickname=link_name,
            platform=platform,
            user_unique_id=user_unique_id,
            target_path=real_user_path,
        )

    return real_user_path
