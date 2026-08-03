"""btbtla.com 的数据类与 HTML 解析函数。

数据类：
    SearchResult  —— 搜索结果中的一项影片
    ResourceItem  —— 某部影片下的一条资源版本
    DownloadLink  —— 下载页里能直接拿来下载的链接集合

站点实现（HTTP 请求）在 ``bt_search.sources.btbtla.BtbtlaSource``，
本模块只保留纯解析逻辑，方便独立测试与复用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

DEFAULT_BASE_URL = "https://www.btbtla.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class SearchResult:
    """搜索结果中的一项影片。"""

    detail_id: str
    title: str
    url: str
    category: str = ""
    year: str = ""
    region: str = ""
    summary: str = ""


@dataclass
class ResourceItem:
    """某部影片下的一条资源版本（如 4K Remux / 1080p 等）。"""

    tdown_id: str
    title: str  # 资源标题，来自详情页 title 属性
    size: str = ""  # 文件大小，例如 47.95GB
    downloads: str = ""  # 下载量
    url: str = ""


@dataclass
class DownloadLink:
    """下载页里能直接拿来下载的链接集合。"""

    tdown_id: str
    magnet: str = ""
    thunder: str = ""  # /dlt/... 形式的迅雷链接
    extras: List[str] = field(default_factory=list)  # 其它直链或网盘


# ---------- Parsing helpers ----------
def _text(node: Tag, selector: str) -> str:
    """便捷：在节点里查找 selector 并取其纯文本。"""

    el = node.select_one(selector)
    return el.get_text(" ", strip=True) if isinstance(el, Tag) else ""


def _iter_search_results(html: str, base_url: str, *, limit: int) -> Iterable[SearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    for anchor in soup.select("a.module-item-title"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href", "")
        m = re.match(r"^/detail/(\d+)\.html$", str(href).strip())
        if not m:
            continue
        detail_id = m.group(1)
        if detail_id in seen:
            continue
        seen.add(detail_id)

        title = anchor.get("title") or anchor.get_text(strip=True)
        card = anchor.find_parent(class_="module-item") or anchor
        category = _text(card, ".video-class")
        year, region = _parse_year_region(card)
        summary = _text(card, ".video-text")

        yield SearchResult(
            detail_id=detail_id,
            title=title.strip(),
            url=urljoin(base_url + "/", href.lstrip("/")),
            category=category,
            year=year,
            region=region,
            summary=summary,
        )
        if len(seen) >= limit:
            break


def _parse_year_region(card: Tag) -> tuple[str, str]:
    """解析详情里类似 '2026 中国大陆' 的短文本。

    优先抓 btbtla 实际结构 `.module-item-caption` 下的 span：
        <span>2026</span> <span class="video-class">剧情,喜剧</span> <span>中国大陆</span>
    回退到老的 `.module-item-text / .module-info / .module-item-style` 通用匹配。
    """

    caption = card.select_one(".module-item-caption")
    if caption:
        category_node = caption.select_one(".video-class")
        category_text = (
            category_node.get_text(" ", strip=True) if isinstance(category_node, Tag) else ""
        )
        year = ""
        region = ""
        for span in caption.find_all("span", recursive=False):
            text = span.get_text(" ", strip=True)
            if not text or text == category_text:
                continue
            if not year and re.fullmatch(r"\d{4}", text):
                year = text
            elif not region:
                region = text
        if year or region:
            return year, region

    # 老结构 fallback：优先摘要节点（.video-text 通常含 year / region / 类型）
    info = card.select_one(".module-item-text, .module-info, .video-text")
    if not info:
        info = card.select_one(".module-item-style")
    text = info.get_text(" ", strip=True) if isinstance(info, Tag) else ""
    year = ""
    region = ""
    if text:
        parts = text.split()
        for p in parts:
            if re.fullmatch(r"\d{4}", p) and not year:
                year = p
            elif not region and len(p) <= 8:
                region = p
    return year, region


def _iter_resources(html: str, base_url: str) -> Iterable[ResourceItem]:
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    for row in soup.select(".module-row-info"):
        if not isinstance(row, Tag):
            continue
        anchor = row.select_one("a")
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href", "")
        m = re.match(r"^/tdown/(\d+)\.html$", str(href).strip())
        if not m:
            continue
        tdown_id = m.group(1)
        if tdown_id in seen:
            continue
        seen.add(tdown_id)

        title_attr = anchor.get("title", "")
        title = re.sub(r"^《.*?》", "", str(title_attr)).strip()
        size = _parse_size(title_attr or title)

        # 下载量在兄弟节点 .btn-down 里
        btn = row.find_next(class_="btn-down")
        downloads = btn.get_text(strip=True) if isinstance(btn, Tag) else ""

        yield ResourceItem(
            tdown_id=tdown_id,
            title=title or str(title_attr),
            size=size,
            downloads=downloads,
            url=urljoin(base_url + "/", href.lstrip("/")),
        )


def _parse_size(text: str) -> str:
    m = re.search(r"([\d.]+)\s*(GB|MB|KB|TB)", text, re.IGNORECASE)
    return f"{m.group(1)}{m.group(2).upper()}" if m else ""


def _extract_download_links(html: str) -> tuple[str, str, List[str]]:
    soup = BeautifulSoup(html, "html.parser")

    magnet = ""
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if href.startswith("magnet:"):
            magnet = href
            break

    thunder = ""
    extras: List[str] = []
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        if href.startswith("magnet:"):
            continue
        if href.startswith("/dlt/"):
            if not thunder:
                thunder = href
            else:
                extras.append(href)
        elif href.startswith("http") and "btbtla.com" not in href:
            extras.append(href)

    return magnet, thunder, extras