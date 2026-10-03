# path: tests/test_twitter_download_dispatch.py

import logging

import pytest

from f2.apps.twitter.dl import TwitterDownloader

VIDEO_URLS = ["https://example.com/1.mp4", "https://example.com/2.mp4"]
IMAGE_URLS = ["https://example.com/1.jpg", "https://example.com/2.jpg"]
KWARGS = {"naming": "{create}_{desc}", "folderize": False}


@pytest.fixture
def downloader(monkeypatch):
    """替换真正的下载，只记录走了哪条下载路径"""
    dl = TwitterDownloader(
        {"cookie": "auth_token=guest", "headers": {"User-Agent": "f2-test"}}
    )
    dl.calls = []

    async def download_video():
        dl.calls.append("video")

    async def download_images():
        dl.calls.append("images")

    async def download_desc():
        dl.calls.append("desc")

    monkeypatch.setattr(dl, "download_video", download_video)
    monkeypatch.setattr(dl, "download_images", download_images)
    monkeypatch.setattr(dl, "download_desc", download_desc)
    return dl


@pytest.fixture
def recording_downloader(monkeypatch):
    """保留真实的 download_video，只记录 initiate_download 的调用"""
    dl = TwitterDownloader(
        {"cookie": "auth_token=guest", "headers": {"User-Agent": "f2-test"}}
    )
    dl.calls = []

    async def initiate_download(file_type, file_url, base_path, file_name, file_suffix):
        dl.calls.append((file_type, file_url, file_name, file_suffix))

    async def download_desc():
        dl.calls.append("desc")

    monkeypatch.setattr(dl, "initiate_download", initiate_download)
    monkeypatch.setattr(dl, "download_desc", download_desc)
    return dl


def tweet_media(media_type, video_urls=None, image_urls=None):
    return {
        "tweet_id": "1",
        "user_id": "u1",
        "tweet_desc": "t",
        "tweet_desc_raw": "t",
        "tweet_created_at": "2018-10-10 20-19-24",
        "tweet_media_type": media_type,
        "tweet_media_url": image_urls,
        "tweet_video_url": video_urls,
    }


def f2_warnings(caplog):
    return [
        r.getMessage()
        for r in caplog.records
        if r.name == "f2" and r.levelno == logging.WARNING
    ]


# 详情模式的媒体类型是列表（多视频/多图推文），此前 ["video","video"] 两个分支都不匹配而被跳过
@pytest.mark.parametrize(
    "media_type, expected",
    [
        ("video", ["video", "desc"]),
        ("animated_gif", ["video", "desc"]),
        (["video"], ["video", "desc"]),
        (["video", "video"], ["video", "desc"]),
        ("photo", ["images", "desc"]),
        (["photo", "photo"], ["images", "desc"]),
        (None, ["desc"]),
        ([], ["desc"]),
    ],
)
async def test_media_type_dispatch(downloader, tmp_path, media_type, expected):
    data = tweet_media(media_type, video_urls=VIDEO_URLS, image_urls=IMAGE_URLS)
    await downloader.handler_download(KWARGS, data, tmp_path)
    assert downloader.calls == expected


async def test_mixed_media_downloads_videos_and_images(downloader, tmp_path):
    # 详情模式图文混合（["photo","video"]）此前只下图片，现在视频与图片都会下载
    data = tweet_media(["photo", "video"], video_urls=VIDEO_URLS, image_urls=IMAGE_URLS)
    await downloader.handler_download(KWARGS, data, tmp_path)
    assert downloader.calls == ["video", "images", "desc"]


async def test_multi_video_downloads_each_url_with_index_suffix(
    recording_downloader, tmp_path
):
    data = tweet_media(["video", "video"], video_urls=VIDEO_URLS)
    await recording_downloader.handler_download(KWARGS, data, tmp_path)

    downloads = recording_downloader.calls[:-1]  # 末位是 desc
    assert [c[1] for c in downloads] == VIDEO_URLS
    assert downloads[0][2].endswith("_video_1")
    assert downloads[1][2].endswith("_video_2")


async def test_single_video_keeps_name_without_index(recording_downloader, tmp_path):
    data = tweet_media("video", video_urls=["https://example.com/only.mp4"])
    await recording_downloader.handler_download(KWARGS, data, tmp_path)

    downloads = recording_downloader.calls[:-1]
    assert len(downloads) == 1
    assert downloads[0][2].endswith("_video")


async def test_video_url_as_string_is_supported(recording_downloader, tmp_path):
    data = tweet_media("video", video_urls="https://example.com/single.mp4")
    await recording_downloader.handler_download(KWARGS, data, tmp_path)

    downloads = recording_downloader.calls[:-1]
    assert [c[1] for c in downloads] == ["https://example.com/single.mp4"]


async def test_empty_video_urls_warns_and_downloads_nothing(
    recording_downloader, tmp_path, caplog
):
    data = tweet_media("video", video_urls=[])
    with caplog.at_level(logging.DEBUG):
        await recording_downloader.handler_download(KWARGS, data, tmp_path)

    assert recording_downloader.calls == ["desc"]
    assert any("视频链接为空" in message for message in f2_warnings(caplog))
