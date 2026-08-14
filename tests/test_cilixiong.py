"""bt_search.sources.cilixiong 的纯 HTML 解析测试（离线，不打网络）。

HTML 片段取自实测抓取的 cilixiong.org 页面，裁剪到最小结构。
"""

from __future__ import annotations

import unittest

from bt_search.sources.cilixiong import _iter_magnets, _iter_movies

BASE = "https://www.cilixiong.org"

SEARCH_HTML = """
<div class="col">
  <div class="card card-cover h-100 overflow-hidden text-bg-dark rounded-4 shadow-lg position-relative">
    <a href="/movie/4167.html">
      <div class="card-img" style="background-image: url('https://i.nacloud.cc/2019/06092.webp');"></div>
      <div class="card-body position-absolute d-flex w-100 flex-column text-white">
        <h2 class="pt-5 lh-1 pb-2 h4">流浪地球2：再次冒险</h2>
        <ul class="d-flex list-unstyled mb-0">
          <li class="me-auto"><span class="rank bg-success p-1">9.0</span></li>
          <li class="d-flex align-items-center small">2024</li>
        </ul>
      </div>
    </a>
  </div>
</div>
<div class="col">
  <div class="card ...">
    <a href="/movie/2959.html">
      <div class="card-body ...">
        <h2 class="...">流浪地球2</h2>
        <ul class="...">
          <li class="me-auto"><span class="rank bg-success p-1">8.3</span></li>
          <li class="d-flex align-items-center small">2023</li>
        </ul>
      </div>
    </a>
  </div>
</div>
<a href="/movie/">电影</a>
"""

DETAIL_HTML = """
<a href="magnet:?xt=urn:btih:5953ad5284d10d48edb2a3f0b2e665b082d16959">
 The.Wandering.Earth.Ⅱ.2023.1080p.WEB-DL.H265.DDP5.1-DreamHD[3.48G]
</a>
<a href="magnet:?xt=urn:btih:b40ccf8a5f65dd9363ae24bd716fe01a567bc444">The.Wandering.Earth.II.2023.HD1080P.X264.AAC.Mandarin.CHS.BD[1.96GB]</a>
<a href="magnet:?xt=urn:btih:5953ad5284d10d48edb2a3f0b2e665b082d16959">
 The.Wandering.Earth.Ⅱ.2023.1080p.WEB-DL.H265.DDP5.1-DreamHD[3.48G]
</a>
"""


class TestIterMovies(unittest.TestCase):
    def test_parse_fields(self):
        movies = list(_iter_movies(SEARCH_HTML, BASE, limit=10))
        self.assertEqual(len(movies), 2)
        first = movies[0]
        self.assertEqual(first.detail_id, "4167")
        self.assertEqual(first.title, "流浪地球2：再次冒险")
        self.assertEqual(first.year, "2024")
        self.assertIn("9.0", first.summary)
        self.assertEqual(first.url, BASE + "/movie/4167.html")

    def test_ignore_nav_links_and_dedup(self):
        movies = list(_iter_movies(SEARCH_HTML, BASE, limit=10))
        self.assertEqual([m.detail_id for m in movies], ["4167", "2959"])

    def test_limit(self):
        movies = list(_iter_movies(SEARCH_HTML, BASE, limit=1))
        self.assertEqual(len(movies), 1)


class TestIterMagnets(unittest.TestCase):
    def test_parse_fields(self):
        items = list(_iter_magnets(DETAIL_HTML))
        self.assertEqual(len(items), 2)  # 重复的 magnet 被去重
        first = items[0]
        self.assertTrue(first.tdown_id.startswith("magnet:?xt=urn:btih:5953ad"))
        self.assertEqual(first.title, "The.Wandering.Earth.Ⅱ.2023.1080p.WEB-DL.H265.DDP5.1-DreamHD")
        self.assertEqual(first.size, "3.48GB")  # "3.48G" 归一化为 GB
        self.assertEqual(items[1].size, "1.96GB")

    def test_empty_page(self):
        self.assertEqual(list(_iter_magnets("<html></html>")), [])


if __name__ == "__main__":
    unittest.main()
