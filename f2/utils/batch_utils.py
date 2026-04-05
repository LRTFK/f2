# path: f2/utils/batch_utils.py

import csv
import typing
from pathlib import Path

from f2.i18n.translator import _
from f2.log.logger import logger


def read_urls_from_file(file_path: str) -> typing.List[dict]:
    """
    从文件中读取 URL 列表

    支持格式：
    - .txt: 每行一个 URL，支持 # 注释和空行，返回 {"url": "xxx", "note": ""}
    - .csv: 必须包含 url 列（大小写不敏感），其他列合并为 note
    - .xlsx/.xls: 必须包含 url 列（大小写不敏感），其他列合并为 note

    Args:
        file_path: URL 文件路径

    Returns:
        [{"url": "xxx", "note": "备注信息"}, ...]

    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无权限读取文件
        ValueError: 文件为空或没有有效的 URL 或 CSV/Excel 缺少 url 列
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    # 检查文件是否存在
    if not path.exists():
        raise FileNotFoundError(_("URL 文件不存在：{0}").format(file_path))

    # 检查是否有读取权限
    if not path.is_file():
        raise PermissionError(_("路径不是文件：{0}").format(file_path))

    if suffix == ".txt":
        return _read_txt_file(path)
    elif suffix == ".csv":
        return _read_csv_file(path)
    elif suffix in (".xlsx", ".xls"):
        return _read_excel_file(path)
    else:
        raise ValueError(_("不支持的文件格式：{0}，仅支持 .txt, .csv, .xlsx, .xls").format(suffix))


def _read_txt_file(path: Path) -> typing.List[dict]:
    """读取 TXT 文件，每行一个 URL"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except PermissionError:
        raise PermissionError(_("无权限读取文件：{0}").format(path))
    except UnicodeDecodeError:
        # 尝试使用其他编码
        try:
            with open(path, "r", encoding="gbk") as f:
                content = f.read()
        except Exception:
            raise ValueError(_("文件编码不支持，请使用 UTF-8 或 GBK 编码"))

    urls = []
    lines = content.splitlines()

    for line in lines:
        line = line.strip()
        # 跳过空行和注释行
        if not line or line.startswith("#"):
            continue
        urls.append({"url": line, "note": ""})

    if not urls:
        raise ValueError(_("URL 文件为空或没有有效的 URL"))

    logger.debug(_("从文件读取了 {0} 个 URL: {1}").format(len(urls), path))
    return urls


def _read_csv_file(path: Path) -> typing.List[dict]:
    """读取 CSV 文件，必须包含 url 列"""
    # 尝试不同的编码读取文件
    content = None
    used_encoding = "utf-8"

    for encoding in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            used_encoding = encoding
            break
        except (PermissionError, UnicodeDecodeError):
            continue

    if content is None:
        if not path.is_file():
            raise PermissionError(_("无权限读取文件：{0}").format(path))
        else:
            raise ValueError(_("文件编码不支持，请使用 UTF-8 或 GBK 编码"))

    try:
        # 使用成功读取时的编码重新打开文件供 csv 模块读取
        with open(path, "r", encoding=used_encoding) as f:
            # 过滤掉注释行（以 # 开头的行）
            lines = [line for line in f if not line.strip().startswith("#")]

        # 使用过滤后的内容创建 CSV reader
        import io
        with io.StringIO("".join(lines)) as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(_("CSV 文件为空或没有表头"))

            # 查找 url 列（大小写不敏感）
            url_col = None
            for col in reader.fieldnames:
                if col and col.strip().lower() == "url":
                    url_col = col
                    break

            if url_col is None:
                raise ValueError(
                    _("CSV 文件缺少必需的 'url' 列。当前列：{0}").format(reader.fieldnames)
                )

            urls = []
            for row in reader:
                url_value = row.get(url_col, "").strip()
                if url_value:
                    # 合并其他列为 note
                    note_parts = []
                    for col, value in row.items():
                        if col != url_col and value and str(value).strip():
                            note_parts.append(str(value).strip())
                    note = "，".join(note_parts)
                    urls.append({"url": url_value, "note": note})

            if not urls:
                raise ValueError(_("CSV 文件没有有效的 URL"))

            logger.debug(_("从 CSV 文件读取了 {0} 个 URL: {1}").format(len(urls), path))
            return urls

    except csv.Error as e:
        raise ValueError(_("CSV 文件解析失败：{0}").format(str(e)))


def _read_excel_file(path: Path) -> typing.List[dict]:
    """读取 Excel 文件，必须包含 url 列"""
    try:
        # 延迟导入，避免不必要的依赖
        import openpyxl
    except ImportError:
        raise ImportError(
            _("读取 Excel 文件需要安装 openpyxl 依赖：pip install 'f2[batch]'")
        )

    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active

        # 读取第一行作为表头
        headers = []
        for cell in ws[1]:
            if cell and cell.value:
                headers.append(str(cell.value))
            else:
                headers.append("")

        if not headers:
            raise ValueError(_("Excel 文件为空或没有表头"))

        # 查找 url 列（大小写不敏感）
        url_col_idx = None
        for idx, col in enumerate(headers):
            if col and col.strip().lower() == "url":
                url_col_idx = idx
                break

        if url_col_idx is None:
            wb.close()
            raise ValueError(
                _("Excel 文件缺少必需的 'url' 列。当前列：{0}").format(headers)
            )

        urls = []
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            # 跳过全空行
            if all(cell is None or str(cell).strip() == "" for cell in row):
                continue

            url_value = row[url_col_idx] if url_col_idx < len(row) else None
            if url_value and str(url_value).strip():
                url_value = str(url_value).strip()
                # 合并其他列为 note
                note_parts = []
                for idx, cell in enumerate(row):
                    if idx != url_col_idx and cell and str(cell).strip():
                        note_parts.append(str(cell).strip())
                note = "，".join(note_parts)
                urls.append({"url": url_value, "note": note})

        wb.close()

        if not urls:
            raise ValueError(_("Excel 文件没有有效的 URL"))

        logger.debug(_("从 Excel 文件读取了 {0} 个 URL: {1}").format(len(urls), path))
        return urls

    except Exception as e:
        if isinstance(e, (ValueError, ImportError)):
            raise
        raise ValueError(_("Excel 文件读取失败：{0}").format(str(e)))


def apply_order_to_urls(
    urls: typing.List[dict], order: str
) -> typing.List[dict]:
    """
    根据指定的顺序处理 URL 列表

    Args:
        urls: URL 列表，每个元素为 {"url": "xxx", "note": "备注"}
        order: 顺序类型
            - "asc" / "forward": 顺序（默认）
            - "desc" / "reverse": 倒序
            - "random" / "shuffle": 随机

    Returns:
        处理后的 URL 列表
    """
    import random

    if order in ("asc", "forward"):
        # 顺序，保持原样
        return urls
    elif order in ("desc", "reverse"):
        # 倒序
        return list(reversed(urls))
    elif order in ("random", "shuffle"):
        # 随机
        result = urls.copy()
        random.shuffle(result)
        return result
    else:
        # 未知值，返回原列表
        return urls
