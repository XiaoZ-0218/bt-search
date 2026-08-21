"""SourcePool：多源管理器。

本身也是一个 ``BTSource``，内部按顺序持有一组站点：

- ``search``：逐源尝试，某个源抛异常就切下一个；返回第一个非空结果，
  全部为空则返回 ``[]``；若所有源都抛异常，抛出最后一个异常。
- ``fetch_resources`` / ``fetch_download``：ID 是源私有的，**不换源重试**。
  出站时给 ``detail_id`` / ``tdown_id`` 加上 ``源名|`` 前缀，回站时拆开直连所属源。
"""

from __future__ import annotations

from typing import List

from ..scraper import DownloadLink, ResourceItem, SearchResult
from ..source import BTSource

_SEP = "|"


def qualify(source_name: str, native_id: str) -> str:
    return f"{source_name}{_SEP}{native_id}"


def split_qualified(qualified: str) -> tuple[str, str]:
    name, sep, native = qualified.partition(_SEP)
    if not sep or not native:
        raise ValueError(f"unqualified id: {qualified}")
    return name, native


class SourcePool(BTSource):
    """按顺序管理多个 BTSource：搜索可换源，取链只打所属源。"""

    def __init__(self, sources: List[BTSource]) -> None:
        if not sources:
            raise ValueError("SourcePool 至少需要一个 BTSource")
        self.sources = list(sources)
        self._owners: dict[str, BTSource] = {}

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
                tagged = [_tag_result(source, r) for r in results]
                for r in tagged:
                    self._owners[r.detail_id] = source
                return tagged
        if not any_ok and last_error is not None:
            raise last_error
        return []

    def fetch_resources(self, detail_id: str) -> List[ResourceItem]:
        """拉取资源列表；只打产出该结果的源，失败不换源。"""

        source, native = self._resolve(detail_id)
        items = source.fetch_resources(native)
        tagged: List[ResourceItem] = []
        for item in items:
            tagged_item = _tag_resource(source, item)
            self._owners[tagged_item.tdown_id] = source
            tagged.append(tagged_item)
        return tagged

    def fetch_download(self, tdown_id: str) -> DownloadLink:
        """拉取下载链接；只打所属源，失败不换源。"""

        source, native = self._resolve(tdown_id)
        return source.fetch_download(native)

    def search_with_fallback(
        self,
        keyword: str,
        *,
        limit: int = 10,
    ) -> tuple[List[SearchResult], List[tuple[str, str, int]]]:
        """关键词 fallback 搜索（拆词/简繁互转）的便捷入口，见 bt_search.search。"""

        from ..search import search_with_fallback

        return search_with_fallback(keyword, self, limit=limit)

    def _resolve(self, qualified: str) -> tuple[BTSource, str]:
        name, native = split_qualified(qualified)
        owner = self._owners.get(qualified)
        if owner is not None:
            return owner, native
        for source in self.sources:
            if source.name == name:
                return source, native
        raise ValueError(f"未知源：{name}")


def _tag_result(source: BTSource, r: SearchResult) -> SearchResult:
    return SearchResult(
        detail_id=qualify(source.name, r.detail_id),
        title=r.title,
        url=r.url,
        category=r.category,
        year=r.year,
        region=r.region,
        summary=r.summary,
        source=source.name,
        complete=r.complete,
    )


def _tag_resource(source: BTSource, item: ResourceItem) -> ResourceItem:
    return ResourceItem(
        tdown_id=qualify(source.name, item.tdown_id),
        title=item.title,
        size=item.size,
        downloads=item.downloads,
        url=item.url,
        source=source.name,
    )
