"""torrentkitty.net 站点实现。

扁平磁力搜索引擎：一次搜索直接命中一堆种子（标题 / 大小 / 日期 / magnet），
没有"影片 → 资源版本"的两级结构。因此这里把整页命中当作一部"影片"的
资源列表：search 返回一条合成结果，fetch_resources 返回全部命中（缓存本次
搜索结果），fetch_download 直接返回 magnet。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup, Tag

from ..scraper import (
    DEFAULT_USER_AGENT,
    DownloadLink,
    ResourceItem,
    SearchResult,
    _parse_size,
)
from ..source import BTSource

BASE_URL = "https://www.torrentkitty.net"


@dataclass
class _KittyHit:
    """一条搜索结果：种子名 / 大小 / 详情页 / magnet。"""

    title: str
    size: str
    detail_url: str
    magnet: str


def _iter_hits(html: str, base_url: str) -> List[_KittyHit]:
    """解析搜索结果表格行（标题 / 大小 / 日期 / Detail + magnet 链接）。

    只取表头为 "Torrent Description" 的结果表，避免侧栏其它表格混入；
    行内字段按 ``td.name / td.size`` class 定位。
    """

    soup = BeautifulSoup(html, "html.parser")
    table = None
    for t in soup.find_all("table"):
        th = t.find("th")
        if isinstance(th, Tag) and "Description" in th.get_text(" ", strip=True):
            table = t
            break
    if table is None:
        return []

    hits: List[_KittyHit] = []
    seen: set[str] = set()
    for row in table.select("tr"):
        detail_a = row.select_one('a[rel="information"]')
        if not isinstance(detail_a, Tag):
            continue
        href = str(detail_a.get("href", "")).strip()
        m = re.match(r"^/information/([0-9A-Fa-f]{40})$", href)
        if not m:
            continue
        info_hash = m.group(1).upper()
        magnet_a = row.select_one('a[href^="magnet:"]')
        magnet = str(magnet_a["href"]).strip() if isinstance(magnet_a, Tag) else ""
        if not magnet:
            continue
        if info_hash in seen:
            continue
        seen.add(info_hash)

        name_td = row.select_one("td.name")
        size_td = row.select_one("td.size")
        title = (
            str(detail_a.get("title") or detail_a.get_text(" ", strip=True)).strip()
        )
        if isinstance(name_td, Tag) and name_td.get_text(" ", strip=True):
            title = name_td.get_text(" ", strip=True)
        size = (
            _parse_size(size_td.get_text(" ", strip=True))
            if isinstance(size_td, Tag)
            else ""
        )

        hits.append(
            _KittyHit(
                title=title,
                size=size,
                detail_url=urljoin(base_url + "/", href.lstrip("/")),
                magnet=magnet,
            )
        )
    return hits


class TorrentKittySource(BTSource):
    """torrentkitty.net 的 BTSource 实现（扁平磁力引擎）。"""

    def __init__(
        self,
        base_url: str = BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 15.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        self._hits: List[_KittyHit] = []  # 首次非空搜索的命中缓存（单次运行内有效）

    @property
    def name(self) -> str:
        return "torrentkitty.net"

    # ---------- HTTP helpers ----------
    def _get(self, path: str) -> str:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text

    # ---------- BTSource API ----------
    def search(self, keyword: str, *, limit: int = 20) -> List[SearchResult]:
        """搜索并缓存命中；返回一条合成结果（整页命中即资源列表）。

        关键词 fallback 会连续调多次 search，只缓存**首个非空**查询的命中——
        与 search_with_fallback 去重后保留的合成结果（detail_id="all"）保持一致，
        否则 fetch_resources 会拿到最后一次查询的命中。
        """

        if not keyword or not keyword.strip():
            return []
        html = self._get(f"/search/{quote(keyword.strip())}")
        hits = _iter_hits(html, self.base_url)[:limit]
        if hits and not self._hits:
            self._hits = hits
        if not hits:
            return []
        n = len(self._hits)
        return [
            SearchResult(
                detail_id="all",
                title=f"「{keyword.strip()}」共 {n} 条磁力资源",
                url=self.base_url,
                summary=f"torrentkitty 搜索到的 {n} 条种子，详见资源列表",
                complete=True,
            )
        ]

    def fetch_resources(self, detail_id: str) -> List[ResourceItem]:
        """返回本次搜索缓存的全部命中（带大小，供挑选）。"""

        if not self._hits:
            raise requests.RequestException("torrentkitty 未缓存搜索结果")
        return [
            ResourceItem(
                tdown_id=hit.magnet,
                title=hit.title,
                size=hit.size,
                url=hit.detail_url,
            )
            for hit in self._hits
        ]

    def fetch_download(self, tdown_id: str) -> DownloadLink:
        """magnet 即最终链接，直接返回。"""

        if not tdown_id.startswith("magnet:"):
            raise ValueError(f"{self.name} 的 tdown_id 必须是 magnet 链接")
        return DownloadLink(tdown_id=tdown_id, magnet=tdown_id)
