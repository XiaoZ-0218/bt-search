"""bt_search.sources.torrentkitty 的纯 HTML 解析测试（离线，不打网络）。

HTML 片段取自实测抓取的 torrentkitty.net 搜索结果页，裁剪到最小结构。
注意 magnet href 里的 &amp; 会被 BeautifulSoup 反转义成 &。
"""

from __future__ import annotations

import unittest

from bt_search.sources.torrentkitty import _iter_hits

BASE = "https://www.torrentkitty.net"

SEARCH_HTML = """
<table>
  <tr><th>Torrent Description</th><th>Torrent Size</th><th>Upload Date</th></tr>
  <tr>
    <td class="name">【高清剧集网发布 www.QQHDTV.com】吞噬星空.第4季[第235集][无字片源].Swallowed.Star.2021.1080p.WEB-DL.H264.AAC-ColorWEB</td>
    <td class="size">8.39 mb</td>
    <td class="date">2026-08-03</td>
    <td class="action">
      <a href="/information/0B2BA3D65BBAA7C548FDBBB78F5258564B8C8091" rel="information" title="【高清剧集网发布 www.QQHDTV.com】吞噬星空.第4季[第235集][无字片源].Swallowed.Star.2021.1080p.WEB-DL.H264.AAC-ColorWEB">Detail</a>
      <a href="magnet:?xt=urn:btih:0B2BA3D65BBAA7C548FDBBB78F5258564B8C8091&amp;dn=%E5%90%9E%E5%99%AC%E6%98%9F%E7%A9%BA">Open</a>
    </td>
  </tr>
  <tr>
    <td class="name">Swallowed.2022.1080p.WEBRip.x264-LAMA</td>
    <td class="size">1.82 GB</td>
    <td class="date">2026-08-01</td>
    <td class="action">
      <a href="/information/F008DD70FB2739B1B4197C1B66FEC8F62B25DDF8" rel="information" title="Swallowed.2022.1080p.WEBRip.x264-LAMA">Detail</a>
      <a href="magnet:?xt=urn:btih:F008DD70FB2739B1B4197C1B66FEC8F62B25DDF8&amp;dn=Swallowed.2022.1080p.WEBRip.x264-LAMA">Open</a>
    </td>
  </tr>
  <tr>
    <td class="name">重复哈希那行</td>
    <td class="size">999 mb</td>
    <td class="date">2026-08-01</td>
    <td class="action">
      <a href="/information/F008DD70FB2739B1B4197C1B66FEC8F62B25DDF8" rel="information" title="重复哈希那行">Detail</a>
      <a href="magnet:?xt=urn:btih:F008DD70FB2739B1B4197C1B66FEC8F62B25DDF8">Open</a>
    </td>
  </tr>
</table>
<table>
  <tr><th>Torrent Description</th><th>Torrent Size</th><th>Upload Date</th></tr>
  <tr>
    <td class="name">侧栏表格不应混入</td>
    <td class="size">2.2 MB</td>
    <td class="date">2026-01-01</td>
    <td class="action">
      <a href="/information/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" rel="information" title="侧栏表格不应混入">Detail</a>
      <a href="magnet:?xt=urn:btih:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA">Open</a>
    </td>
  </tr>
</table>
"""


class TestIterHits(unittest.TestCase):
    def test_parse_fields(self):
        hits = _iter_hits(SEARCH_HTML, BASE)
        self.assertEqual(len(hits), 2)  # 相同 info hash 的行被去重
        first, second = hits
        self.assertEqual(first.title, "【高清剧集网发布 www.QQHDTV.com】吞噬星空.第4季[第235集][无字片源].Swallowed.Star.2021.1080p.WEB-DL.H264.AAC-ColorWEB")
        self.assertEqual(first.size, "8.39MB")  # "8.39 mb" 归一化
        self.assertEqual(first.detail_url, BASE + "/information/0B2BA3D65BBAA7C548FDBBB78F5258564B8C8091")
        self.assertTrue(first.magnet.startswith("magnet:?xt=urn:btih:0B2BA3"))
        self.assertIn("&dn=", first.magnet)  # &amp; 已被反转义
        self.assertEqual(second.size, "1.82GB")

    def test_empty_page(self):
        self.assertEqual(_iter_hits("<html></html>", BASE), [])


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        pass


class _FakeSession:
    """按 URL 片段返回预设页面的假 session。"""

    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.headers: dict[str, str] = {}

    def get(self, url: str, timeout=None):
        for fragment, text in self.pages.items():
            if fragment in url:
                return _FakeResponse(text)
        raise AssertionError(f"unexpected url: {url}")

    def post(self, *args, **kwargs):  # pragma: no cover - 本测试不用
        raise AssertionError("no post expected")


SECOND_QUERY_HTML = """
<table>
  <tr><th>Torrent Description</th><th>Torrent Size</th><th>Upload Date</th></tr>
  <tr>
    <td class="name">第二次查询的命中</td>
    <td class="size">5 GB</td>
    <td class="date">2026-01-01</td>
    <td class="action">
      <a href="/information/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB" rel="information" title="第二次查询的命中">Detail</a>
      <a href="magnet:?xt=urn:btih:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB">Open</a>
    </td>
  </tr>
</table>
"""


class TestSourceFallback(unittest.TestCase):
    def test_fallback_keeps_first_query_hits(self):
        # 关键词 fallback 会连续调多次 search，缓存只保留首个非空查询的命中
        session = _FakeSession(
            {
                "/search/Swallowed%202022": SEARCH_HTML,
                "/search/Swallowed": SECOND_QUERY_HTML,
            }
        )
        from bt_search.sources.torrentkitty import TorrentKittySource

        src = TorrentKittySource(session=session)
        src.search("Swallowed 2022")
        src.search("Swallowed")  # 第二次查询不应覆盖缓存
        resources = src.fetch_resources("all")
        self.assertEqual(len(resources), 2)
        self.assertIn("Swallowed.2022.1080p.WEBRip", resources[1].title)
        self.assertNotIn("第二次查询的命中", [r.title for r in resources])

    def test_empty_followup_query_returns_empty_keeps_cache(self):
        session = _FakeSession(
            {
                "/search/Swallowed%202022": SEARCH_HTML,
                "/search/Nope": "<html></html>",
            }
        )
        from bt_search.sources.torrentkitty import TorrentKittySource

        src = TorrentKittySource(session=session)
        self.assertEqual(len(src.search("Swallowed 2022")), 1)
        self.assertEqual(src.search("Nope"), [])
        self.assertEqual(len(src.fetch_resources("all")), 2)

    def test_fetch_download_rejects_non_magnet_id(self):
        from bt_search.sources.torrentkitty import TorrentKittySource

        with self.assertRaises(ValueError):
            TorrentKittySource().fetch_download("55")


if __name__ == "__main__":
    unittest.main()
