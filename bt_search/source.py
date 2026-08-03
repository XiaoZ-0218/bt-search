"""BT 站点抽象接口。

一个 ``BTSource`` 代表一个可搜索的 BT 站点。接口**只负责取数据并原样返回**，
不做任何过滤、挑选或关键词变形——那些是上层的职责：

    main.py / search（上层：fallback 关键词、按序号取资源）
        ↓
    SourcePool（多源管理：失败切站）
        ↓
    BTSource（本接口：search / fetch_resources / fetch_download，原样返回）
        ↓
    BtbtlaSource（具体实现，见 bt_search/sources/）

新增一个站点 = 写一个 ``BTSource`` 子类，塞进 ``SourcePool`` 即可。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .scraper import DownloadLink, ResourceItem, SearchResult


class BTSource(ABC):
    """BT 站点接口。所有网络异常应原样抛出（``requests.RequestException``），
    由上层（SourcePool / 调用方）决定如何处理。"""

    @property
    def name(self) -> str:
        """站点名，用于日志和错误提示。默认取类名。"""
        return type(self).__name__

    @abstractmethod
    def search(self, keyword: str, *, limit: int = 20) -> List[SearchResult]:
        """按关键词搜索影片，原样返回结果（不做去重/过滤/排序）。"""

    @abstractmethod
    def fetch_resources(self, detail_id: str) -> List[ResourceItem]:
        """拉取某部影片的资源版本列表。"""

    @abstractmethod
    def fetch_download(self, tdown_id: str) -> DownloadLink:
        """拉取某条资源的下载链接（含 magnet）。"""
