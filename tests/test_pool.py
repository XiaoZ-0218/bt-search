"""SourcePool 路由与多源 ID 归属测试（离线，假源）。"""

from __future__ import annotations

import unittest

import requests

from bt_search import SourcePool, search_with_fallback
from bt_search.scraper import DownloadLink, ResourceItem, SearchResult
from bt_search.source import BTSource


class FakeSource(BTSource):
    """按调用记录返回固定数据的假源。"""

    def __init__(
        self,
        name: str,
        *,
        results=None,
        resources=None,
        link=None,
        search_error=None,
        resource_error=None,
        download_error=None,
        echo_magnet=False,
    ):
        self._name = name
        self._results = list(results or [])
        self._resources = list(resources or [])
        self._link = link
        self.search_error = search_error
        self.resource_error = resource_error
        self.download_error = download_error
        self.echo_magnet = echo_magnet
        self.search_queries: list[str] = []
        self.resource_requests: list[str] = []
        self.download_requests: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def search(self, keyword, *, limit=20):
        self.search_queries.append(keyword)
        if self.search_error:
            raise self.search_error
        return list(self._results)

    def fetch_resources(self, detail_id):
        self.resource_requests.append(detail_id)
        if self.resource_error:
            raise self.resource_error
        return list(self._resources)

    def fetch_download(self, tdown_id):
        self.download_requests.append(tdown_id)
        if self.download_error:
            raise self.download_error
        if self.echo_magnet:
            return DownloadLink(tdown_id=tdown_id, magnet=tdown_id)
        if self._link is not None:
            return self._link
        return DownloadLink(
            tdown_id=tdown_id, magnet=f"magnet:?xt=urn:btih:{tdown_id}"
        )


class TestFetchDownloadRouting(unittest.TestCase):
    def test_owner_error_does_not_echo_numeric_id_as_magnet(self):
        """btbtla 取链失败时，不能让磁力熊把 '55' 当成 magnet 返回。"""

        primary = FakeSource(
            "btbtla.com",
            results=[SearchResult("1", "片A", "https://a/1")],
            resources=[ResourceItem("55", "4K")],
            download_error=requests.RequestException("tdown 500"),
        )
        backup = FakeSource("cilixiong.org", echo_magnet=True)
        pool = SourcePool([primary, backup])

        movies = pool.search("片")
        resources = pool.fetch_resources(movies[0].detail_id)
        with self.assertRaises(requests.RequestException):
            pool.fetch_download(resources[0].tdown_id)
        self.assertEqual(backup.download_requests, [])

    def test_fetch_download_unwraps_to_native_id(self):
        primary = FakeSource(
            "btbtla.com",
            results=[SearchResult("1", "片A", "https://a/1")],
            resources=[ResourceItem("55", "4K")],
            link=DownloadLink("55", magnet="magnet:?xt=urn:btih:real"),
        )
        pool = SourcePool([primary])
        movies = pool.search("片")
        resources = pool.fetch_resources(movies[0].detail_id)
        link = pool.fetch_download(resources[0].tdown_id)
        self.assertEqual(primary.download_requests, ["55"])
        self.assertEqual(link.magnet, "magnet:?xt=urn:btih:real")


class TestIdNamespacing(unittest.TestCase):
    def test_search_qualifies_detail_id_and_sets_source(self):
        src = FakeSource(
            "btbtla.com",
            results=[SearchResult("1", "片A", "https://a/1")],
        )
        movies = SourcePool([src]).search("片")
        self.assertEqual(movies[0].detail_id, "btbtla.com|1")
        self.assertEqual(movies[0].source, "btbtla.com")

    def test_colliding_native_ids_fetch_from_own_source(self):
        """fallback 两次命中同一数字 id 时，各自拉自己的资源，不改写归属。"""

        class Btbtla(FakeSource):
            def search(self, keyword, *, limit=20):
                self.search_queries.append(keyword)
                if " " in keyword.strip():
                    return []
                return [SearchResult("100", "bt 的片", "https://b/100")]

        btbtla = Btbtla(
            "btbtla.com",
            resources=[ResourceItem("99", "4K")],
            link=DownloadLink("99", magnet="magnet:?xt=urn:btih:bbb"),
        )
        cilixiong = FakeSource(
            "cilixiong.org",
            results=[SearchResult("100", "熊的片", "https://c/100")],
            resources=[ResourceItem("magnet:?xt=urn:btih:ccc", "1080p")],
            echo_magnet=True,
        )
        pool = SourcePool([btbtla, cilixiong])
        movies, _attempts = search_with_fallback("原词 拆词", pool, limit=10)

        by_title = {m.title: m for m in movies}
        self.assertIn("熊的片", by_title)
        self.assertIn("bt 的片", by_title)

        bear = pool.fetch_resources(by_title["熊的片"].detail_id)
        self.assertEqual(cilixiong.resource_requests, ["100"])
        self.assertEqual(btbtla.resource_requests, [])
        self.assertTrue(bear[0].tdown_id.startswith("cilixiong.org|"))

        bt_res = pool.fetch_resources(by_title["bt 的片"].detail_id)
        self.assertEqual(btbtla.resource_requests, ["100"])
        self.assertTrue(bt_res[0].tdown_id.startswith("btbtla.com|"))


class TestSearchFailover(unittest.TestCase):
    def test_search_skips_failed_source_and_uses_next(self):
        broken = FakeSource(
            "btbtla.com", search_error=requests.RequestException("down")
        )
        backup = FakeSource(
            "cilixiong.org",
            results=[SearchResult("7", "备援片", "https://c/7")],
        )
        movies = SourcePool([broken, backup]).search("片")
        self.assertEqual(len(movies), 1)
        self.assertEqual(movies[0].source, "cilixiong.org")
        self.assertEqual(movies[0].title, "备援片")

    def test_empty_primary_falls_through(self):
        empty = FakeSource("btbtla.com", results=[])
        backup = FakeSource(
            "torrentkitty.net",
            results=[SearchResult("all", "合成卡", "https://k/", complete=True)],
        )
        movies = SourcePool([empty, backup]).search("片")
        self.assertEqual(movies[0].source, "torrentkitty.net")


if __name__ == "__main__":
    unittest.main()
