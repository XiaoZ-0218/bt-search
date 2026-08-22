"""bt_search.sources.nyaa 的纯 HTML 解析测试（离线）。"""

from __future__ import annotations

import unittest

from bt_search.sources.nyaa import _iter_hits

BASE = "https://nyaa.si"

SEARCH_HTML = """
<table class="torrent-list">
  <tr class="default">
    <td></td>
    <td colspan="2">
      <a href="/view/1900784#comments">1</a>
      <a href="/view/1900784" title="[DBD-Raws][4K_HDR][流浪地球2][2160P][简体内封]">[DBD-Raws][4K_HDR][流浪地球2][2160P][简体内封]</a>
    </td>
    <td class="text-center">
      <a href="/download/1900784.torrent">dl</a>
      <a href="magnet:?xt=urn:btih:381e27fc1b57100a1b75bae8745896cba522024b&amp;dn=Earth2">mag</a>
    </td>
    <td class="text-center">17.5 GiB</td>
    <td class="text-center">2024-11-17</td>
    <td class="text-center">3</td>
  </tr>
  <tr class="default">
    <td></td>
    <td colspan="2">
      <a href="/view/1900784" title="重复哈希">重复哈希</a>
    </td>
    <td class="text-center">
      <a href="magnet:?xt=urn:btih:381e27fc1b57100a1b75bae8745896cba522024b">mag</a>
    </td>
    <td class="text-center">1 GiB</td>
  </tr>
</table>
"""


class TestIterHits(unittest.TestCase):
    def test_parse_fields(self):
        hits = _iter_hits(SEARCH_HTML, BASE)
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertIn("流浪地球2", hit.title)
        self.assertNotEqual(hit.title, "1")
        self.assertEqual(hit.size, "17.5GB")
        self.assertTrue(hit.magnet.startswith("magnet:?xt=urn:btih:381e27fc"))
        self.assertEqual(hit.detail_url, BASE + "/view/1900784")

    def test_empty_page(self):
        self.assertEqual(_iter_hits("<html></html>", BASE), [])


if __name__ == "__main__":
    unittest.main()
