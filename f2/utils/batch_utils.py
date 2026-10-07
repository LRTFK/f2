# path: f2/utils/batch_utils.py

"""批量运行：从文本文件读取链接列表，按指定顺序逐条执行"""

import random
import traceback
from pathlib import Path
from typing import Callable, List

import click

from f2.i18n.translator import _
from f2.log.logger import logger, trace_logger

# --order 的取值
ORDER_CHOICES = ["asc", "desc", "random"]


def read_urls_from_file(file_path: str) -> List[str]:
    """
    读取文本文件里的链接，每行一条，忽略空行与以 # 开头的注释行
    (Read one link per line, skipping blank lines and # comment lines)

    Args:
        file_path (str): 文件路径 (Path of the file)

    Returns:
        List[str]: 链接列表，可能为空 (List of links, possibly empty)
    """

    path = Path(file_path)
    if not path.is_file():
        raise click.ClickException(_("链接文件不存在：{0}").format(file_path))

    # 文本文件在 Windows 上可能是 GBK，先按 UTF-8（含 BOM）读，失败再退回 GBK
    for encoding in ("utf-8-sig", "gbk"):
        try:
            lines = path.read_text(encoding=encoding).splitlines()
            break
        except UnicodeDecodeError:
            continue
    else:
        raise click.ClickException(_("无法识别链接文件的编码：{0}").format(file_path))

    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]


def apply_order(urls: List[str], order: str) -> List[str]:
    """
    按指定顺序排列链接 (Arrange the links in the requested order)

    Args:
        urls (List[str]): 链接列表 (List of links)
        order (str): asc 正序、desc 倒序、random 随机 (See ORDER_CHOICES)

    Returns:
        List[str]: 排列后的新列表 (A new, reordered list)
    """

    if order == "desc":
        return list(reversed(urls))
    if order == "random":
        shuffled = list(urls)
        random.shuffle(shuffled)
        return shuffled
    return list(urls)


def run_batch_urls(
    ctx: click.Context,
    urls: List[str],
    order: str,
    run_one: Callable[[str], None],
) -> None:
    """
    逐条执行链接，某一条失败不中断后续，最后按整体结果设置退出码
    (Run every link in turn, keep going after a failure, then set the exit code
    from the overall result)

    Args:
        ctx (click.Context): click的上下文对象 (Click's context object)
        urls (List[str]): 链接列表 (List of links)
        order (str): 执行顺序，见 ORDER_CHOICES (Execution order)
        run_one (Callable[[str], None]): 处理单条链接的函数，抛异常表示该条失败
            (Handler for a single link; raising means this one failed)
    """

    ordered = apply_order(urls, order)
    if not ordered:
        logger.error(_("链接文件里没有可用的链接"))
        ctx.exit(1)

    total = len(ordered)
    failed: List[str] = []
    logger.info(_("[Batch] 共 {0} 条链接，执行顺序：{1}").format(total, order))

    for index, url in enumerate(ordered, 1):
        logger.info(_("[Batch] {0}/{1} - {2}").format(index, total, url))
        try:
            run_one(url)
        except click.exceptions.Exit as e:
            # 被调用的命令自己以非零码结束（配置缺失、下载失败等），只影响这一条
            if e.exit_code:
                failed.append(url)
        except click.Abort:
            failed.append(url)
        except Exception:
            trace_logger.error(traceback.format_exc())
            logger.error(_("[Batch] 处理失败：{0}").format(url))
            failed.append(url)

    if failed:
        logger.error(
            _("[Batch] 完成：成功 {0}/{1}，失败 {2} 条").format(
                total - len(failed), total, len(failed)
            )
        )
        ctx.exit(1)

    logger.info(_("[Batch] 完成：{0} 条全部成功").format(total))
