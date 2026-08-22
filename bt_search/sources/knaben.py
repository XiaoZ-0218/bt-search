"""knaben.org 站点实现（扁平磁力引擎）。"""

from __future__ import annotations

from typing import List, Optional
from urllib.parse import quote

from bs4 import Tag

from ..scraper import _parse_size
from .flat import CachedFlatSource, MagnetHit, parse_magnet_rows

BASE_URL = "https://knaben.org"


def _iter_hits(html: str, base_url: str = BASE_URL) -> List[MagnetHit]:
    def pick(row: Tag, magnet: str) -> Optional[MagnetHit]:
        title_a = row.select_one('a[href^="magnet:"]')
        if not isinstance(title_a, Tag):
            return None
        title = str(title_a.get("title") or title_a.get_text(" ", strip=True)).strip()
        tds = row.find_all("td", recursive=False)
        size = _parse_size(tds[2].get_text(" ", strip=True)) if len(tds) > 2 else ""
        return MagnetHit(title=title or magnet, size=size, magnet=magnet)

    return parse_magnet_rows(html, pick=pick)


class KnabenSource(CachedFlatSource):
    """knaben.org 的扁平磁力搜索。"""

    def __init__(self, base_url: str = BASE_URL, **kwargs) -> None:
        super().__init__(base_url, **kwargs)

    @property
    def name(self) -> str:
        return "knaben.org"

    def search_url(self, keyword: str) -> str:
        return f"{self.base_url}/search/{quote(keyword)}/0/1/seeders"

    def parse_hits(self, html: str) -> List[MagnetHit]:
        return _iter_hits(html, self.base_url)
