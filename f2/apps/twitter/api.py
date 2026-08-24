# path: f2/apps/twitter/api.py


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
