# path: f2/cli/batch_command.py

import asyncio
import importlib
from pathlib import Path
from typing import Optional

import click

import f2
from f2.i18n.translator import _
from f2.log.logger import logger
from f2.utils.batch_runner import BatchRunner
from f2.utils.config.conf_manager import ConfigManager
from f2.utils.config.merge import merge_config
from f2.utils.file.path import get_resource_path


# 平台映射（用于获取配置）
PLATFORM_TO_APP = {
    "dy": "douyin",
    "douyin": "douyin",
    "wb": "weibo",
    "weibo": "weibo",
    "twitter": "twitter",
    "x": "twitter",
    "tiktok": "tiktok",
    "bark": "bark",
}


def get_client_conf_manager(app_name: str):
    """动态获取对应平台的 ClientConfManager"""
    try:
        module = importlib.import_module(f"f2.apps.{app_name}.utils")
        return getattr(module, "ClientConfManager")
    except (ImportError, AttributeError):
        logger.warning(_("平台 {0} 没有找到 ClientConfManager，使用默认配置").format(app_name))
        return None


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
    # 将平台简称转换为完整名称
    app_name = PLATFORM_TO_APP.get(platform.lower(), platform.lower())

    ##################
    # 配置合并逻辑：
    # CLI 参数具有最高优先，CLI >= 自定义 >= 低频
    # 在 app 低频配置中设置好重试次数，超时时间，下载路径，下载线程，cookie 等低频的参数
    # 在自定义配置中可以设置不同用户的高频参数
    # CLI 参数为配置文件的热修改
    ##################

    # 读取低频主配置文件
    main_manager = ConfigManager(f2.APP_CONFIG_FILE_PATH)
    main_conf_path = get_resource_path(f2.APP_CONFIG_FILE_PATH)
    main_conf = main_manager.get_config(app_name)

    if not main_conf:
        logger.warning(_("未在主页配置中找到 {0} 的配置，使用空配置").format(app_name))
        main_conf = {}

    # 获取对应平台的 ClientConfManager 并更新主配置中的 headers 和 proxies
    client_conf_mgr = get_client_conf_manager(app_name)
    if client_conf_mgr:
        # 更新主配置文件中的代理参数
        main_conf.setdefault("proxies", {})
        main_conf["proxies"] = client_conf_mgr.proxies()

        # 更新主配置文件中的 headers 参数
        kwargs.setdefault("headers", {})
        try:
            kwargs["headers"]["User-Agent"] = client_conf_mgr.user_agent()
            kwargs["headers"]["Referer"] = client_conf_mgr.referer()
        except AttributeError:
            # 如果平台没有这些方法，跳过
            pass

    # 读取自定义配置文件
    if config:
        custom_manager = ConfigManager(config)
        custom_conf = custom_manager.get_config(app_name) or {}
    else:
        custom_manager = main_manager
        config = str(main_conf_path)
        custom_conf = main_conf

    # 检查并转换 proxies 类型（兼容旧版）
    if kwargs.get("proxies"):
        if isinstance(kwargs["proxies"], dict):
            # 已经是正确的格式，不需要转换
            pass
        elif isinstance(kwargs["proxies"], (tuple, list)) and len(kwargs["proxies"]) >= 2:
            proxy_url = kwargs["proxies"][1]  # 第二个元素是地址
            proxy_type = kwargs["proxies"][0]  # 第一个元素是类型
            kwargs["proxies"] = {
                "type": proxy_type,
                f"{proxy_type}://": f"{proxy_type}://{proxy_url}",
                "http://": (
                    f"{proxy_type}://{proxy_url}" if proxy_type == "http" else None
                ),
                "https://": (
                    f"{proxy_type}://{proxy_url}" if proxy_type == "https" else None
                ),
            }

    # 配置合并：主配置 + 自定义配置 + CLI 参数
    kwargs = merge_config(main_conf, custom_conf, **kwargs)

    # 添加平台信息和 batch 参数
    kwargs["app_name"] = app_name
    kwargs["platform"] = platform
    kwargs["batch"] = batch
    kwargs["order"] = order

    logger.info(_("批量模式：平台={0}, URL 文件={1}").format(platform, batch))
    logger.info(_("主配置路径：{0}").format(main_conf_path))
    logger.info(_("自定义配置路径：{0}").format(Path.cwd() / config if config else "无"))
    logger.debug(_("合并后参数：{0}").format(kwargs))

    # 创建批量运行器并执行
    runner = BatchRunner(platform, kwargs)

    # 运行异步任务
    try:
        stats = asyncio.run(runner.run_batch())

        # 根据执行结果退出
        if stats["failed"] > 0:
            ctx.exit(1)
        ctx.exit(0)

    except Exception as e:
        logger.error(_("批量处理执行失败：{0}").format(str(e)))
        ctx.exit(1)
