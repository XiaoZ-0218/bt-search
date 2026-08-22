"""bt_search.sources.knaben 的纯 HTML 解析测试（离线）。"""

from __future__ import annotations

import unittest

from bt_search.sources.knaben import _iter_hits

BASE = "https://knaben.org"

SEARCH_HTML = """
<table>
  <tr class="text-nowrap" data-id="9a384d74548884dc4ae9c4ebe1911c402251135a">
    <td>TV</td>
    <td class="text-wrap w-100">
      <a href="magnet:?xt=urn:btih:9a384d74548884dc4ae9c4ebe1911c402251135a&amp;dn=Earth"
         title="[DBD-Raws][流浪地球][1080P][简体内封]">[DBD-Raws][流浪地球][1080P][简体内封]</a>
    </td>
    <td>5 GB</td>
    <td>2021-10-16</td>
    <td>17</td>
  </tr>
  <tr class="text-nowrap" data-id="9a384d74548884dc4ae9c4ebe1911c402251135a">
    <td>TV</td>
    <td class="text-wrap w-100">
      <a href="magnet:?xt=urn:btih:9a384d74548884dc4ae9c4ebe1911c402251135a" title="重复哈希">重复哈希</a>
    </td>
    <td>5 GB</td>
  </tr>
  <tr><td>无磁力</td></tr>
</table>
"""


class TestIterHits(unittest.TestCase):
    def test_parse_fields(self):
        hits = _iter_hits(SEARCH_HTML, BASE)
        self.assertEqual(len(hits), 1)
        hit = hits[0]
        self.assertIn("流浪地球", hit.title)
        self.assertEqual(hit.size, "5GB")
        self.assertTrue(hit.magnet.startswith("magnet:?xt=urn:btih:9a384d74"))
        self.assertIn("&dn=", hit.magnet)

    def test_empty_page(self):
        self.assertEqual(_iter_hits("<html></html>", BASE), [])


if __name__ == "__main__":
    unittest.main()
