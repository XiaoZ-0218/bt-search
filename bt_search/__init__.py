"""bt_search: 在 btbtla.com 上搜索影片并获取下载链接。

分层：
    BTSource          —— 站点抽象接口（bt_search.source）
    BtbtlaSource      —— btbtla.com 实现（bt_search.sources.btbtla）
    SourcePool        —— 多源容错管理（bt_search.sources.pool）
    search_with_fallback —— 关键词 fallback（bt_search.search）
"""

from .scraper import SearchResult, ResourceItem, DownloadLink
from .source import BTSource
from .sources import BtbtlaSource, SourcePool
from .search import search_with_fallback
from . import lang

# 向后兼容：旧代码里的 BTSearchClient 就是现在的 BtbtlaSource
BTSearchClient = BtbtlaSource

__all__ = [
    "BTSource",
    "BtbtlaSource",
    "SourcePool",
    "BTSearchClient",
    "SearchResult",
    "ResourceItem",
    "DownloadLink",
    "search_with_fallback",
    "lang",
]
