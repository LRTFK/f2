# path: f2/apps/twitter/api.py
#
# queryId 更新说明：
# 各端点 URL 中的哈希段（如 Gb-d6r0vxPOADdG62OEBpQ）是 X 前端打包时生成的
# GraphQL 查询标识，X 发版会轮换。当接口报 "Could not find query" 时，
# 运行以下工具一键提取最新 queryId 并回写本文件：
#   .venv/Scripts/python.exe tools/update_twitter_queryid.py --patch
# 该工具从登录态首页 main bundle 提取查询定义，缺漏时经 /sw.js 缓存清单
# 兜底扫描全部 chunk（详见 tools/update_twitter_queryid.py 头部说明）。


class TwitterAPIEndpoints:
    """
    API Endpoints for Twitter
    """

    # Twitter Domain
    TWITTER_DOMAIN = "https://x.com"

    API_DOMAIN = "https://x.com/i/api/graphql"

    # User Detail
    USER_PROFILE = f"{API_DOMAIN}/Gb-d6r0vxPOADdG62OEBpQ/UserByScreenName"

    # User Post
    USER_POST = f"{API_DOMAIN}/SXVCYB8XHSS25nzIljNtZA/UserTweets"

    # User Like
    USER_LIKE = f"{API_DOMAIN}/xA8fDIbrJfy4ojjjXmSR-A/Likes"

    # User Bookmark
    USER_BOOKMARK = f"{API_DOMAIN}/iblrFnKr6PZUR-dWpfXG6g/Bookmarks"

    # Post Detail
    POST_DETAIL = f"{API_DOMAIN}/XMOz5h24KAZ86qKffKTLdQ/TweetDetail"
