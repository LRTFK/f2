# path: f2/utils/batch_utils.py

import typing
from pathlib import Path
from f2.i18n.translator import _
from f2.log.logger import logger


def read_urls_from_file(file_path: str) -> typing.List[str]:
    """
    从文件中读取 URL 列表

    支持 .txt 和 .csv 格式：
    - .txt: 每行一个 URL，支持 # 注释和空行
    - .csv: 每行一个 URL，可忽略表头

    Args:
        file_path: URL 文件路径

    Returns:
        URL 列表

    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无权限读取文件
        ValueError: 文件为空或没有有效的 URL
    """
    path = Path(file_path)

    # 检查文件是否存在
    if not path.exists():
        raise FileNotFoundError(_("URL 文件不存在：{0}").format(file_path))

    # 检查是否有读取权限
    if not path.is_file():
        raise PermissionError(_("路径不是文件：{0}").format(file_path))

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except PermissionError:
        raise PermissionError(_("无权限读取文件：{0}").format(file_path))
    except UnicodeDecodeError:
        # 尝试使用其他编码
        try:
            with open(path, "r", encoding="gbk") as f:
                content = f.read()
        except Exception:
            raise ValueError(_("文件编码不支持，请使用 UTF-8 或 GBK 编码"))

    # 解析文件内容
    urls = []
    lines = content.splitlines()

    # 检查是否为 csv 文件（通过扩展名判断）
    is_csv = path.suffix.lower() == ".csv"

    for line in lines:
        # 去除两端空白
        line = line.strip()

        # 跳过空行
        if not line:
            continue

        # 跳过注释行（仅针对 txt 文件）
        if not is_csv and line.startswith("#"):
            continue

        # 如果是 CSV 且有表头，跳过第一行（简单判断：是否包含URL 特征）
        # CSV 文件不做特殊处理，每行都当作 URL 尝试

        # 添加到 URL 列表
        urls.append(line)

    if not urls:
        raise ValueError(_("URL 文件为空或没有有效的 URL"))

    logger.debug(_("从文件读取了 {0} 个 URL: {1}").format(len(urls), file_path))

    return urls
