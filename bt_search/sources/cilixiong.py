"""cilixiong.org（磁力熊）站点实现。

与 btbtla 同构的影片站：搜索 → 影片列表 → 详情页直接带 magnet 链接。
搜索走 POST（Empire CMS 的 /e/search/index.php，需要带完整表单字段否则返回空），
详情页的 magnet 锚点就是最终链接，因此 fetch_download 直接返回 magnet，无需再请求。
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from ..scraper import DEFAULT_USER_AGENT, DownloadLink, ResourceItem, SearchResult
from ..source import BTSource

BASE_URL = "https://www.cilixiong.org"

_SEARCH_FORM = {
    "classid": "1,2",  # 电影 + 剧集分类
    "show": "title",
    "tempid": "1",
    "keyboard": "",  # 关键词
}
_MOVIE_RE = re.compile(r"^/movie/(\d+)\.html$")
_SIZE_RE = re.compile(r"\[([\d.]+)\s*([TGKM]B?)\]")


def _iter_movies(html: str, base_url: str, *, limit: int) -> Iterable[SearchResult]:
    """解析搜索结果页的影片卡片（标题 / 评分 / 年份）。"""

    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    for anchor in soup.select('a[href^="/movie/"]'):
        href = anchor.get("href", "")
        m = _MOVIE_RE.match(str(href).strip())
        if not m:
            continue
        detail_id = m.group(1)
        if detail_id in seen:
            continue
        seen.add(detail_id)

        h2 = anchor.select_one("h2")
        title = h2.get_text(" ", strip=True) if isinstance(h2, Tag) else ""
        title = title or anchor.get_text(" ", strip=True)
        rank_el = anchor.select_one(".rank")
        year_el = anchor.select_one("li.small")

        yield SearchResult(
            detail_id=detail_id,
            title=title.strip(),
            url=urljoin(base_url + "/", href.lstrip("/")),
            year=year_el.get_text(" ", strip=True) if isinstance(year_el, Tag) else "",
            summary=(
                f"评分 {rank_el.get_text(strip=True)}"
                if isinstance(rank_el, Tag) and rank_el.get_text(strip=True)
                else ""
            ),
        )
        if len(seen) >= limit:
            break


def _iter_magnets(html: str) -> Iterable[ResourceItem]:
    """解析详情页的 magnet 锚点为资源条目（标题带 [3.48G] 大小后缀）。"""

    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href.startswith("magnet:"):
            continue
        if href in seen:
            continue
        seen.add(href)

        title = anchor.get_text(" ", strip=True)
        size = ""
        m = _SIZE_RE.search(title)
        if m:
            unit = m.group(2).upper()
            size = f"{m.group(1)}{unit}" + ("" if unit.endswith("B") else "B")
            title = (title[: m.start()] + title[m.end():]).strip()

        yield ResourceItem(tdown_id=href, title=title or href, size=size, url=href)


class CilixiongSource(BTSource):
    """cilixiong.org（磁力熊）的 BTSource 实现。"""

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

    @property
    def name(self) -> str:
        return "cilixiong.org"

    # ---------- HTTP helpers ----------
    def _get(self, path: str) -> str:
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    # ---------- BTSource API ----------
    def search(self, keyword: str, *, limit: int = 20) -> List[SearchResult]:
        """按关键词搜索影片（Empire CMS POST，302 后跟到结果页）。"""

        if not keyword or not keyword.strip():
            return []
        data = dict(_SEARCH_FORM, keyboard=keyword.strip())
        resp = self.session.post(
            urljoin(self.base_url + "/", "e/search/index.php"),
            data=data,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        return list(_iter_movies(resp.text, self.base_url, limit=limit))

    def fetch_resources(self, detail_id: str) -> List[ResourceItem]:
        """拉取影片详情页的 magnet 版本列表。"""

        html = self._get(f"/movie/{detail_id}.html")
        return list(_iter_magnets(html))

    def fetch_download(self, tdown_id: str) -> DownloadLink:
        """详情页 magnet 即最终链接，直接返回。"""

        return DownloadLink(tdown_id=tdown_id, magnet=tdown_id)
