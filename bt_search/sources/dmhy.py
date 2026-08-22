"""share.dmhy.org（动漫花园）站点实现（扁平磁力引擎）。"""

from __future__ import annotations

from typing import List, Optional
from urllib.parse import quote, urljoin

from bs4 import Tag

from ..scraper import _parse_size
from .flat import CachedFlatSource, MagnetHit, parse_magnet_rows

BASE_URL = "https://share.dmhy.org"


def _iter_hits(html: str, base_url: str = BASE_URL) -> List[MagnetHit]:
    def pick(row: Tag, magnet: str) -> Optional[MagnetHit]:
        title_a = row.select_one("td.title a[href]")
        if not isinstance(title_a, Tag):
            return None
        title = title_a.get_text(" ", strip=True)
        href = str(title_a.get("href", "")).strip()
        size = ""
        for td in row.find_all("td"):
            parsed = _parse_size(td.get_text(" ", strip=True))
            if parsed:
                size = parsed
                break
        return MagnetHit(
            title=title or magnet,
            size=size,
            detail_url=urljoin(base_url + "/", href.lstrip("/")),
            magnet=magnet,
        )

    return parse_magnet_rows(html, pick=pick)


class DmhySource(CachedFlatSource):
    """动漫花园的扁平磁力搜索。"""

    def __init__(self, base_url: str = BASE_URL, **kwargs) -> None:
        super().__init__(base_url, **kwargs)

    @property
    def name(self) -> str:
        return "share.dmhy.org"

    def search_url(self, keyword: str) -> str:
        return f"{self.base_url}/topics/list?keyword={quote(keyword)}"

    def parse_hits(self, html: str) -> List[MagnetHit]:
        return _iter_hits(html, self.base_url)
