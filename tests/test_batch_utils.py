# path: tests/test_batch_utils.py

import click
import pytest

from f2.utils.batch_utils import (
    apply_order,
    read_urls_from_file,
    run_batch_urls,
)


def _ctx() -> click.Context:
    return click.Context(click.Command("batch"))


def test_read_urls_skips_blank_and_comment_lines(tmp_path):
    url_file = tmp_path / "urls.txt"
    url_file.write_text(
        "https://example.com/1\n\n# 这是注释\n   \nhttps://example.com/2\n",
        encoding="utf-8",
    )

    assert read_urls_from_file(str(url_file)) == [
        "https://example.com/1",
        "https://example.com/2",
    ]


def test_read_urls_handles_crlf_and_bom(tmp_path):
    url_file = tmp_path / "urls.txt"
    url_file.write_bytes(
        b"\xef\xbb\xbfhttps://example.com/1\r\nhttps://example.com/2\r\n"
    )

    assert read_urls_from_file(str(url_file)) == [
        "https://example.com/1",
        "https://example.com/2",
    ]


def test_read_urls_falls_back_to_gbk(tmp_path):
    url_file = tmp_path / "urls.txt"
    url_file.write_bytes("# 中文注释\nhttps://example.com/1\n".encode("gbk"))

    assert read_urls_from_file(str(url_file)) == ["https://example.com/1"]


def test_read_urls_reports_missing_file(tmp_path):
    with pytest.raises(click.ClickException):
        read_urls_from_file(str(tmp_path / "not-here.txt"))


def test_apply_order():
    urls = ["a", "b", "c"]

    assert apply_order(urls, "asc") == ["a", "b", "c"]
    assert apply_order(urls, "desc") == ["c", "b", "a"]
    assert sorted(apply_order(urls, "random")) == urls
    # 原列表不被改动
    assert urls == ["a", "b", "c"]


def test_run_batch_urls_keeps_going_after_a_failure():
    seen = []

    def run_one(url):
        seen.append(url)
        if url == "b":
            raise RuntimeError("boom")

    with pytest.raises(click.exceptions.Exit) as excinfo:
        run_batch_urls(_ctx(), ["a", "b", "c"], "asc", run_one)

    assert excinfo.value.exit_code == 1
    assert seen == ["a", "b", "c"]


def test_run_batch_urls_exit_zero_counts_as_success():
    def run_one(url):
        raise click.exceptions.Exit(0)

    # 被调用的命令以 0 结束不算失败，整体不应抛异常
    run_batch_urls(_ctx(), ["a"], "asc", run_one)


def test_run_batch_urls_empty_file_exits_nonzero():
    with pytest.raises(click.exceptions.Exit) as excinfo:
        run_batch_urls(_ctx(), [], "asc", lambda url: None)

    assert excinfo.value.exit_code == 1


def test_batch_command_is_registered():
    from f2.cli.cli_commands import main

    assert "batch" in main.commands


@pytest.mark.parametrize(
    "option", ["--platform", "--batch", "--order", "--config", "--max-counts"]
)
def test_batch_command_exposes_options(option):
    from f2.cli.batch_command import batch_command

    options = {
        opt
        for param in batch_command.params
        if isinstance(param, click.Option)
        for opt in param.opts
    }

    assert option in options
