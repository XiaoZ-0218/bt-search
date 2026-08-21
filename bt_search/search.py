"""与站点无关的关键词 fallback 搜索。

直接搜 "夜王 黄子华" 0 结果时，按 bt_search.lang.build_search_plan 生成的
计划（原词 → 拆词 → 简繁互转）逐个再搜，合并去重后返回。

``source`` 参数可以是单个 ``BTSource``，也可以是 ``SourcePool``
（跨源容错由 pool 自己负责，本函数只关心关键词怎么变形）。
"""

from __future__ import annotations

from typing import List

import requests

from .lang import build_search_plan
from .scraper import SearchResult
from .source import BTSource


def search_with_fallback(
    keyword: str,
    source: BTSource,
    *,
    limit: int = 10,
) -> tuple[List[SearchResult], List[tuple[str, str, int]]]:
    """带回退的搜索：原词 → 拆词 → 简繁互转。

    返回：
        (merged_results, attempts)
        attempts 每一项是 (实际搜索的关键词, 触发原因, 该次结果数)。
    """

    plan = build_search_plan(keyword)
    if not plan:
        return [], []

    seen_ids: set[str] = set()
    merged: List[SearchResult] = []
    attempts: List[tuple[str, str, int]] = []

    for query, reason in plan:
        try:
            results = source.search(query, limit=max(limit, 1))
        except requests.RequestException as e:
            attempts.append((query, f"{reason}（失败：{e}）", 0))
            continue
        attempts.append((query, reason, len(results)))
        for r in results:
            if r.detail_id in seen_ids:
                continue
            seen_ids.add(r.detail_id)
            merged.append(r)
        # 凑够就停，不浪费后续 fallback
        if merged and len(merged) >= limit:
            break
        # 扁平源（如 torrentkitty）一次搜索即完整结果
        if any(r.complete for r in merged):
            break

    return merged[:limit], attempts
