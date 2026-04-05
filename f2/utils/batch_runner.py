# path: f2/utils/batch_runner.py

import asyncio
import csv
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from f2.cli.cli_console import RichConsoleManager
from f2.i18n.translator import _
from f2.log.logger import logger

rich_console = RichConsoleManager().rich_console


class BatchRunner:
    """通用批量运行器，处理 URL 读取、排序、执行"""

    # 平台映射
    PLATFORM_MAPPING = {
        "dy": "douyin",
        "douyin": "douyin",
        "wb": "weibo",
        "weibo": "weibo",
        "twitter": "twitter",
        "x": "twitter",
        "tiktok": "tiktok",
        "bark": "bark",
    }

    def __init__(self, platform: str, kwargs: Dict[str, Any]):
        """
        初始化批量运行器

        Args:
            platform: 平台标识 (dy/douyin, wb/weibo, twitter, tiktok, bark)
            kwargs: 命令行参数字典
        """
        self.platform = self.PLATFORM_MAPPING.get(platform.lower(), platform.lower())
        self.kwargs = kwargs
        self.urls: List[Dict[str, Any]] = []
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "failed_urls": [],
        }

    def read_urls(self, file_path: str) -> List[Dict[str, Any]]:
        """
        读取 URL 文件，支持 .txt/.csv/.xlsx

        Args:
            file_path: URL 文件路径

        Returns:
            URL 列表，每个元素为包含 'url' 键的字典
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(_("URL 文件不存在：{0}").format(file_path))

        suffix = path.suffix.lower()

        if suffix == ".txt":
            return self._read_txt(path)
        elif suffix == ".csv":
            return self._read_csv(path)
        elif suffix in [".xlsx", ".xls"]:
            return self._read_excel(path)
        else:
            raise ValueError(
                _("不支持的文件格式：{0}，支持 .txt/.csv/.xlsx").format(suffix)
            )

    def _read_txt(self, path: Path) -> List[Dict[str, Any]]:
        """读取 txt 文件，每行一个 URL"""
        urls = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith("#"):  # 跳过空行和注释
                    urls.append({"url": url})
        logger.info(_("从 {0} 读取到 {1} 个 URL").format(path, len(urls)))
        return urls

    def _read_csv(self, path: Path) -> List[Dict[str, Any]]:
        """读取 CSV 文件，使用标准库 csv 模块"""
        urls = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                # 尝试获取 url 列，如果没有则使用第一列
                fieldnames = reader.fieldnames
                if not fieldnames:
                    return urls

                url_column = "url" if "url" in fieldnames else fieldnames[0]

                for row in reader:
                    url = row.get(url_column, "").strip()
                    if url:
                        urls.append({"url": url})
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(path, "r", encoding="gbk") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                if not fieldnames:
                    return urls

                url_column = "url" if "url" in fieldnames else fieldnames[0]

                for row in reader:
                    url = row.get(url_column, "").strip()
                    if url:
                        urls.append({"url": url})

        logger.info(_("从 {0} 读取到 {1} 个 URL").format(path, len(urls)))
        return urls

    def _read_excel(self, path: Path) -> List[Dict[str, Any]]:
        """读取 Excel 文件，需要安装 pandas 和 openpyxl"""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError(
                _("读取 Excel 文件需要安装 pandas 和 openpyxl: pip install pandas openpyxl")
            )

        df = pd.read_excel(path)

        # 如果只有一列，默认作为 url 列
        if len(df.columns) == 1:
            df.columns = ["url"]
        elif "url" not in df.columns:
            # 使用第一列作为 URL
            df = df.rename(columns={df.columns[0]: "url"})

        urls = df["url"].dropna().tolist()
        result = [{"url": str(url)} for url in urls if str(url).strip()]
        logger.info(_("从 {0} 读取到 {1} 个 URL").format(path, len(result)))
        return result

    def sort_urls(self, order: str = "asc") -> List[Dict[str, Any]]:
        """
        排序 URL

        Args:
            order: 排序方式 (asc/desc/random)

        Returns:
            排序后的 URL 列表
        """
        if order == "random":
            random.shuffle(self.urls)
            logger.info(_("URL 已随机排序"))
        elif order == "desc":
            self.urls.reverse()
            logger.info(_("URL 已倒序排序"))
        else:
            logger.info(_("URL 保持原始顺序"))

        return self.urls

    async def run_batch(self) -> Dict[str, Any]:
        """
        执行批量任务

        流程:
        1. 读取 URL 文件
        2. 按 order 参数排序
        3. 遍历每个 URL:
           - 更新 kwargs['url']
           - 调用对应平台的 handler.main()
           - 记录成功/失败
           - 显示进度和备注信息
        4. 返回统计结果

        Returns:
            统计结果字典
        """
        # 1. 读取 URL 文件
        batch_file = self.kwargs.get("batch")
        if not batch_file:
            raise ValueError(_("未指定 URL 文件路径"))

        self.urls = self.read_urls(batch_file)
        self.stats["total"] = len(self.urls)

        if not self.urls:
            logger.warning(_("URL 文件为空，没有可处理的内容"))
            return self.stats

        # 2. 排序 URL
        order = self.kwargs.get("order", "asc")
        self.sort_urls(order)

        # 3. 遍历执行
        rich_console.print(
            _(
                "\n[bold cyan]开始批量处理 {0} 个 URL，平台：{1}[/bold cyan]"
            ).format(len(self.urls), self.platform)
        )

        for index, url_item in enumerate(self.urls, start=1):
            url = url_item.get("url")
            if not url:
                continue

            rich_console.print(
                _("[cyan]进度：{0}/{1} - 处理 URL: {2}[/cyan]").format(
                    index, len(self.urls), url
                )
            )

            try:
                # 更新 kwargs 中的 URL
                self.kwargs["url"] = url

                # 调用对应平台的 handler
                await self._run_platform_handler()

                self.stats["success"] += 1
                rich_console.print(
                    _("[green]✓ URL {0} 处理成功[/green]").format(url)
                )

            except Exception as e:
                self.stats["failed"] += 1
                self.stats["failed_urls"].append({"url": url, "error": str(e)})
                logger.error(_("URL {0} 处理失败：{1}").format(url, str(e)))
                rich_console.print(
                    _("[red]✗ URL {0} 处理失败：{1}[/red]").format(url, str(e))
                )

            # 添加延时避免请求过于频繁
            if index < len(self.urls):
                timeout = self.kwargs.get("timeout", 1)
                logger.info(_("等待 {0} 秒后继续下一个 URL").format(timeout))
                await asyncio.sleep(timeout)

        # 4. 返回统计结果
        self._print_summary()
        return self.stats

    async def _run_platform_handler(self) -> None:
        """调用对应平台的 handler.main()"""
        import importlib

        # 动态导入平台 handler
        handler_module = importlib.import_module(f"f2.apps.{self.platform}.handler")

        # 创建 handler 实例并执行
        handler_class = getattr(handler_module, f"{self.platform.capitalize()}Handler")
        handler = handler_class(self.kwargs)

        # 获取模式并执行对应的处理函数
        mode = self.kwargs.get("mode")
        if mode:
            from f2.utils.core.decorators import mode_function_map

            if mode in mode_function_map:
                await mode_function_map[mode](handler)
            else:
                raise ValueError(_("不存在该模式：{0}").format(mode))
        else:
            # 如果没有指定模式，调用 main
            await handler_module.main(self.kwargs)

    def _print_summary(self) -> None:
        """打印执行摘要"""
        rich_console.print(
            _(
                "\n[bold cyan]=== 批量处理完成 ===[/bold cyan]"
            )
        )
        rich_console.print(
            _("[cyan]总数：{0}[/cyan]").format(self.stats["total"])
        )
        rich_console.print(
            _("[green]成功：{0}[/green]").format(self.stats["success"])
        )
        rich_console.print(
            _("[red]失败：{0}[/red]").format(self.stats["failed"])
        )

        if self.stats["failed_urls"]:
            rich_console.print(
                _("\n[yellow]失败的 URL 列表:[/yellow]")
            )
            for failed in self.stats["failed_urls"]:
                rich_console.print(
                    _("  - {0}: {1}").format(failed["url"], failed["error"])
                )
