# path: f2/cli/batch_command.py

import importlib

import click

from f2.i18n.translator import _
from f2.utils.batch_utils import ORDER_CHOICES, read_urls_from_file, run_batch_urls

# 支持批量运行的应用，与 f2/apps/__apps__.py 里的应用名一致
BATCH_PLATFORMS = ["douyin", "twitter", "weibo"]


@click.command(
    name="batch",
    help=_("批量运行：从文本文件读取链接，逐个执行指定应用的下载流程"),
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--platform",
    "-P",
    type=click.Choice(BATCH_PLATFORMS),
    required=True,
    help=_("批量运行的应用：douyin、twitter、weibo"),
)
@click.option(
    "--batch",
    "-b",
    "batch_file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help=_("链接文件：每行一条链接，忽略空行与以 # 开头的注释行"),
)
@click.option(
    "--order",
    "-O",
    type=click.Choice(ORDER_CHOICES),
    default="asc",
    show_default=True,
    help=_("链接的执行顺序：asc 正序、desc 倒序、random 随机"),
)
@click.option(
    "--config",
    "-c",
    type=click.Path(file_okay=True, dir_okay=False, readable=True),
    help=_("配置文件的路径，与各应用命令的 -c 相同，模式、下载路径等参数都从这里读取"),
)
@click.option(
    "--max-counts",
    "-o",
    type=int,
    help=_("每条链接最多下载的作品数，0 表示不限制；不指定时用配置文件里的值"),
)
@click.pass_context
def batch_command(
    ctx: click.Context,
    platform: str,
    batch_file: str,
    order: str,
    config: str,
    max_counts: int,
) -> None:
    """
    逐个链接调用对应应用的命令 (Run the app's command for every link)

    每个链接都走一遍该应用完整的下载流程（配置合并、校验、下载），
    因此参数与退出码的行为和单独运行 `f2 <应用> -u <链接>` 完全一致。

    Args:
        ctx (click.Context): click的上下文对象 (Click's context object)
        platform (str): 应用名 (Name of the app)
        batch_file (str): 链接文件路径 (Path of the link file)
        order (str): 执行顺序，见 ORDER_CHOICES (Execution order)
        config (str): 自定义配置文件路径 (Path of the custom config file)
        max_counts (int): 每条链接最多下载的作品数 (Works per link, None for the config value)
    """

    # 动态导入应用命令，避免 CLI 启动时就加载各应用的依赖
    app_command = getattr(importlib.import_module(f"f2.apps.{platform}.cli"), platform)

    run_batch_urls(
        ctx,
        read_urls_from_file(batch_file),
        order,
        lambda url: ctx.invoke(
            app_command, url=url, config=config, max_counts=max_counts
        ),
    )
