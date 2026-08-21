"""main.run() 的端到端测试：注入假 BTSource，全程离线。

运行方式（仓库根目录）：
    uv run --with requests --with beautifulsoup4 --with zhconv \
        python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

import requests

import main
from bt_search import BTSource, SourcePool
from bt_search.scraper import DownloadLink, ResourceItem, SearchResult

RESULTS = [
    SearchResult(detail_id="1", title="甲片", url="https://x/detail/1.html"),
    SearchResult(detail_id="2", title="乙片", url="https://x/detail/2.html"),
]
RESOURCES = [
    ResourceItem(tdown_id="t1", title="甲片 4K 版", size="15GB", downloads="100"),
    ResourceItem(tdown_id="t2", title="甲片 1080p 版", size="8GB", downloads="200"),
]
LINK = DownloadLink(tdown_id="t2", magnet="magnet:?xt=urn:btih:fake")


class FakeSource(BTSource):
    """按调用记录返回固定数据的假源。"""

    def __init__(self, results=RESULTS, resources=RESOURCES, link=LINK):
        self._results = results
        self._resources = resources
        self._link = link
        self.download_requests: list[str] = []

    def search(self, keyword, *, limit=20):
        return self._results

    def fetch_resources(self, detail_id):
        return self._resources

    def fetch_download(self, tdown_id):
        self.download_requests.append(tdown_id)
        return self._link


class FakeTty(io.StringIO):
    def isatty(self):
        return True


def run_cli(argv, fake, *, stdin=None):
    """跑 main.run()，返回 (exit_code, stdout, stderr)。"""

    out, err = io.StringIO(), io.StringIO()
    args = main.build_parser().parse_args(argv)
    with (
        patch("main._build_pool", return_value=SourcePool([fake])),
        patch("sys.stdin", stdin if stdin is not None else io.StringIO("")),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        code = main.run(args)
    return code, out.getvalue(), err.getvalue()


class TestNonInteractiveFlow(unittest.TestCase):
    def test_list_resources_without_resource_index(self):
        code, out, err = run_cli(["avatar", "--movies", "1"], FakeSource())
        self.assertEqual(code, 0)
        self.assertIn("甲片 4K 版", err)          # 资源表打到 stderr
        self.assertIn("仅列出资源", err)           # 提示重跑
        self.assertEqual(out, "")                  # stdout 干净

    def test_fetch_magnet_by_resource_index(self):
        fake = FakeSource()
        code, out, err = run_cli(
            ["avatar", "--movies", "1", "--resource-index", "2", "--magnet-only"],
            fake,
        )
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "magnet:?xt=urn:btih:fake")
        self.assertEqual(fake.download_requests, ["t2"])  # 选中的是第 2 条资源

    def test_multi_movies_lists_each(self):
        code, out, err = run_cli(["avatar", "--movies", "1,2"], FakeSource())
        self.assertEqual(code, 0)
        self.assertIn("《甲片》", err)
        self.assertIn("《乙片》", err)

    def test_non_tty_without_movies_lists_and_exits(self):
        code, out, err = run_cli(["avatar"], FakeSource())
        self.assertEqual(code, 0)
        self.assertIn("甲片", err)
        self.assertIn("--movies", err)
        self.assertEqual(out, "")
        self.assertNotIn("资源版本", err)

    def test_list_resources_error_exits_nonzero(self):
        class PartialFail(FakeSource):
            def fetch_resources(self, detail_id):
                if detail_id in {"2", "FakeSource|2"}:
                    raise requests.RequestException("boom")
                return super().fetch_resources(detail_id)

        code, _, err = run_cli(["avatar", "--movies", "1,2"], PartialFail())
        self.assertEqual(code, 1)
        self.assertIn("获取资源列表失败", err)


class TestArgErrors(unittest.TestCase):
    def test_resource_index_out_of_range(self):
        code, _, err = run_cli(
            ["avatar", "--movies", "1", "--resource-index", "99"], FakeSource()
        )
        self.assertEqual(code, 2)
        self.assertIn("超出范围", err)

    def test_resource_index_rejected_for_multi_movies(self):
        code, _, err = run_cli(
            ["avatar", "--movies", "1,2", "--resource-index", "1"], FakeSource()
        )
        self.assertEqual(code, 2)
        self.assertIn("仅支持单部影片", err)

    def test_invalid_movies(self):
        code, _, err = run_cli(["avatar", "--movies", "99"], FakeSource())
        self.assertEqual(code, 2)
        self.assertIn("序号无效", err)

    def test_no_search_results(self):
        code, _, err = run_cli(["avatar", "--movies", "1"], FakeSource(results=[]))
        self.assertEqual(code, 1)
        self.assertIn("没有找到", err)

    def test_invalid_source_exits_2(self):
        # 未知源在发任何请求前就失败，因此不 patch _build_pool，走真实路径
        out, err = io.StringIO(), io.StringIO()
        args = main.build_parser().parse_args(
            ["avatar", "--source", "bogus", "--movies", "1"]
        )
        with (
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = main.run(args)
        self.assertEqual(code, 2)
        self.assertIn("未知站点", err.getvalue())


class TestBuildPool(unittest.TestCase):
    def test_default_pool_has_all_sources(self):
        pool = main._build_pool(None)
        self.assertEqual(pool.name, "pool(btbtla.com,cilixiong.org,torrentkitty.net)")

    def test_single_source(self):
        pool = main._build_pool("torrentkitty.net")
        self.assertEqual(len(pool.sources), 1)
        self.assertEqual(pool.sources[0].name, "torrentkitty.net")

    def test_unknown_source_raises(self):
        with self.assertRaises(ValueError):
            main._build_pool("bogus")


class TestInteractiveFlow(unittest.TestCase):
    def test_tty_user_picks_resource(self):
        fake = FakeSource()
        with patch("builtins.input", side_effect=["1", "2"]):  # 选影片 1，再选资源 2
            code, out, err = run_cli(["avatar"], fake, stdin=FakeTty())
        self.assertEqual(code, 0)
        self.assertEqual(fake.download_requests, ["t2"])
        self.assertIn("magnet:?xt=urn:btih:fake", out)


if __name__ == "__main__":
    unittest.main()
