import re
from typing import Dict, Optional, Union

from f2.utils.file.name import split_filename

DEFAULT_OS_LIMIT = {
    "win32": 200,
    "cygwin": 200,
    "darwin": 200,
    "linux": 200,
}

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def _is_windows_reserved_name(name: str) -> bool:
    head = name.split(".", 1)[0].upper()
    return head in WINDOWS_RESERVED_NAMES


def sanitize_nickname(
    nickname: Union[str, int, None],
    platform: str,
    user_unique_id: Union[str, int],
    os_limit: Optional[Dict[str, int]] = None,
) -> str:
    """
    清洗昵称，生成适合跨平台目录名的字符串。
    """

    text = "" if nickname is None else str(nickname)
    text = text.strip()

    # 统一空白字符
    text = re.sub(r"\s+", "_", text)

    # Windows 非法字符和控制字符
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)

    # 避免以空格/点结尾，兼容 Windows
    text = text.strip(" ._")
    text = re.sub(r"_+", "_", text)

    if not text:
        text = f"{platform}_{user_unique_id}"

    if _is_windows_reserved_name(text):
        text = f"{text}_user"

    normalized = split_filename(text, os_limit or DEFAULT_OS_LIMIT)
    if _is_windows_reserved_name(normalized):
        normalized = f"{normalized}_user"

    return normalized
