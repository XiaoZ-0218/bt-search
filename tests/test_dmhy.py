"""bt_search.sources.dmhy 的纯 HTML 解析测试（离线）。"""

from __future__ import annotations

import unittest

from bt_search.sources.dmhy import _iter_hits

BASE = "https://share.dmhy.org"

SEARCH_HTML = """
<table id="topic_list">
  <tr>
    <td>2026/08/15 23:20</td>
    <td>季度全集</td>
    <td class="title">
      <a href="/topics/view/724949_Frieren.html" target="_blank">
        [Shiniori-Raws] <span class="keyword">葬送的芙莉莲</span> 第二季 (BD 1920x1080)
      </a>
    </td>
    <td>
      <a class="download-arrow arrow-magnet" href="magnet:?xt=urn:btih:JSTYORPG2DEE3SFUNTLJ3VQFXPN6OKEB&amp;dn=&amp;tr=http%3A%2F%2Ftracker">磁力</a>
    </td>
    <td>17.7GB</td>
    <td>-</td>
  </tr>
  <tr>
    <td>2026/08/14</td>
    <td>動畫</td>
    <td class="title">
      <a href="/topics/view/1.html">重复哈希</a>
    </td>
    <td>
      <a href="magnet:?xt=urn:btih:JSTYORPG2DEE3SFUNTLJ3VQFXPN6OKEB">磁力</a>
    </td>
    <td>1GB</td>
  </tr>
</table>
"""


class TestIterHits(unittest.TestCase):
    def test_parse_fields(self):
        hits = _iter_hits(SEARCH_HTML, BASE)
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertIn("葬送的芙莉莲", hit.title)
        self.assertEqual(hit.size, "17.7GB")
        self.assertTrue(hit.magnet.startswith("magnet:?xt=urn:btih:JSTYORPG"))
        self.assertEqual(hit.detail_url, BASE + "/topics/view/724949_Frieren.html")

    def test_empty_page(self):
        self.assertEqual(_iter_hits("<html></html>", BASE), [])


if __name__ == "__main__":
    unittest.main()
