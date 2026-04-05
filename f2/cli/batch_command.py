# path: f2/cli/batch_command.py

import click
from typing import Optional

from f2.i18n.translator import _
from f2.utils.batch_runner import BatchRunner


@click.command(name="batch")
@click.option(
    "-P",
    "--platform",
    required=True,
    type=click.Choice(
        ["dy", "douyin", "wb", "weibo", "twitter", "x", "tiktok", "bark"],
        case_sensitive=False,
    ),
    help=_("平台标识 (dy/douyin, wb/weibo, twitter/x, tiktok, bark)"),
)
@click.option(
    "-b",
    "--batch",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    help=_("URL 文件路径，支持 .txt/.csv/.xlsx 格式"),
)
@click.option(
    "-c",
    "--config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True),
    help=_("配置文件路径"),
)
@click.option(
    "-O",
    "--order",
    type=click.Choice(["asc", "desc", "random"]),
    default="asc",
    help=_("URL 执行顺序：asc(正序), desc(倒序), random(随机)"),
)
@click.option(
    "-M",
    "--mode",
    type=str,
    help=_("下载模式，不同平台支持的模式不同"),
)
@click.option(
    "-u",
    "--url",
    type=str,
    help=_(
        "根据模式提供相应的链接（此参数会被 batch 文件中的 URL 覆盖，仅作为默认值）"
    ),
)
@click.option(
    "-p",
    "--path",
    type=str,
    help=_("作品保存位置，支持绝对与相对路径"),
)
@click.option(
    "-f",
    "--folderize",
    type=bool,
    help=_("是否将作品保存到单独的文件夹"),
)
@click.option(
    "-n",
    "--naming",
    type=str,
    help=_("全局作品文件命名方式"),
)
@click.option(
    "-k",
    "--cookie",
    type=str,
    help=_("登录后的 cookie"),
)
@click.option(
    "-e",
    "--timeout",
    type=int,
    default=1,
    help=_("网络请求超时时间，也用于控制每个 URL 之间的延时"),
)
@click.option(
    "-r",
    "--max_retries",
    type=int,
    help=_("网络请求超时重试数"),
)
@click.option(
    "-x",
    "--max-connections",
    type=int,
    help=_("网络请求并发连接数"),
)
@click.option(
    "-t",
    "--max-tasks",
    type=int,
    help=_("异步的任务数"),
)
@click.option(
    "-o",
    "--max-counts",
    type=int,
    help=_("最大作品下载数。0 表示无限制"),
)
@click.option(
    "-s",
    "--page-counts",
    type=int,
    help=_("从接口每页可获取作品数，不建议超过 20"),
)
@click.option(
    "-m",
    "--music",
    type=bool,
    help=_("是否保存视频原声"),
)
@click.option(
    "-v",
    "--cover",
    type=bool,
    help=_("是否保存视频封面"),
)
@click.option(
    "-d",
    "--desc",
    type=bool,
    help=_("是否保存视频文案"),
)
@click.option(
    "-i",
    "--interval",
    type=str,
    help=_("下载日期区间发布的作品，格式：YYYY-MM-DD|YYYY-MM-DD，'all' 为下载所有作品"),
)
@click.pass_context
def batch(
    ctx: click.Context,
    platform: str,
    batch: str,
    config: Optional[str],
    order: str,
    **kwargs,
):
    """
    批量运行子命令 - 从文件读取多个 URL 依次执行

    示例:
        f2 batch -P dy -b urls.txt -c dy.yaml --mode post
        f2 batch -P wb -b urls.csv --order desc
        f2 batch -P twitter -b urls.xlsx -M one
    """
    # 合并参数
    kwargs["platform"] = platform
    kwargs["batch"] = batch
    kwargs["order"] = order
    kwargs["config"] = config

    # 移除 None 值参数
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    # 创建批量运行器并执行
    runner = BatchRunner(platform, kwargs)

    # 运行异步任务
    import asyncio

    try:
        stats = asyncio.run(runner.run_batch())

        # 根据执行结果退出
        if stats["failed"] > 0:
            ctx.exit(1)
        ctx.exit(0)

    except Exception as e:
        from f2.log.logger import logger

        logger.error(_("批量处理执行失败：{0}").format(str(e)))
        ctx.exit(1)
