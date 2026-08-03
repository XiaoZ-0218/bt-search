"""CLI 渲染工具：搜索结果、资源表、下载链接输出。"""

from __future__ import annotations

import shutil
import sys
from typing import Callable, List, Optional, TextIO, TypeVar

from .scraper import DownloadLink, ResourceItem, SearchResult

T = TypeVar("T")

# 使用 ANSI 颜色让终端输出更可读；非 TTY 时自动关闭。
_USE_COLOR = shutil.get_terminal_size((0, 0)).columns > 0 and sys.stdout.isatty()


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _c(code: str, text: str, file: TextIO | None = None) -> str:
    if file is not None and getattr(file, "isatty", lambda: False)():
        return f"\033[{code}m{text}\033[0m"
    if _USE_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text


def print_search_results(
    results: List[SearchResult], *, file: TextIO | None = None
) -> None:
    if file is None:
        file = sys.stdout
    print(_c("1;36", "── 搜索结果 ──", file=file), file=file)
    for idx, r in enumerate(results, 1):
        head = f"[{idx}] {_c('1;33', r.title, file=file)}"
        meta = " · ".join(p for p in [r.year, r.region, r.category] if p)
        print(f"{head}  {meta}", file=file)
        if r.summary:
            print(f"    {_c('90', _truncate(r.summary, 110), file=file)}", file=file)
    print(file=file)


def print_resource_table(
    resources: List[ResourceItem], *, file: TextIO | None = None
) -> None:
    if file is None:
        file = sys.stdout
    print(_c("1;36", "── 资源版本 ──", file=file), file=file)
    for idx, r in enumerate(resources, 1):
        title = _truncate(r.title, 70)
        size = r.size or "-"
        dl = r.downloads or "-"
        print(
            f"[{idx}] {_c('1;33', title, file=file)}  "
            f"{_c('36', size, file=file)}  下载量 {_c('35', dl, file=file)}",
            file=file,
        )
    print(file=file)


def print_download_links_batch(
    pairs: list[tuple[DownloadLink, ResourceItem]],
    magnet_only: bool,
    *,
    file: TextIO | None = None,
    err: TextIO | None = None,
) -> None:
    """批量输出下载链接；--magnet-only 时每行一个 magnet。"""

    if file is None:
        file = sys.stdout
    if err is None:
        err = sys.stderr

    if magnet_only:
        for link, resource in pairs:
            if link.magnet:
                print(link.magnet, file=file)
            else:
                print(f"未找到磁力链接：{resource.title}", file=err)
        return

    print(_c("1;32", "── 下载链接 ──", file=file), file=file)
    for idx, (link, resource) in enumerate(pairs):
        prefix = "\n" if idx > 0 else ""
        print(
            f"{prefix}资源：{resource.title}  [{resource.size or '?'}]  热度 {resource.downloads or '?'}",
            file=file,
        )
        if link.magnet:
            print(f"{_c('1;33', '磁力链接 (magnet):', file=file)}", file=file)
            print(link.magnet, file=file)
        if link.thunder:
            print(f"{_c('1;33', '迅雷链接:', file=file)} {link.thunder}", file=file)
        for extra in link.extras:
            print(f"{_c('1;33', '其它:', file=file)} {extra}", file=file)
        if not link.magnet and not link.thunder and not link.extras:
            print(
                _c("31", "未找到可用下载链接，可能需要登录或触发验证。", file=err),
                file=err,
            )


def print_download_links(
    link: DownloadLink,
    resource: ResourceItem,
    magnet_only: bool,
    *,
    file: TextIO | None = None,
    err: TextIO | None = None,
) -> None:
    """单条资源的兼容包装。"""
    print_download_links_batch([(link, resource)], magnet_only, file=file, err=err)


def parse_indices(raw: str, max_idx: int) -> list[int]:
    """解析 '1,3,5' / '1-3' / '1,3-5,7' / 'all' 成去重后的 1-based 序号列表。

    任意片段非法时返回空列表，视为取消选择。
    """
    text = (raw or "").strip()
    if not text or text.lower() in {"q", "quit", "exit"}:
        return []
    if text.lower() == "all":
        return list(range(1, max_idx + 1))

    indices: list[int] = []
    seen: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, _, end = part.partition("-")
            try:
                a, b = int(start), int(end)
            except ValueError:
                return []
            if a > b:
                a, b = b, a
            for i in range(a, b + 1):
                if i not in seen and 1 <= i <= max_idx:
                    indices.append(i)
                    seen.add(i)
        else:
            try:
                i = int(part)
            except ValueError:
                return []
            if i not in seen and 1 <= i <= max_idx:
                indices.append(i)
                seen.add(i)
    return indices


def choose_many_from_list(
    items: List[T],
    *,
    prompt: str,
    label_key: Callable[[T], str],
    file: TextIO | None = None,
) -> List[T]:
    """读取用户输入的序号（支持 1,3-5,7 / all / q），返回选中的项列表。"""

    if file is None:
        file = sys.stdout
    if not items:
        return []

    print(prompt, end="", file=file)
    try:
        raw = input().strip()
    except EOFError:
        return []
    indices = parse_indices(raw, len(items))
    return [items[i - 1] for i in indices]


def choose_from_list(
    items: List[T],
    *,
    prompt: str,
    label_key: Callable[[T], str],
    file: TextIO | None = None,
) -> Optional[T]:
    """读取用户输入的单个下标，返回对应项；输入 q / 空 / 非数字 / EOF 返回 None。"""

    chosen = choose_many_from_list(
        items, prompt=prompt, label_key=label_key, file=file
    )
    return chosen[0] if chosen else None