"""命令行入口：交互式输入影片名 → 选择影片 → 选择资源 → 输出 magnet 等下载链接。"""

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
import re
import sys
from typing import List, Optional

import requests

from bt_search import BtbtlaSource, DownloadLink, ResourceItem, SearchResult, SourcePool
from bt_search.cli import (
    choose_from_list,
    choose_many_from_list,
    parse_indices,
    print_download_links_batch,
    print_resource_table,
    print_search_results,
)
from bt_search.config import load_config
from bt_search.picker import Preferences, normalize_lang, pick_best


_KNOWN_AUDIO = {"", "guo", "yue", "eng", "jpn", "kor"}
_KNOWN_SUBTITLES = {"", "chi", "eng", "jpn", "kor"}
_KNOWN_RESOLUTIONS = {"", "8k", "4320p", "4k", "2160p", "uhd", "1440p", "2k", "qhd",
                      "1080p", "fhd", "720p", "hd", "480p", "sd"}


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
        "  · 换站点：btbtt.com / btdig.com / ciliba.com / 蒲公英 / 磁力熊",
        file=file,
    )


def _warn_if_unknown(name: str, value: str, known: set[str]) -> None:
    if value and value not in known:
        print(
            f"警告：{name} “{value}” 不是已知的取值，挑选时可能无法命中。"
            f"已知值：{', '.join(sorted(known - {''}))}",
            file=sys.stderr,
        )


def _parse_size_gb(value: str) -> float:
    """解析 "20" / "20GB" / "4.5GB" / "800MB" / "1TB" 这样的体积串为 GB 浮点。"""

    s = (value or "").strip()
    if not s:
        raise ValueError("空字符串")
    m = re.match(r"^\s*([\d.]+)\s*(GB|MB|KB|TB)?\s*$", s, re.IGNORECASE)
    if not m:
        raise ValueError(f"无法解析体积：{value!r}")
    num = float(m.group(1))
    unit = (m.group(2) or "GB").upper()
    if unit == "TB":
        return num * 1000.0
    if unit == "MB":
        return num / 1000.0
    if unit == "KB":
        return num / 1_000_000.0
    return num


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bt-search",
        description="在 btbtla.com 上搜索影片并获取磁力等下载链接。",
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
    p.add_argument(
        "--resolution",
        default=None,
        help="覆盖配置文件里的默认分辨率（例 1080p / 2160p / 4k）。",
    )
    p.add_argument(
        "--audio",
        default=None,
        help="覆盖音频偏好（guo/eng/jpn/kor/yue 或 国语/英语...）。",
    )
    p.add_argument(
        "--subtitles",
        default=None,
        help="覆盖字幕偏好（chi/eng/jpn/kor 或 中字/英字...）。",
    )
    p.add_argument(
        "--prefer-original-audio",
        dest="prefer_original_audio",
        action="store_true",
        default=None,
        help="偏好原声音轨（适合外国片原声+中字场景，覆盖配置）。",
    )
    p.add_argument(
        "--no-prefer-original-audio",
        dest="prefer_original_audio",
        action="store_false",
        default=None,
        help="关闭原声偏好（覆盖配置）。",
    )
    p.add_argument(
        "--hdr",
        dest="hdr",
        action="store_true",
        default=None,
        help="强制接受 HDR（覆盖配置）。",
    )
    p.add_argument(
        "--no-hdr",
        dest="hdr",
        action="store_false",
        default=None,
        help="强制偏好非 HDR（覆盖配置）。",
    )
    p.add_argument(
        "--dolby-vision",
        dest="dolby_vision",
        action="store_true",
        default=None,
        help="强制接受杜比视界（覆盖配置）。",
    )
    p.add_argument(
        "--no-dolby-vision",
        dest="dolby_vision",
        action="store_false",
        default=None,
        help="强制偏好非杜比视界（覆盖配置）。",
    )
    p.add_argument(
        "--max-size",
        dest="max_size",
        default=None,
        help=(
            "体积上限。接受纯数字（默认 GB）或带单位，如 20 / 20GB / 4.5GB / 800MB。"
            " 超过的资源会被扣分而不是直接排除（仍可回落）。"
        ),
    )

    auto_group = p.add_mutually_exclusive_group()
    auto_group.add_argument(
        "--auto-pick",
        dest="auto_pick",
        action="store_true",
        default=None,
        help="开启自动挑选（覆盖配置）。",
    )
    auto_group.add_argument(
        "--interactive",
        dest="auto_pick",
        action="store_false",
        default=None,
        help="关闭自动挑选，进入交互选择（覆盖配置）。",
    )
    return p


def _build_pool() -> SourcePool:
    """构造站点池。目前只有 btbtla 一个可用源；以后接新源往列表里加即可。"""

    return SourcePool([BtbtlaSource()])


def run(args: argparse.Namespace) -> int:
    cfg = load_config()
    auto_pick = args.auto_pick if args.auto_pick is not None else cfg.auto_pick

    resolution = (args.resolution or cfg.resolution).strip().lower() or cfg.resolution
    audio = normalize_lang(args.audio if args.audio is not None else cfg.audio)
    subtitles = normalize_lang(args.subtitles if args.subtitles is not None else cfg.subtitles)

    _warn_if_unknown("音频", audio, _KNOWN_AUDIO)
    _warn_if_unknown("字幕", subtitles, _KNOWN_SUBTITLES)
    _warn_if_unknown("分辨率", resolution, _KNOWN_RESOLUTIONS)

    # 体积上限：CLI 优先，其次配置
    max_size_gb: Optional[float] = None
    raw_max_size = args.max_size if args.max_size is not None else cfg.max_size_gb
    if raw_max_size is not None:
        try:
            max_size_gb = float(raw_max_size) if isinstance(raw_max_size, (int, float)) else _parse_size_gb(str(raw_max_size))
        except ValueError as e:
            print(f"警告：max_size 解析失败（{e}），已忽略。", file=sys.stderr)

    prefs = Preferences(
        resolution=resolution,
        audio=audio,
        subtitles=subtitles,
        prefer_original_audio=(
            args.prefer_original_audio
            if args.prefer_original_audio is not None
            else cfg.prefer_original_audio
        ),
        hdr=args.hdr if args.hdr is not None else cfg.hdr,
        dolby_vision=args.dolby_vision if args.dolby_vision is not None else cfg.dolby_vision,
        max_size_gb=max_size_gb,
    )

    original_audio = " · 偏好原声" if prefs.prefer_original_audio else ""
    max_size_str = f" · 体积上限 {prefs.max_size_gb:g}GB" if prefs.max_size_gb is not None else ""
    print(
        f"\n偏好：分辨率 {prefs.resolution}"
        f" · 音频 {prefs.audio or '不限'}"
        f"{original_audio}"
        f" · 字幕 {prefs.subtitles or '不限'}"
        f" · HDR {'开' if prefs.hdr else '关'}"
        f" · 杜比视界 {'开' if prefs.dolby_vision else '关'}"
        f"{max_size_str}"
        f" · 自动挑选 {'开' if auto_pick else '关'}\n",
        file=sys.stderr,
    )

    pool = _build_pool()

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
    else:
        chosen_movies = choose_many_from_list(
            results,
            prompt="选择影片 (输入序号, 支持 1,3-5 / all / q): ",
            label_key=lambda r: r.title,
            file=sys.stderr,
        )
        if not chosen_movies:
            return 0

    multi_movie = len(chosen_movies) > 1
    pairs: list[tuple[DownloadLink, ResourceItem]] = []
    had_error = False

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

        if args.resource_index is not None and not multi_movie:
            if not 1 <= args.resource_index <= len(resources):
                print("指定的资源序号超出范围。", file=sys.stderr)
                return 2
            chosen_resource = resources[args.resource_index - 1]
        elif multi_movie or auto_pick:
            print_resource_table(resources, file=sys.stderr)
            picked = pick_best(resources, prefs)
            chosen_resource = picked.item
            print(f"\n自动挑选：{chosen_resource.title}  [{chosen_resource.size or '?'}]", file=sys.stderr)
            print(f"  理由：{picked.reason}", file=sys.stderr)
        else:
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