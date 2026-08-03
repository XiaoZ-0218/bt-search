"""bt_search.scraper 的纯 HTML 解析测试（离线，不打网络）。"""

from __future__ import annotations

import unittest

from bt_search.scraper import (
    _extract_download_links,
    _iter_resources,
    _iter_search_results,
    _parse_size,
)

BASE = "https://www.btbtla.com"

SEARCH_HTML = """
<div class="module-item">
  <a class="module-item-title" href="/detail/123.html" title="阿凡达">阿凡达</a>
  <div class="module-item-caption">
    <span>2009</span><span class="video-class">动作,科幻</span><span>美国</span>
  </div>
  <div class="video-text">前海军战士杰克·萨利来到潘多拉星……</div>
</div>
<div class="module-item">
  <a class="module-item-title" href="/detail/123.html" title="阿凡达">阿凡达</a>
</div>
<div class="module-item">
  <a class="module-item-title" href="/detail/456.html" title="阿凡达：水之道">阿凡达：水之道</a>
  <div class="module-item-caption">
    <span>2022</span><span class="video-class">动作,科幻</span><span>美国</span>
  </div>
</div>
<a class="module-item-title" href="/other/789.html" title="不在 detail 路径下">忽略我</a>
"""

RESOURCES_HTML = """
<div class="module-row-info">
  <a href="/tdown/55.html" title="《阿凡达》阿凡达[国英多音轨+简繁英字幕].2009.2160p.WEB-DL 14.97GB">x</a>
</div>
<div class="btn-down">237</div>
<div class="module-row-info">
  <a href="/tdown/66.html" title="《阿凡达》阿凡达.2009.1080p.BluRay 9.84GB">x</a>
</div>
<div class="btn-down">213</div>
"""

DOWNLOAD_HTML = """
<a href="magnet:?xt=urn:btih:ea5a8a3004dbb4d5eba651645dfe1ae5e9c2abd1">磁力链接</a>
<a href="/dlt/12345.html">迅雷下载</a>
<a href="https://pan.example.com/s/abc">网盘</a>
<a href="https://www.btbtla.com/help">站内链接不算</a>
"""


class TestIterSearchResults(unittest.TestCase):
    def test_parse_fields(self):
        results = list(_iter_search_results(SEARCH_HTML, BASE, limit=10))
        self.assertEqual(len(results), 2)
        first = results[0]
        self.assertEqual(first.detail_id, "123")
        self.assertEqual(first.title, "阿凡达")
        self.assertEqual(first.year, "2009")
        self.assertEqual(first.region, "美国")
        self.assertEqual(first.category, "动作,科幻")
        self.assertIn("潘多拉", first.summary)
        self.assertEqual(first.url, BASE + "/detail/123.html")

    def test_dedup_and_href_filter(self):
        results = list(_iter_search_results(SEARCH_HTML, BASE, limit=10))
        ids = [r.detail_id for r in results]
        self.assertEqual(ids, ["123", "456"])  # 重复 123 与 /other/ 都被去掉

    def test_limit(self):
        results = list(_iter_search_results(SEARCH_HTML, BASE, limit=1))
        self.assertEqual(len(results), 1)


class TestIterResources(unittest.TestCase):
    def test_parse_fields(self):
        resources = list(_iter_resources(RESOURCES_HTML, BASE))
        self.assertEqual(len(resources), 2)
        first = resources[0]
        self.assertEqual(first.tdown_id, "55")
        # 标题去掉《...》前缀
        self.assertFalse(first.title.startswith("《"))
        self.assertIn("2160p", first.title)
        self.assertEqual(first.size, "14.97GB")
        self.assertEqual(first.downloads, "237")
        self.assertEqual(first.url, BASE + "/tdown/55.html")


class TestParseSize(unittest.TestCase):
    def test_units(self):
        self.assertEqual(_parse_size("xx 47.95GB yy"), "47.95GB")
        self.assertEqual(_parse_size("800MB"), "800MB")
        self.assertEqual(_parse_size("没有体积"), "")


class TestExtractDownloadLinks(unittest.TestCase):
    def test_magnet_thunder_extras(self):
        magnet, thunder, extras = _extract_download_links(DOWNLOAD_HTML)
        self.assertTrue(magnet.startswith("magnet:?xt=urn:btih:ea5a"))
        self.assertEqual(thunder, "/dlt/12345.html")
        self.assertEqual(extras, ["https://pan.example.com/s/abc"])

    def test_empty_page(self):
        magnet, thunder, extras = _extract_download_links("<html></html>")
        self.assertEqual((magnet, thunder, extras), ("", "", []))


if __name__ == "__main__":
    unittest.main()
