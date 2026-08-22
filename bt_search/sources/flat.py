"""扁平磁力源共用：命中数据类 + 首次非空缓存 + magnet 直出。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional
from urllib.parse import urljoin

import requests

from ..scraper import DEFAULT_USER_AGENT, DownloadLink, ResourceItem, SearchResult
from ..source import BTSource

_BTIH_RE = re.compile(r"xt=urn:btih:([A-Za-z0-9]+)", re.IGNORECASE)


@dataclass
class MagnetHit:
    title: str
    size: str = ""
    detail_url: str = ""
    magnet: str = ""


def magnet_hash(magnet: str) -> str:
    m = _BTIH_RE.search(magnet)
    return m.group(1).upper() if m else ""


class CachedFlatSource(BTSource):
    """一次搜索即出种子列表的扁平源。"""

    def __init__(
        self,
        base_url: str,
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
        self._hits: List[MagnetHit] = []

    def _get(self, url: str) -> str:
        if not url.startswith("http"):
            url = urljoin(self.base_url + "/", url.lstrip("/"))
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text

    def search_url(self, keyword: str) -> str:
        raise NotImplementedError

    def parse_hits(self, html: str) -> List[MagnetHit]:
        raise NotImplementedError

    def search(self, keyword: str, *, limit: int = 20) -> List[SearchResult]:
        if not keyword or not keyword.strip():
            return []
        html = self._get(self.search_url(keyword.strip()))
        hits = self.parse_hits(html)[:limit]
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
                summary=f"{self.name} 搜索到的 {n} 条种子，详见资源列表",
                complete=True,
            )
        ]

    def fetch_resources(self, detail_id: str) -> List[ResourceItem]:
        if not self._hits:
            raise requests.RequestException(f"{self.name} 未缓存搜索结果")
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
        if not tdown_id.startswith("magnet:"):
            raise ValueError(f"{self.name} 的 tdown_id 必须是 magnet 链接")
        return DownloadLink(tdown_id=tdown_id, magnet=tdown_id)


def parse_magnet_rows(
    html: str,
    *,
    pick: Callable[..., Optional[MagnetHit]],
) -> List[MagnetHit]:
    """遍历所有 magnet 锚点所在行，按 info hash 去重。"""

    from bs4 import BeautifulSoup, Tag

    soup = BeautifulSoup(html, "html.parser")
    hits: List[MagnetHit] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href.startswith("magnet:"):
            continue
        row = anchor.find_parent("tr")
        if not isinstance(row, Tag):
            continue
        hit = pick(row, href)
        if hit is None:
            continue
        key = magnet_hash(hit.magnet) or hit.magnet
        if key in seen:
            continue
        seen.add(key)
        hits.append(hit)
    return hits
