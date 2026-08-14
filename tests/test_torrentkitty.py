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
    <td>【高清剧集网发布 www.QQHDTV.com】吞噬星空.第4季[第235集][无字片源].Swallowed.Star.2021.1080p.WEB-DL.H264.AAC-ColorWEB</td>
    <td>8.39 mb</td>
    <td>2026-08-03</td>
    <td class="action">
      <a href="/information/0B2BA3D65BBAA7C548FDBBB78F5258564B8C8091" rel="information" title="【高清剧集网发布 www.QQHDTV.com】吞噬星空.第4季[第235集][无字片源].Swallowed.Star.2021.1080p.WEB-DL.H264.AAC-ColorWEB">Detail</a>
      <a href="magnet:?xt=urn:btih:0B2BA3D65BBAA7C548FDBBB78F5258564B8C8091&amp;dn=%E5%90%9E%E5%99%AC%E6%98%9F%E7%A9%BA">Open</a>
    </td>
  </tr>
  <tr>
    <td>Swallowed.2022.1080p.WEBRip.x264-LAMA</td>
    <td>1.82 GB</td>
    <td>2026-08-01</td>
    <td class="action">
      <a href="/information/F008DD70FB2739B1B4197C1B66FEC8F62B25DDF8" rel="information" title="Swallowed.2022.1080p.WEBRip.x264-LAMA">Detail</a>
      <a href="magnet:?xt=urn:btih:F008DD70FB2739B1B4197C1B66FEC8F62B25DDF8&amp;dn=Swallowed.2022.1080p.WEBRip.x264-LAMA">Open</a>
    </td>
  </tr>
  <tr>
    <td>重复哈希那行</td>
    <td>999 mb</td>
    <td>2026-08-01</td>
    <td class="action">
      <a href="/information/F008DD70FB2739B1B4197C1B66FEC8F62B25DDF8" rel="information" title="重复哈希那行">Detail</a>
      <a href="magnet:?xt=urn:btih:F008DD70FB2739B1B4197C1B66FEC8F62B25DDF8">Open</a>
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


if __name__ == "__main__":
    unittest.main()
