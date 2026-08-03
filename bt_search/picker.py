"""从资源标题里识别画质信息并按用户偏好挑一条最合适的资源。

识别字段（仅靠资源标题与下载量两列字段）：
    - 分辨率（2160p / 4K / 1080p / 720p ...）
    - 音频语言（国语 / 粤语 / 英语 / 日语 / 韩语 ...）
    - 字幕语言（中字 / 中英 / 英字 ...）
    - HDR / 杜比视界标记（HDR10 / HDR10+ / DV / DoVi / 杜比视界 / Dolby Vision）

打分顺序（在分辨率桶内）：
    1. 偏好语言音频命中 + 大权重加分
    2. 偏好字幕命中 + 中权重加分
    3. HDR / 杜比视界按用户配置 + 中权重加减分
    4. 同样条件下，按下载量从大到小

找不到任何分辨率时直接按下载量挑，不再回退（用户已设了偏好）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .scraper import ResourceItem

# ──────────────────────────── 分辨率 ────────────────────────────
_RESOLUTION_RANK: dict[str, int] = {
    "8k": 4320,
    "4320p": 4320,
    "4k": 2160,
    "2160p": 2160,
    "uhd": 2160,
    "1440p": 1440,
    "2k": 1440,
    "qhd": 1440,
    "1080p": 1080,
    "fhd": 1080,
    "720p": 720,
    "hd": 720,
    "480p": 480,
    "sd": 480,
}
_NUMERIC_P = re.compile(r"\b(\d{3,4})p\b", re.IGNORECASE)
_TEXT_TOKEN = re.compile(r"\b(8k|4k|uhd|2k|qhd|fhd|hd|sd)\b", re.IGNORECASE)

# ──────────────────────────── 音频语言 ────────────────────────────
# 关键词 → 规范化语言名。匹配顺序敏感，越靠前越先匹配（更具体优先）。
_AUDIO_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"国粤|粤国|guoyue|yueguo|guangyue", re.IGNORECASE), "yue"),
    (re.compile(r"粤语|cantonese", re.IGNORECASE), "yue"),
    (re.compile(r"国语|普通话|中文(?!.*?字幕)|chinese|mandarin|国配", re.IGNORECASE), "guo"),
    (re.compile(r"英语|英文|english", re.IGNORECASE), "eng"),
    (re.compile(r"日语|日文|japanese", re.IGNORECASE), "jpn"),
    (re.compile(r"韩语|韩文|korean", re.IGNORECASE), "kor"),
)

# 标题里"音轨/声道"段在很多时候跟在语言词后面，先把它当锚点抓
_AUDIO_TRACK_HINT = re.compile(
    r"(?:音轨|声轨|audio|track)[:：]?\s*([\u4e00-\u9fffA-Za-z/]+)",
    re.IGNORECASE,
)

# 压缩写法："国粤日多音轨" / "粤英音轨" —— ≥2 个语言字连用且后面跟音轨语境。
# 要求"连用 + 音轨后缀"是为了避免误中"中英字幕"这类字幕描述。
_AUDIO_CLUSTER = re.compile(r"([国粤英日韩]{2,})(?=[多双三四五]?音轨)")
_AUDIO_CLUSTER_CHARS = {"国": "guo", "粤": "yue", "英": "eng", "日": "jpn", "韩": "kor"}

# ──────────────────────────── 字幕语言 ────────────────────────────
# 命中规则：
#   "中字"/"中英"/"双语" => 字幕语言集合含 "chi"
#   "英字"                => 字幕语言集合含 "eng"
#   "日字"                => 字幕语言集合含 "jpn"
_SUB_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"中英|双语|中&英|zh.?en", re.IGNORECASE), "chi,eng"),
    (re.compile(r"中字|中字幕|简中|繁中|中文|chinese(?:.*?sub|sub.*?chinese)|zh", re.IGNORECASE), "chi"),
    (re.compile(r"英字|英字幕|english(?:.*?sub|sub.*?english)|en(?:g)?(?=sub)", re.IGNORECASE), "eng"),
    (re.compile(r"日字|日字幕|japanese(?:.*?sub|sub.*?japanese)|ja(?:p)?(?=sub)", re.IGNORECASE), "jpn"),
    (re.compile(r"韩字|韩字幕|korean(?:.*?sub|sub.*?korean)|ko(?:r)?(?=sub)", re.IGNORECASE), "kor"),
)
_SUB_LINE_HINT = re.compile(
    r"(?:字幕|字幕语言|sub(?:title)?s?|subs?)[:：]?\s*([\u4e00-\u9fffA-Za-z/&]+)",
    re.IGNORECASE,
)

# ──────────────────────────── HDR / 杜比视界 ────────────────────────────
_HDR_PATTERNS = (
    re.compile(r"hdr10\+|hdr10plus", re.IGNORECASE),
    re.compile(r"hdr10", re.IGNORECASE),
    re.compile(r"hdr(?!\+)", re.IGNORECASE),
)
_DOLBY_VISION_PATTERNS = (
    # "Dolby Vision" / "DoVi" / "杜比视界" / 单独 "DV"（但要避免误中 DVDRip 等）
    re.compile(r"dolby[\s._-]?vision|do[\s._-]?vi|杜比视界|(?<![A-Za-z0-9])DV(?![A-Za-z0-9])", re.IGNORECASE),
)

# ──────────────────────────── 文件体积 ────────────────────────────
_SIZE_PARSE = re.compile(r"([\d.]+)\s*(GB|MB|KB|TB)", re.IGNORECASE)

# 各分辨率分档的合理体积上限 (GB)，超过此值会被轻微扣分
_SIZE_LIMITS: dict[int, float] = {
    4320: 30.0,  # 8K
    2160: 20.0,  # 4K
    1440: 12.0,  # 2K
    1080: 8.0,   # 1080p
    720: 4.0,    # 720p
    480: 2.0,    # 480p
}
_SIZE_DEFAULT_LIMIT = 10.0  # 无法识别的分辨率用此值

# ──────────────────────────── 下载量 ────────────────────────────
_DOWNLOADS_UNIT = re.compile(r"([\d.]+)\s*(万|亿|k)?", re.IGNORECASE)

# 用户配置里的语言别名 → 上面识别的规范化 token
_LANG_ALIAS: dict[str, str] = {
    # audio
    "guo": "guo", "guoyu": "guo", "国语": "guo", "普通话": "guo", "国配": "guo",
    "yue": "yue", "粤语": "yue",
    "eng": "eng", "英语": "eng", "英文": "eng",
    "jpn": "jpn", "日语": "jpn", "日文": "jpn",
    "kor": "kor", "韩语": "kor", "韩文": "kor",
    # subtitle
    "chi": "chi", "中字": "chi", "中文": "chi",
}

# "原声" 的语义：除国/粤之外的所有被识别出来的音轨（eng / jpn / kor / ...）
_LOCALIZED_AUDIO = {"guo", "yue"}


# ──────────────────────────── 数据类 ────────────────────────────

@dataclass
class Preferences:
    resolution: str = "1080p"
    audio: str = ""               # "" 表示不限定；"guo" / "eng" / ...
    subtitles: str = ""           # 同上
    prefer_original_audio: bool = False  # True 时优先非国语音轨（适合"外国片原声+中字"）
    hdr: bool = True              # True 接受 HDR；False 偏好 SDR
    dolby_vision: bool = True     # True 接受杜比视界；False 偏好非 DV
    max_size_gb: Optional[float] = None  # 体积上限（GB）；None = 不限

    # 评分权重（如果以后想做 /config 调试可以暴露给用户）
    weight_audio: int = 100
    weight_subtitle: int = 30
    weight_hdr: int = 10
    weight_dv: int = 20
    weight_downloads: int = 1
    # 用户"不想要"时的主动扣分（hdr=False / dv=False 时给 HDR/DV 资源扣多少）
    weight_hdr_penalty: int = 200
    weight_dv_penalty: int = 400
    # 超过 max_size 时的扣分（不直接排除，仍可回落）
    weight_size_penalty: int = 1_000


@dataclass
class PickedItem:
    item: ResourceItem
    height: int
    downloads_score: int
    audios: list[str] = field(default_factory=list)
    subtitles: list[str] = field(default_factory=list)
    has_hdr: bool = False
    has_dolby_vision: bool = False
    reason: str = ""


# ──────────────────────────── 解析函数 ────────────────────────────

def detect_resolution(title: str) -> int:
    if not title:
        return 0
    m = _NUMERIC_P.search(title)
    if m:
        return int(m.group(1))
    m = _TEXT_TOKEN.search(title)
    if m:
        return _RESOLUTION_RANK.get(m.group(1).lower(), 0)
    return 0


def detect_audio(title: str) -> list[str]:
    if not title:
        return []
    hit = _AUDIO_TRACK_HINT.search(title)
    scope = hit.group(1) if hit else ""
    # 锚点后面没抓到有效内容（如 "[粤英多音轨+...]"，捕获在 + 处截断为空）
    # 时回退到整个标题，避免把紧贴锚点前面的语言词丢掉
    if not scope.strip():
        scope = title
    langs: list[str] = []
    # "国粤日多音轨" / "粤英多音轨" 这类压缩写法：≥2 个语言字连用 + 音轨语境
    for cluster in _AUDIO_CLUSTER.finditer(scope):
        for ch, token in _AUDIO_CLUSTER_CHARS.items():
            if ch in cluster.group(1) and token not in langs:
                langs.append(token)
    # 每种语言独立判定，互不短路。"粤国/国粤" 这种双语言标题也应同时识别。
    language_checks = (
        ("yue", re.compile(r"国粤|粤国|粤语|cantonese", re.IGNORECASE)),
        # "粤国" 同时作为国语存在的证据（行业里 "粤国" = 粤语 + 国语）
        ("guo", re.compile(r"国粤|粤国|国语|普通话|国配|mandarin", re.IGNORECASE)),
        ("eng", re.compile(r"英语|英文|english", re.IGNORECASE)),
        ("jpn", re.compile(r"日语|日文|japanese", re.IGNORECASE)),
        ("kor", re.compile(r"韩语|韩文|korean", re.IGNORECASE)),
    )
    # "中文" / "chinese" 单独处理，避免误命中"中英字幕"等
    if re.search(r"中文(?!.*?字幕)|chinese(?!\w)", scope, re.IGNORECASE):
        langs.append("guo")
    for token, pat in language_checks:
        if pat.search(scope) and token not in langs:
            langs.append(token)
    return langs


def detect_subtitles(title: str) -> list[str]:
    if not title:
        return []
    hit = _SUB_LINE_HINT.search(title)
    scope = hit.group(1) if hit else title
    langs: list[str] = []
    for pat, names in _SUB_PATTERNS:
        if pat.search(scope):
            for n in names.split(","):
                if n not in langs:
                    langs.append(n)
    return langs


def detect_hdr(title: str) -> bool:
    return any(p.search(title or "") for p in _HDR_PATTERNS)


def detect_dolby_vision(title: str) -> bool:
    return any(p.search(title or "") for p in _DOLBY_VISION_PATTERNS)


def parse_downloads(text: str) -> int:
    if not text:
        return 0
    raw = str(text).strip().replace(",", "").replace(" ", "")
    if not raw:
        return 0
    m = _DOWNLOADS_UNIT.search(raw)
    if not m:
        try:
            return int(float(raw))
        except ValueError:
            return 0
    num = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit == "万":
        num *= 10_000
    elif unit == "亿":
        num *= 100_000_000
    elif unit == "k":
        num *= 1_000
    return int(num)


def parse_size_gb(size_str: str) -> float:
    """把 ``ResourceItem.size``（如 ``47.95GB`` / ``800MB``）转为 GB 浮点数。"""
    if not size_str:
        return 0.0
    m = _SIZE_PARSE.search(str(size_str).strip().upper())
    if not m:
        return 0.0
    raw = m.group(1).lstrip(".").strip()
    if not raw:
        return 0.0
    value = float(raw)
    unit = m.group(2)
    if unit == "TB":
        value *= 1000
    elif unit == "MB":
        value /= 1000
    elif unit == "KB":
        value /= 1_000_000
    return value


def _size_penalty(size_gb: float, height: int) -> int:
    """对超出合理体积的文件打分惩罚，值越大越不想要。"""
    if size_gb <= 0:
        return 0
    limit = _SIZE_LIMITS.get(height, _SIZE_DEFAULT_LIMIT)
    if size_gb <= limit:
        return 0
    return int((size_gb - limit) * 5_000)


def normalize_lang(value: str) -> str:
    """把用户写的语言名（'guo' / '国语' / 'eng' / '英语' 等）规范成 token。"""
    if not value:
        return ""
    key = value.strip().lower()
    return _LANG_ALIAS.get(key, key.lower())


# ──────────────────────────── 评分 / 选优 ────────────────────────────

def _score_one(
    item: ResourceItem,
    prefs: Preferences,
    target_height: int,
) -> tuple[int, int, PickedItem]:
    height = detect_resolution(item.title)
    downloads = parse_downloads(item.downloads)
    audios = detect_audio(item.title)
    subs = detect_subtitles(item.title)
    has_hdr = detect_hdr(item.title)
    has_dv = detect_dolby_vision(item.title)

    # 分辨率桶：完全相等=0，>=target=1，<target=2，无法识别=3
    if height == target_height:
        bucket = 0
    elif height > target_height:
        bucket = 1
    elif height > 0:
        bucket = 2
    else:
        bucket = 3

    # 桶内排序键：音频偏好 > 字幕偏好 > HDR/DV 偏好 > 下载量
    # 用"累加负数"做排序键——越大越想选，sort 后越靠前
    rank = 0
    if prefs.audio and prefs.audio in audios:
        rank -= 1_000_000
    if prefs.subtitles and prefs.subtitles in subs:
        rank -= 10_000
    if has_dv and prefs.dolby_vision:
        rank -= 1_000
    elif has_dv and not prefs.dolby_vision:
        rank += prefs.weight_dv_penalty  # 用户不想要 DV：主动扣分
    if has_hdr and not has_dv and prefs.hdr:
        rank -= 100
    elif has_hdr and not prefs.hdr:
        rank += prefs.weight_hdr_penalty  # 用户不想要 HDR：主动扣分
    # 原声音轨偏好：未识别出音轨的资源当作"原声"放行；纯国/粤语资源扣分
    if prefs.prefer_original_audio:
        non_localized = [a for a in audios if a not in _LOCALIZED_AUDIO]
        if non_localized:
            rank -= 50_000
        elif audios and all(a in _LOCALIZED_AUDIO for a in audios):
            rank += 30_000  # 资源明确只有国/粤语：扣分（仍允许回落）
    # 下载量作为最终 tie-breaker（值越大越靠前）
    rank = rank * 10_000_000 - downloads

    # 体积惩罚：同档分辨率下偏好体积合理的文件
    size_gb = parse_size_gb(item.size)
    rank += _size_penalty(size_gb, height)

    # max_size 过滤：超过时扣分（不直接排除，仍可回落）
    if prefs.max_size_gb is not None and size_gb > prefs.max_size_gb:
        rank += prefs.weight_size_penalty

    picked = PickedItem(
        item=item,
        height=height,
        downloads_score=downloads,
        audios=audios,
        subtitles=subs,
        has_hdr=has_hdr,
        has_dolby_vision=has_dv,
        reason="",
    )
    return bucket, rank, picked


def _target_height(preferred: str) -> int:
    pref = (preferred or "").strip().lower()
    if pref in _RESOLUTION_RANK:
        return _RESOLUTION_RANK[pref]
    m = _NUMERIC_P.fullmatch(pref)
    if m:
        return int(m.group(1))
    return _RESOLUTION_RANK["1080p"]


def _build_reason(picked: PickedItem, prefs: Preferences, bucket: int) -> str:
    bits: list[str] = []

    if bucket == 0:
        bits.append(f"分辨率匹配 {prefs.resolution}")
    elif picked.height > 0:
        if bucket == 1:
            bits.append(f"偏好 {prefs.resolution} 不可用，取更高画质 {picked.height}p")
        else:
            bits.append(f"未达到偏好 {prefs.resolution}，回落至 {picked.height}p")
    else:
        bits.append("无法识别分辨率，按综合分选最合适")

    if prefs.audio:
        if prefs.audio in picked.audios:
            bits.append(f"音频命中 {prefs.audio}")
        else:
            bits.append(f"音频未命中（资源={','.join(picked.audios) or '?'}）")

    if prefs.prefer_original_audio:
        non_localized = [a for a in picked.audios if a not in _LOCALIZED_AUDIO]
        if non_localized:
            bits.append("原声 ✓（" + "/".join(non_localized) + "）")
        elif picked.audios and all(a in _LOCALIZED_AUDIO for a in picked.audios):
            bits.append("原声未命中（仅有 " + "/".join(picked.audios) + "）")
        else:
            bits.append("原声偏好（未识别出音轨，按原声放行）")

    if prefs.subtitles:
        if prefs.subtitles in picked.subtitles:
            bits.append(f"字幕命中 {prefs.subtitles}")
        else:
            bits.append(f"字幕未命中（资源={','.join(picked.subtitles) or '?'}）")

    if picked.has_dolby_vision:
        bits.append("杜比视界" + ("✓" if prefs.dolby_vision else "（不想要，已扣分）"))
    elif picked.has_hdr:
        bits.append("HDR" + ("✓" if prefs.hdr else "（不想要，已扣分）"))

    if (
        prefs.max_size_gb is not None
        and picked.item.size
        and parse_size_gb(picked.item.size) > prefs.max_size_gb
    ):
        bits.append(f"体积 {picked.item.size}（超 max_size={prefs.max_size_gb:g}GB，已扣分）")
    else:
        bits.append(f"热度 {picked.downloads_score or picked.item.downloads or '?'}")
        if picked.item.size:
            bits.append(f"体积 {picked.item.size}")
    return " · ".join(bits)


def pick_best(
    resources: Iterable[ResourceItem],
    prefs: Preferences,
) -> PickedItem | None:
    bucket_list = list(resources)
    if not bucket_list:
        return None

    target = _target_height(prefs.resolution)
    scored = [_score_one(r, prefs, target) for r in bucket_list]

    # 1) 在偏好桶内（bucket 0/1）按 rank 挑：分辨率满意时尊重音频/字幕/HDR 偏好
    in_pref = [s for s in scored if s[0] in (0, 1)]
    if in_pref:
        in_pref.sort(key=lambda x: (x[0], x[1]))
        bucket, _, picked = in_pref[0]
        picked.reason = _build_reason(picked, prefs, bucket)
        return picked

    # 2) 没有达到偏好的：先在所有资源里取可识别的最高分辨率，再在那一档里按下载量 + 偏好
    recognized = [s for s in scored if s[2].height > 0]
    if recognized:
        max_h = max(s[2].height for s in recognized)
        top_h = [s for s in recognized if s[2].height == max_h]
        top_h.sort(key=lambda x: x[1])  # rank 越小越靠前
        bucket = 2
        _, _, picked = top_h[0]
        picked.reason = _build_reason(picked, prefs, bucket)
        return picked

    # 3) 完全认不出分辨率：按 downloads 取最高
    fallback = [s for s in scored if s[2].downloads_score > 0]
    pool = fallback or scored
    pool.sort(key=lambda x: -x[2].downloads_score)
    bucket = 3
    _, _, picked = pool[0]
    picked.reason = _build_reason(picked, prefs, bucket)
    return picked