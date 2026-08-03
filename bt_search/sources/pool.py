"""SourcePool：多源管理器。

本身也是一个 ``BTSource``，内部按顺序持有一组站点，提供跨源容错：

- ``search``：逐源尝试，某个源抛异常就切下一个；返回第一个非空结果，
  全部为空则返回 ``[]``（"这个站没收录"不等于"别的站也没有"）；
  若所有源都抛异常，抛出最后一个异常（让上层走"搜索失败"分支）。
- ``fetch_resources`` / ``fetch_download``：ID 是源私有的（如 btbtla 的
  detail_id），跨源没有意义，只在**异常**时切下一个源重试。
"""

from __future__ import annotations

from typing import Callable, List, TypeVar

from ..scraper import DownloadLink, ResourceItem, SearchResult
from ..source import BTSource

_T = TypeVar("_T")


class SourcePool(BTSource):
    """按顺序管理多个 BTSource，失败自动切下一个。"""

    def __init__(self, sources: List[BTSource]) -> None:
        if not sources:
            raise ValueError("SourcePool 至少需要一个 BTSource")
        self.sources = list(sources)

    @property
    def name(self) -> str:
        return "pool(" + ",".join(s.name for s in self.sources) + ")"

    def search(self, keyword: str, *, limit: int = 20) -> List[SearchResult]:
        """逐源搜索：异常切下一个源；返回第一个非空结果；全空返回 []。"""

        last_error: Exception | None = None
        any_ok = False
        for source in self.sources:
            try:
                results = source.search(keyword, limit=limit)
            except Exception as e:  # 单源故障不拖垮整个 pool
                last_error = e
                continue
            any_ok = True
            if results:
                return results
        if not any_ok and last_error is not None:
            raise last_error
        return []

    def fetch_resources(self, detail_id: str) -> List[ResourceItem]:
        """拉取资源列表；异常时切下一个源重试。"""

        return self._failover(lambda s: s.fetch_resources(detail_id))

    def fetch_download(self, tdown_id: str) -> DownloadLink:
        """拉取下载链接；异常时切下一个源重试。"""

        return self._failover(lambda s: s.fetch_download(tdown_id))

    def search_with_fallback(
        self,
        keyword: str,
        *,
        limit: int = 10,
    ) -> tuple[List[SearchResult], List[tuple[str, str, int]]]:
        """关键词 fallback 搜索（拆词/简繁互转）的便捷入口，见 bt_search.search。"""

        from ..search import search_with_fallback

        return search_with_fallback(keyword, self, limit=limit)

    # ---------- internals ----------
    def _failover(self, call: "Callable[[BTSource], _T]") -> _T:
        """对源私有的操作做"异常才切源"的重试；全部失败抛最后一个异常。"""

        last_error: Exception | None = None
        for source in self.sources:
            try:
                return call(source)
            except Exception as e:
                last_error = e
                continue
        assert last_error is not None
        raise last_error
