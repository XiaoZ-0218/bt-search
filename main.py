"""命令行入口：搜索影片 → 选择影片 → 列出资源 → 按序号输出 magnet 等下载链接。

本程序只做"搜索、列表、取链接"，不替用户挑资源：
    - 人类在 TTY 里运行时，交互式选择；
    - 作为 agent 调用时，先跑一遍看资源表（stderr），再由大模型挑选序号，
      加 ``--resource-index N`` 重跑取链接。挑选启发式写在 SKILL.md 里。
"""

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "requests>=2.31.0",
#     "beautifulsoup4>=4.12.0",
#     "zhconv>=1.4.3",
# ]
# ///

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

import requests

from bt_search import (
    BtbtlaSource,
    CilixiongSource,
    DownloadLink,
    ResourceItem,
    SearchResult,
    SourcePool,
    TorrentKittySource,
)
from bt_search.cli import (
    choose_from_list,
    choose_many_from_list,
    parse_indices,
    print_download_links_batch,
    print_resource_table,
    print_search_results,
)


def _print_fallback_log(
    attempts: List[tuple[str, str, int]], *, file
) -> None:
    """打印回退搜索过程（已用 ≥2 个关键词尝试时）。"""

    print("── 已尝试的搜索关键词 ──", file=file)
    for query, reason, count in attempts:
        flag = f"命中 {count} 条" if count else "0 条"
        print(f"  · {query}  →  {flag}  ({reason})", file=file)
    print(file=file)


def _print_no_results_help(
    keyword: str,
    attempts: List[tuple[str, str, int]],
    *,
    file,
) -> None:
    """0 结果时打印：尝试过的关键词 + 下一步建议。"""

    print(f"没有找到与 “{keyword}” 相关的影片。", file=file)
    if attempts:
        _print_fallback_log(attempts, file=file)
    print(
        "可以试试：\n"
        "  · 切换关键词（英文名 / 拼音 / IMDb ID）\n"
        "  · 暂时无片源：过几天再跑一次，新片源通常 1-2 周内陆续流出\n"
        "  · 强制指定备用源：--source cilixiong.org / --source torrentkitty.net",
        file=file,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bt-search",
        description="在多个 BT 站点上搜索影片并获取磁力等下载链接。",
    )
    p.add_argument(
        "keyword",
        nargs="?",
        help="要搜索的影片名（中文 / 英文均可）。省略时进入交互模式。",
    )
    p.add_argument(
        "-n",
        "--limit",
        type=int,
        default=10,
        help="搜索结果最多显示多少部影片，默认 10。",
    )
    p.add_argument(
        "--source",
        default=None,
        metavar="NAME",
        help=(
            "指定搜索站点（默认全部，自动失败切换）："
            "btbtla.com / cilixiong.org / torrentkitty.net"
        ),
    )
    p.add_argument(
        "--resource-index",
        type=int,
        default=None,
        help="直接指定资源序号（从 1 开始），跳过选择。仅单部影片时生效。",
    )
    p.add_argument(
        "--movies",
        default=None,
        help="直接指定多部影片序号，如 1,3,5 或 1-3,7。",
    )
    p.add_argument(
        "--movie-index",
        type=int,
        default=None,
        help="已废弃，请用 --movies。直接指定单部影片序号（从 1 开始）。",
    )
    p.add_argument(
        "--magnet-only",
        action="store_true",
        help="只打印 magnet 链接（适合直接喂给下载工具）。",
    )
    return p


_ALL_SOURCES: "dict[str, type]" = {
    "btbtla.com": BtbtlaSource,
    "cilixiong.org": CilixiongSource,
    "torrentkitty.net": TorrentKittySource,
}
_DEFAULT_SOURCES = [BtbtlaSource, CilixiongSource, TorrentKittySource]


def _build_pool(source: Optional[str] = None) -> SourcePool:
    """构造站点池：默认全源（btbtla 主源，其余失败切换）；--source 指定单源。"""

    if source is None:
        return SourcePool([cls() for cls in _DEFAULT_SOURCES])
    cls = _ALL_SOURCES.get(source)
    if cls is None:
        raise ValueError(
            f"未知站点：{source}（可选：{' / '.join(_ALL_SOURCES)}）"
        )
    return SourcePool([cls()])


def run(args: argparse.Namespace) -> int:
    try:
        pool = _build_pool(args.source)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2

    keyword: Optional[str] = args.keyword
    if not keyword:
        print("请输入要搜索的影片名: ", end="", file=sys.stderr)
        try:
            keyword = input().strip()
        except EOFError:
            print("\n输入已结束。", file=sys.stderr)
            return 130
    if not keyword:
        print("关键词不能为空。", file=sys.stderr)
        return 2

    print(f"\n正在搜索：{keyword}\n", file=sys.stderr)
    try:
        results, attempts = pool.search_with_fallback(
            keyword, limit=max(args.limit, 1)
        )
    except requests.RequestException as e:
        print(f"搜索失败：{e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"搜索时发生错误：{e}", file=sys.stderr)
        return 1
    if not results:
        _print_no_results_help(keyword, attempts, file=sys.stderr)
        return 1
    if len(attempts) > 1:
        _print_fallback_log(attempts, file=sys.stderr)
    print_search_results(results, file=sys.stderr)

    chosen_movies: List[SearchResult]
    if args.movies is not None:
        indices = parse_indices(args.movies, len(results))
        if not indices:
            print("指定的影片序号无效。", file=sys.stderr)
            return 2
        chosen_movies = [results[i - 1] for i in indices]
    elif args.movie_index is not None:
        if not 1 <= args.movie_index <= len(results):
            print("指定的影片序号超出范围。", file=sys.stderr)
            return 2
        chosen_movies = [results[args.movie_index - 1]]
    elif sys.stdin.isatty():
        chosen_movies = choose_many_from_list(
            results,
            prompt="选择影片 (输入序号, 支持 1,3-5 / all / q): ",
            label_key=lambda r: r.title,
            file=sys.stderr,
        )
        if not chosen_movies:
            return 0
    else:
        print(
            "未指定 --movies，仅列出影片。挑选序号后重新运行，例如：\n"
            "  --movies <影片序号>",
            file=sys.stderr,
        )
        return 0

    multi_movie = len(chosen_movies) > 1
    if args.resource_index is not None and multi_movie:
        print(
            "--resource-index 仅支持单部影片；多部影片请逐部单独运行。",
            file=sys.stderr,
        )
        return 2

    pairs: list[tuple[DownloadLink, ResourceItem]] = []
    had_error = False
    listed_only = False  # 非交互且未指定资源序号：只列了资源表，没取链接

    for movie in chosen_movies:
        print(f"\n── 《{movie.title}》 ──", file=sys.stderr)
        try:
            resources: List[ResourceItem] = pool.fetch_resources(movie.detail_id)
        except requests.RequestException as e:
            print(f"获取资源列表失败：{e}", file=sys.stderr)
            had_error = True
            continue
        except Exception as e:
            print(f"获取资源列表时发生错误：{e}", file=sys.stderr)
            had_error = True
            continue
        if not resources:
            print(f"《{movie.title}》暂无可用资源。", file=sys.stderr)
            had_error = True
            continue

        if args.resource_index is not None:
            if not 1 <= args.resource_index <= len(resources):
                print("指定的资源序号超出范围。", file=sys.stderr)
                return 2
            chosen_resource = resources[args.resource_index - 1]
        elif sys.stdin.isatty():
            print_resource_table(resources, file=sys.stderr)
            chosen_resource = choose_from_list(
                resources,
                prompt="选择资源版本 (输入序号, q 退出): ",
                label_key=lambda r: f"{r.title}  [{r.size or '未知大小'}]",
                file=sys.stderr,
            )
            if chosen_resource is None:
                if not multi_movie:
                    return 0
                continue
        else:
            # 非交互调用（agent）：程序不替用户挑，列出资源表后交还给调用方。
            print_resource_table(resources, file=sys.stderr)
            listed_only = True
            continue

        try:
            link = pool.fetch_download(chosen_resource.tdown_id)
        except requests.RequestException as e:
            print(f"获取下载链接失败：{e}", file=sys.stderr)
            had_error = True
            continue
        except Exception as e:
            print(f"获取下载链接时发生错误：{e}", file=sys.stderr)
            had_error = True
            continue
        pairs.append((link, chosen_resource))

    if listed_only and not pairs:
        print(
            "未指定 --resource-index，仅列出资源。挑选序号后重新运行，例如：\n"
            f"  --movies <影片序号> --resource-index <资源序号> --magnet-only",
            file=sys.stderr,
        )
        return 1 if had_error else 0

    if not pairs:
        return 1 if had_error else 0

    print_download_links_batch(pairs, args.magnet_only)
    return 1 if had_error else 0


def main(argv: Optional[List[str]] = None) -> int:
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        return run(args)
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except EOFError:
        print("\n输入已结束。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
