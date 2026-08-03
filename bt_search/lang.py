"""简繁/简繁中文互转（基于 zhconv，包装 OpenCC 数据）。

仅做 best-effort 简繁互转，用于"搜不到时再试一次"的 fallback。
不做句子级语义转换。
"""

from __future__ import annotations

from typing import Optional

try:
    import zhconv  # type: ignore
except ImportError:  # pragma: no cover - 依赖已固定，理论不可能发生
    zhconv = None  # type: ignore[assignment]


def to_traditional(text: str) -> str:
    """把字符串转为繁体中文（zh-tw）。zhconv 不可用时原样返回。"""

    if not text or zhconv is None:
        return text
    return zhconv.convert(text, "zh-tw")


def to_simplified(text: str) -> str:
    """把字符串转为简体中文（zh-cn）。zhconv 不可用时原样返回。"""

    if not text or zhconv is None:
        return text
    return zhconv.convert(text, "zh-cn")


def has_simplified(text: str) -> bool:
    """判断字符串是否包含可能可以转繁体的简体字。

    用"转换前后是否变化"判断，对 OpenCC 来说这是个稳定信号：
    简体输入会变，繁体/纯英文/数字/纯标点输入不会变。
    """

    if not text or zhconv is None:
        return False
    return zhconv.convert(text, "zh-tw") != text


def has_traditional(text: str) -> bool:
    """判断字符串是否包含可能可以转简体的繁体字（方向同 has_simplified）。"""

    if not text or zhconv is None:
        return False
    return zhconv.convert(text, "zh-cn") != text


def split_tokens(text: str) -> list[str]:
    """把搜索关键词按空白 + 常见中文标点切成多个 token。

    用途：原词搜不到时，拆词逐个搜（"夜王 黄子华" → ["夜王", "黄子华"]）。
    过滤掉单字符（标点）和重复 token。
    """

    if not text:
        return []
    # 中文 / 英文 / 数字 之间都断开
    import re

    parts = re.split(r"[\s,，、/／;；|｜]+", text.strip())
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 单字符时仅保留 ASCII 字母 / 数字；纯标点 / 单字中文都过滤
        if len(p) == 1 and not (p.isascii() and p.isalnum()):
            continue
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def try_traditional(text: str) -> Optional[str]:
    """如果 text 含简体字，返回对应的繁体版本；否则返回 None。"""

    if not has_simplified(text):
        return None
    return to_traditional(text)


def try_simplified(text: str) -> Optional[str]:
    """如果 text 含繁体字，返回对应的简体版本；否则返回 None。"""

    if not has_traditional(text):
        return None
    return to_simplified(text)


def build_search_plan(keyword: str) -> list[tuple[str, str]]:
    """构造回退搜索计划：(关键词, 触发原因)。

    顺序：
        1. 原词
        2. 拆词后的每个 token（仅当 ≥2 个 token 时）
        3. 整句的繁体（仅当含简体时）→ 每个 token 的繁体
        4. 整句的简体（仅当含繁体时）→ 每个 token 的简体
           （站点以简体收录为主，繁体输入很需要这一步）
    """

    keyword = (keyword or "").strip()
    if not keyword:
        return []

    plan: list[tuple[str, str]] = [(keyword, "原词")]
    tokens = split_tokens(keyword)
    if len(tokens) >= 2:
        for t in tokens:
            plan.append((t, f"拆词：{t}"))

    trad = try_traditional(keyword)
    if trad and trad != keyword:
        plan.append((trad, f"繁体：{trad}"))
        if len(tokens) >= 2:
            for t in tokens:
                t_trad = try_traditional(t)
                if t_trad and t_trad != t:
                    plan.append((t_trad, f"繁体拆词：{t_trad}"))

    simp = try_simplified(keyword)
    if simp and simp != keyword:
        plan.append((simp, f"简体：{simp}"))
        if len(tokens) >= 2:
            for t in tokens:
                t_simp = try_simplified(t)
                if t_simp and t_simp != t:
                    plan.append((t_simp, f"简体拆词：{t_simp}"))

    return plan
