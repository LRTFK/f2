# path: f2/apps/twitter/utils.py

import asyncio
import base64
import re
import traceback
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

import httpx

import f2
from f2.crawlers.base_crawler import BaseCrawler
from f2.exceptions.api_exceptions import (
    APIConnectionError,
    APINotFoundError,
    APIResponseError,
    APITimeoutError,
    APIUnauthorizedError,
)
from f2.exceptions.conf_exceptions import InvalidConfError
from f2.i18n.translator import _
from f2.log.logger import logger, trace_logger
from f2.utils.config.conf_manager import ConfigManager
from f2.utils.file.name import split_filename
from f2.utils.file.user_storage import ensure_user_storage
from f2.utils.string.formatter import extract_valid_urls
from f2.utils.time.timestamp import str_2_timestamp


class ClientConfManager:
    """
    用于管理客户端配置 (Used to manage client configuration)
    """

    client_conf = ConfigManager(f2.F2_CONFIG_FILE_PATH).get_config("f2")
    twitter_conf = client_conf.get("twitter", {})

    @classmethod
    def client(cls) -> dict:
        return cls.twitter_conf

    @classmethod
    def conf_version(cls) -> str:
        return cls.client_conf.get("version", "unknown")

    @classmethod
    def proxies(cls) -> dict:
        return cls.twitter_conf.get("proxies", {})

    @classmethod
    def headers(cls) -> dict:
        return cls.twitter_conf.get("headers", {})

    @classmethod
    def user_agent(cls) -> str:
        return cls.headers().get("User-Agent", "")

    @classmethod
    def referer(cls) -> str:
        return cls.headers().get("Referer", "")

    @classmethod
    def authorization(cls) -> str:
        return cls.headers().get("Authorization", "")

    @classmethod
    def x_csrf_token(cls) -> str:
        return cls.headers().get("X-Csrf-Token", "")


class ModelManager:

    @classmethod
    def model_2_endpoint(
        cls,
        base_endpoint: str,
        params: dict,
    ) -> str:
        if not isinstance(params, dict):
            raise TypeError(_("参数必须是字典类型"))

        param_str = "&".join([f"{k}={v}" for k, v in params.items()])

        # 检查base_endpoint是否已有查询参数 (Check if base_endpoint already has query parameters)
        separator = "&" if "?" in base_endpoint else "?"

        final_endpoint = f"{base_endpoint}{separator}{param_str}"

        return final_endpoint


class UniqueIdFetcher(BaseCrawler):
    # https://x.com/CaroylnG61544
    # https://x.com/CaroylnG61544/
    # https://x.com/CaroylnG61544/followers
    # https://x.com/CaroylnG61544/status/1440000000000000000
    # https://twitter.com/CaroylnG61544/status/1440000000000000000/photo/1

    # 预编译正则表达式
    _UNIQUE_ID_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?(twitter\.com|x\.com)/(?:@)?([a-zA-Z0-9_]+)"
    )

    @classmethod
    async def get_unique_id(cls, url: str) -> str:
        """
        从用户URL中提取用户ID
        (Extract user ID from user URL)

        Args:
            url (str): 用户URL (User URL)

        Returns:
            str: 用户唯一ID (User Unique Id)
        """

        if not isinstance(url, str):
            raise TypeError(_("参数必须是字符串类型"))

        # 提取有效URL
        extracted_url = extract_valid_urls(url)

        if extracted_url is None:
            raise APINotFoundError(_("输入的URL不合法。类名：{0}").format(cls.__name__))
        url = extracted_url

        # 创建一个实例以访问 aclient
        instance = cls()

        try:
            headers = {
                "User-Agent": ClientConfManager.user_agent(),
                "Referer": url,
            }
            response = await instance.aclient.get(
                url, headers=headers, follow_redirects=True
            )

            match = cls._UNIQUE_ID_PATTERN.search(str(response.url))
            if match:
                return match.group(2)
            else:
                raise APIResponseError(
                    _(
                        "未在响应的地址中找到unique_id，检查链接是否为用户链接。类名：{0}"
                    ).format(cls.__name__)
                )

        except httpx.TimeoutException as exc:
            trace_logger.error(traceback.format_exc())
            raise APITimeoutError(
                _(
                    "{0}。 链接：{1}，代理：{2}，异常类名：{3}，异常详细信息：{4}"
                ).format(
                    "请求端点超时",
                    url,
                    cls.proxies,
                    cls.__name__,
                    exc,
                )
            )

        except httpx.NetworkError as exc:
            trace_logger.error(traceback.format_exc())
            raise APIConnectionError(
                _(
                    "{0}。 链接：{1}，代理：{2}，异常类名：{3}，异常详细信息：{4}"
                ).format(
                    "网络连接失败，请检查当前网络环境",
                    url,
                    cls.proxies,
                    cls.__name__,
                    exc,
                )
            )

        except httpx.ProtocolError as exc:
            trace_logger.error(traceback.format_exc())
            raise APIUnauthorizedError(
                _(
                    "{0}。 链接：{1}，代理：{2}，异常类名：{3}，异常详细信息：{4}"
                ).format(
                    "请求协议错误",
                    url,
                    cls.proxies,
                    cls.__name__,
                    exc,
                )
            )

        except httpx.ProxyError as exc:
            trace_logger.error(traceback.format_exc())
            raise APIConnectionError(
                _(
                    "{0}。 链接：{1}，代理：{2}，异常类名：{3}，异常详细信息：{4}"
                ).format(
                    "请求代理错误",
                    url,
                    cls.proxies,
                    cls.__name__,
                    exc,
                )
            )

    @classmethod
    async def get_all_unique_ids(cls, urls: list) -> list:
        """
        从用户URL列表中提取所有用户唯一ID
        (Extract all unique ids from the list of user URLs)

        Args:
            urls (list): 用户URL列表 (List of user URLs)

        Returns:
            list: 用户唯一ID列表 (List of unique ids)
        """

        if not isinstance(urls, list):
            raise TypeError(_("参数必须是列表类型"))

        # 提取有效URL
        urls = extract_valid_urls(urls)

        # 获取所有用户ID
        if urls == []:
            raise (
                APINotFoundError(
                    _("输入的URL List不合法。类名：{0}").format(cls.__name__)
                )
            )

        unique_ids = [cls.get_unique_id(url) for url in urls]
        return await asyncio.gather(*unique_ids)


class TweetIdFetcher(BaseCrawler):
    # 预编译正则表达式
    _TWEET_URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/.*/status/(\d+)(?:/|\?|#.*$|$)"
    )

    @classmethod
    async def get_tweet_id(cls, url: str) -> str:
        """
        从推文URL中提取推文ID
        (Extract tweet ID from tweet URL)

        Args:
            url (str): 推文URL (Tweet URL)

        Returns:
            str: 推文ID (Tweet ID)
        """

        if not isinstance(url, str):
            raise TypeError(_("参数必须是字符串类型"))

        # 提取有效URL
        extracted_url = extract_valid_urls(url)

        if extracted_url is None:
            raise APINotFoundError(_("输入的URL不合法。类名：{0}").format(cls.__name__))
        url = extracted_url

        # 创建一个实例以访问 aclient
        instance = cls()

        # 解析URL并检查主机
        parsed_url = urlparse(url)
        host = parsed_url.hostname

        if host is None:
            raise APINotFoundError(
                _("无法解析URL的主机部分。类名：{0}").format(cls.__name__)
            )
        try:
            if "t.co" in host:
                response = await instance.aclient.get(
                    url, headers=ClientConfManager.headers(), follow_redirects=True
                )
                url = response.text

            match = cls._TWEET_URL_PATTERN.search(url)
            if match:
                return match.group(1)
            else:
                raise APIResponseError(
                    _(
                        "未在响应的地址中找到tweet_id，检查链接是否为推文链接。类名：{0}"
                    ).format(cls.__name__),
                    response.status_code,
                )

        except httpx.HTTPStatusError:
            raise APINotFoundError(
                _("未找到推文，请检查推文链接是否正确。类名：{0}").format(cls.__name__)
            )

        except httpx.RequestError as exc:
            raise APIConnectionError(
                _(
                    "请求端点失败，请检查当前网络环境。 链接：{0}，代理：{1}，异常类名：{2}，异常详细信息：{3}"
                ).format(url, ClientConfManager.proxies(), cls.__name__, exc)
            )

    @classmethod
    async def get_all_tweet_ids(cls, urls: list) -> list:
        """
        从推文URL列表中提取所有推文ID
        (Extract all tweet IDs from the list of tweet URLs)

        Args:
            urls (list): 推文URL列表 (List of tweet URLs)

        Returns:
            list: 推文ID列表 (List of tweet IDs)
        """

        if not isinstance(urls, list):
            raise TypeError(_("参数必须是列表类型"))

        # 提取有效URL
        urls = extract_valid_urls(urls)

        # 获取所有推文ID
        if urls == []:
            raise (
                APINotFoundError(
                    _("输入的URL List不合法。类名：{0}").format(cls.__name__)
                )
            )

        tweet_ids = [cls.get_tweet_id(url) for url in urls]
        return await asyncio.gather(*tweet_ids)


def format_file_name(
    naming_template: str,
    tweet_data: dict = {},
    custom_fields: dict = {},
) -> str:
    """
    根据配置文件的全局格式化文件名
    (Format file name according to the global conf file)

    Args:
        naming_template (str): 文件的命名模板, 如 "{create}_{desc}" (Naming template for files, such as "{create}_{desc}")
        tweet_data (dict): 推文数据的字典 (dict of twitter data)
        custom_fields (dict): 用户自定义字段, 用于替代默认的字段值 (Custom fields for replacing default field values)

    Note:
        windows 文件名长度限制为 255 个字符, 开启了长文件名支持后为 32,767 个字符
        (Windows file name length limit is 255 characters, 32,767 characters after long file name support is enabled)
        Unix 文件名长度限制为 255 个字符
        (Unix file name length limit is 255 characters)
        取去除后的50个字符, 加上后缀, 一般不会超过255个字符
        (Take the removed 50 characters, add the suffix, and generally not exceed 255 characters)
        详细信息请参考: https://en.wikipedia.org/wiki/Filename#Length
        (For more information, please refer to: https://en.wikipedia.org/wiki/Filename#Length)

    Returns:
        str: 格式化的文件名 (Formatted file name)
    """

    if not naming_template:
        raise InvalidConfError(key="naming", value=naming_template)

    # 为不同系统设置不同的文件名长度限制
    os_limit = {
        "win32": 200,
        "cygwin": 200,
        "darwin": 200,
        "linux": 200,
    }
    fields = {
        "create": tweet_data.get("tweet_created_at", ""),  # 长度固定19
        "nickname": tweet_data.get("nickname", ""),  # 不固定
        "tweet_id": tweet_data.get("tweet_id", ""),  # 长度固定19
        "desc": split_filename(tweet_data.get("tweet_desc", ""), os_limit),
        "uid": tweet_data.get("user_unique_id", ""),  # 不固定
    }

    if custom_fields:
        # 更新自定义字段
        fields.update(custom_fields)

    try:
        return naming_template.format(**fields)
    except KeyError as e:
        raise KeyError(_("文件名模板字段 {0} 不存在，请检查").format(e))


def create_or_rename_user_folder(
    kwargs: dict,
    local_user_data: dict,
    user_unique_id: str,
    current_nickname: str,
) -> Path:
    """
    创建或重命名用户目录 (Create or rename user directory)

    Args:
        kwargs (dict): 配置参数 (Conf parameters)
        local_user_data (dict): 本地用户数据 (Local user data)
        current_nickname (str): 当前用户昵称 (Current user nickname)

    Returns:
        user_path (Path): 用户目录路径 (User directory path)
    """
    legacy_nicknames = [current_nickname]
    if local_user_data:
        legacy_nicknames.append(local_user_data.get("nickname"))

    return create_user_folder(
        kwargs,
        user_unique_id=user_unique_id,
        current_nickname=current_nickname,
        legacy_nicknames=legacy_nicknames,
    )


def create_user_folder(
    kwargs: dict,
    user_unique_id: Union[str, int],
    current_nickname: Union[str, int, None],
    legacy_nicknames: list[Union[str, int, None]] | None = None,
) -> Path:
    """
    根据提供的配置文件创建用户唯一ID真实目录和昵称链接目录。
    (Create user unique-id storage directory and nickname link directory.)

    Args:
        kwargs (dict): 配置文件，字典格式。(Conf file, dict format)
        user_unique_id (Union[str, int]): 用户唯一ID。 (User unique id)
        current_nickname (Union[str, int, None]): 当前昵称。 (Current nickname)
        legacy_nicknames (list): 可能存在的历史昵称列表。 (Legacy nicknames)

    Note:
        如果未在配置文件中指定路径，则默认为 "Download"。
        (If the path is not specified in the conf file, it defaults to "Download".)
        支持绝对与相对路径。
        (Support absolute and relative paths)

    Raises:
        TypeError: 如果 kwargs 不是字典格式，将引发 TypeError。
        (If kwargs is not in dict format, TypeError will be raised.)
    """

    return ensure_user_storage(
        kwargs=kwargs,
        platform="twitter",
        user_unique_id=user_unique_id,
        current_nickname=current_nickname,
        legacy_nicknames=legacy_nicknames,
    )


def rename_user_folder(old_path: Path, new_nickname: str) -> Path:
    """
    重命名用户目录 (Rename User Folder).

    Args:
        old_path (Path): 旧的用户目录路径 (Path of the old user folder)
        new_nickname (str): 新的用户昵称 (New user nickname)

    Returns:
        Path: 重命名后的用户目录路径 (Path of the renamed user folder)
    """
    # 保留兼容旧调用，新的目录策略已不再执行重命名。
    return old_path


import base64
import re


def extract_desc(text):
    """
    提取推特标题，抛弃从 "https" 开始及其后的内容，包括其前一个空格。

    Args:
        text (str): 原始推文内容

    Returns:
        str: 提取后的标题
    """

    text = text.strip()  # 去掉两端空格
    https_index = text.find("https")  # 查找 "https" 的起始位置

    if https_index != -1:  # 如果存在 "https"
        # 找到 "https" 前第一个空格的位置
        cutoff_index = text.rfind(" ", 0, https_index)
        if cutoff_index != -1:
            return text[:cutoff_index].strip()  # 返回截断后的部分
    return text.strip()  # 如果没有 "https"，返回去掉两端空格后的内容


def cursor_to_timestamp(cursor_str: str) -> int:
    """
    从 Twitter cursor 解码并转换为毫秒时间戳

    Twitter cursor 是 Base64 编码的字符串，包含 Twitter Snowflake ID
    通过解码 cursor 并提取 Snowflake ID，然后转换为时间戳

    Args:
        cursor_str (str): Twitter cursor 字符串，如 "DAAHCgABHDdvw-f__-sLAAIAAAATMjAyNjg5MDY3MzI3MDc2NzkzMggAAwAAAAIAAA"

    Returns:
        int: 毫秒时间戳，如果解码失败返回 0

    Note:
        Twitter Snowflake ID 结构 (64 位):
        - 1 位未使用
        - 41 位时间戳 (毫秒级，相对于 Twitter epoch)
        - 10 位机器 ID
        - 12 位序列号
        Twitter epoch: 1288834974657 (2010-11-04 01:42:54.657 UTC)

    解密步骤示例:
        1. Base64 解码 (需添加 padding 使长度为 4 的倍数)
           cursor: 'DAAHCgAB...EAAA' (66 字符)
           填充后：'DAAHCgAB...EAAA==' (68 字符)

        2. 字节转字符串 (使用 latin-1 保留所有字节)
           decoded: b"\x0c\x00...\x132033371544584626477\x08..."
           包含控制字符和可读的 Snowflake ID 数字字符串

        3. 正则提取 Snowflake ID
           匹配 15-20 位数字：2033371544584626477

        4. 位运算转换时间戳
           snowflake_id >> 22 = 484793554445 (去掉 10 位机器 ID + 12 位序列号)
           + 1288834974657 (Twitter epoch)
           = 1773628529102 (毫秒时间戳)
    """

    logger.debug(_("----cursor_str: '{0}'").format(str(cursor_str)))

    if not cursor_str:
        return 0

    try:
        # Base64 解码 - 添加 padding 修复
        # Base64 字符串长度必须是 4 的倍数，否则需要添加 '=' padding
        # 例如：66 % 4 = 2，需要添加 2 个 '='
        padding_needed = len(cursor_str) % 4
        if padding_needed:
            cursor_str_padded = cursor_str + '=' * (4 - padding_needed)
        else:
            cursor_str_padded = cursor_str

        decoded = base64.b64decode(cursor_str_padded)
        # logger.debug(_("----decoded: '{0}'").format(str(decoded)))
        decoded_str = decoded.decode('latin-1')  # 使用 latin-1 解码以保留所有字节
        # logger.debug(_("----decoded_str: '{0}'").format(str(decoded_str)))

        # 使用正则表达式提取数字字符串 (Twitter Snowflake ID)
        # Snowflake ID 是 15-20 位的数字，embedded 在解码后的字符串中
        # 周围可能包含二进制控制字符
        match = re.search(r'(\d{15,20})', decoded_str)
        if match:
            snowflake_id = int(match.group(1))

            # Twitter Snowflake ID 转时间戳
            # 右移 22 位：去掉低位的 10 位机器 ID + 12 位序列号，保留 41 位时间戳
            # 加上 Twitter epoch (1288834974657) 转换为标准 Unix 时间戳
            timestamp_ms = (snowflake_id >> 22) + 1288834974657

            logger.debug(_("----timestamp_ms: '{0}'").format(str(timestamp_ms)))
            return timestamp_ms
        else:
            logger.debug(_("cursor 中未找到有效的 Snowflake ID: {0}").format(cursor_str[:50]))
            return 0

    except Exception as e:
        logger.debug(_("cursor 解码失败：{0}, 错误：{1}").format(cursor_str[:50], e))
        return 0


def get_page_earliest_timestamp(tweet_created_at_list: list) -> int:
    """
    从页面的推文创建时间列表中获取最早的时间戳

    Args:
        tweet_created_at_list (list): 推文创建时间字符串列表

    Returns:
        int: 最早的时间戳 (毫秒)，如果列表为空或所有值无效返回 0
    """
    if not tweet_created_at_list:
        return 0

    valid_timestamps = []
    for ts_str in tweet_created_at_list:
        if ts_str and ts_str != "Invalid timestamp":
            try:
                ts = str_2_timestamp(ts_str, unit="milli")
                if ts > 0:
                    valid_timestamps.append(ts)
            except Exception:
                continue

    if not valid_timestamps:
        return 0

    # 返回最早的时间戳（最小值）
    return min(valid_timestamps)
