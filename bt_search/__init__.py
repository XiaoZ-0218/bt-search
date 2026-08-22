"""bt_search: 在多个 BT 站点上搜索影片并获取下载链接。

分层：
    BTSource          —— 站点抽象接口（bt_search.source）
    BtbtlaSource      —— btbtla.com 实现（bt_search.sources.btbtla）
    CilixiongSource   —— cilixiong.org 磁力熊实现（bt_search.sources.cilixiong）
    TorrentKittySource—— torrentkitty.net 实现（bt_search.sources.torrentkitty）
    KnabenSource      —— knaben.org 实现（bt_search.sources.knaben）
    DmhySource        —— share.dmhy.org 动漫花园（bt_search.sources.dmhy）
    NyaaSource        —— nyaa.si 实现（bt_search.sources.nyaa）
    SourcePool        —— 多源容错管理（bt_search.sources.pool）
    search_with_fallback —— 关键词 fallback（bt_search.search）
"""

from .scraper import SearchResult, ResourceItem, DownloadLink
from .source import BTSource
from .sources import (
    BtbtlaSource,
    CilixiongSource,
    DmhySource,
    KnabenSource,
    NyaaSource,
    SourcePool,
    TorrentKittySource,
)
from .search import search_with_fallback
from . import lang

# 向后兼容：旧代码里的 BTSearchClient 就是现在的 BtbtlaSource
BTSearchClient = BtbtlaSource

__all__ = [
    "BTSource",
    "BtbtlaSource",
    "CilixiongSource",
    "TorrentKittySource",
    "KnabenSource",
    "DmhySource",
    "NyaaSource",
    "SourcePool",
    "BTSearchClient",
    "SearchResult",
    "ResourceItem",
    "DownloadLink",
    "search_with_fallback",
    "lang",
]
