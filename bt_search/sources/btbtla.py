"""btbtla.com 站点实现。

所有网络请求共用一个 ``requests.Session``，附带浏览器 UA 与 Referer，
减少被反爬挡掉的概率。HTML 解析函数在 ``bt_search.scraper`` 里。
"""

from __future__ import annotations

from typing import List, Optional
from urllib.parse import quote, urljoin

import requests

from ..scraper import (
    DEFAULT_BASE_URL,
    DEFAULT_USER_AGENT,
    DownloadLink,
    ResourceItem,
    SearchResult,
    _extract_download_links,
    _iter_resources,
    _iter_search_results,
)
from ..source import BTSource


class BtbtlaSource(BTSource):
    """btbtla.com 的 BTSource 实现。"""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
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

    @property
    def name(self) -> str:
        return "btbtla.com"

    # ---------- HTTP helpers ----------
    def _get(self, path: str, *, referer: Optional[str] = None) -> str:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        headers = {}
        if referer:
            headers["Referer"] = referer
        resp = self.session.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        # 站点输出 utf-8，强制按 utf-8 解码，避免 chardet 误判
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    # ---------- BTSource API ----------
    def search(self, keyword: str, *, limit: int = 20) -> List[SearchResult]:
        """按关键词搜索影片。"""

        if not keyword or not keyword.strip():
            return []
        path = f"/search/{quote(keyword.strip())}"
        html = self._get(path)
        return list(_iter_search_results(html, self.base_url, limit=limit))

    def fetch_resources(self, detail_id: str) -> List[ResourceItem]:
        """拉取某部影片详情页下方的资源版本列表。"""

        html = self._get(f"/detail/{detail_id}.html")
        return list(_iter_resources(html, self.base_url))

    def fetch_download(self, tdown_id: str) -> DownloadLink:
        """拉取某条资源的下载链接（含 magnet）。"""

        html = self._get(f"/tdown/{tdown_id}.html")
        magnet, thunder, extras = _extract_download_links(html)
        return DownloadLink(tdown_id=tdown_id, magnet=magnet, thunder=thunder, extras=extras)

    # ---------- 便捷方法 ----------
    def get_first_magnet(self, keyword: str) -> Optional[DownloadLink]:
        """便捷方法：返回搜索结果第一名 / 第一个资源的 magnet（如有）。"""

        results = self.search(keyword, limit=1)
        if not results:
            return None
        resources = self.fetch_resources(results[0].detail_id)
        if not resources:
            return None
        return self.fetch_download(resources[0].tdown_id)
