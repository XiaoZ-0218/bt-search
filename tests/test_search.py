"""search_with_fallback 停止条件测试（离线，假源）。"""

from __future__ import annotations

import unittest

from bt_search import search_with_fallback
from bt_search.scraper import SearchResult
from bt_search.source import BTSource


class RecordingSource(BTSource):
    def __init__(self, name: str, results):
        self._name = name
        self._results = list(results)
        self.queries: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    def search(self, keyword, *, limit=20):
        self.queries.append(keyword)
        return list(self._results)

    def fetch_resources(self, detail_id):
        raise AssertionError("not used")

    def fetch_download(self, tdown_id):
        raise AssertionError("not used")


class TestFallbackStop(unittest.TestCase):
    def test_complete_result_stops_further_queries(self):
        src = RecordingSource(
            "torrentkitty.net",
            [SearchResult("all", "「夜王 黄子华」", "https://k/", complete=True)],
        )
        results, attempts = search_with_fallback("夜王 黄子华", src, limit=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(src.queries, ["夜王 黄子华"])
        self.assertEqual(len(attempts), 1)


if __name__ == "__main__":
    unittest.main()
