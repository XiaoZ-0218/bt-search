"""读取用户配置：默认分辨率、音频语言、字幕语言、HDR / 杜比视界偏好。

查找顺序（先找到先用，后者覆盖前者）：
    1. 内置默认值
    2. ~/.config/bt-search/config.json
    3. ./bt-search.json （当前目录）

配置格式（JSON，未给出的字段走默认）：

    {
      "resolution": "1080p",
      "audio": "guo",          // 国语 guo / 粤语 yue / 英语 eng / 日语 jpn / 韩语 kor
      "subtitles": "chi",      // 中字 chi / 英字 eng / 日字 jpn / 韩字 kor
      "hdr": true,             // 是否接受 HDR
      "dolby_vision": true,    // 是否接受杜比视界
      "auto_pick": true        // 自动按上述偏好选资源；false 时回退到交互选择
    }

文件读取/解析失败一律静默回落到默认，避免单点配置错误打断主流程。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_RESOLUTION = "1080p"

_USER_CONFIG = Path.home() / ".config" / "bt-search" / "config.json"
_PROJECT_CONFIG = Path("bt-search.json")

# 支持 // 整行注释（位于行首或仅含空白符之后），方便用户在配置文件里写备注。
_COMMENT_LINE = re.compile(r"^\s*//.*$", re.MULTILINE)


@dataclass
class Config:
    resolution: str = DEFAULT_RESOLUTION
    audio: str = ""            # "" = 不限定
    subtitles: str = ""
    prefer_original_audio: bool = False  # True 偏好原声（适合"外国片原声+中字"）
    hdr: bool = True
    dolby_vision: bool = True
    auto_pick: bool = True
    max_size_gb: float | None = None  # 体积上限（GB），None = 不限
    extras: dict = field(default_factory=dict)


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        text = _COMMENT_LINE.sub("", text)
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _as_str(value, default: str) -> str:
    if value is None:
        return default
    return str(value).strip()


def _as_float(value, default):
    """解析成 float。支持纯数字和带单位字符串（"20GB" / "800MB"）。"""

    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    # 尝试带单位解析（"20GB" / "800MB" / "1TB"）
    if isinstance(value, str):
        try:
            from .picker import parse_size_gb

            parsed = parse_size_gb(value)
            return parsed if parsed > 0 else default
        except Exception:
            return default
    return default


def load_config() -> Config:
    """按优先级合并配置，返回 ``Config``。"""

    merged: dict = {}
    for path in (_USER_CONFIG, _PROJECT_CONFIG):
        data = _read_json(path)
        if data:
            merged.update(data)

    cfg = Config(
        resolution=_as_str(merged.get("resolution"), DEFAULT_RESOLUTION) or DEFAULT_RESOLUTION,
        audio=_as_str(merged.get("audio"), ""),
        subtitles=_as_str(merged.get("subtitles"), ""),
        prefer_original_audio=_as_bool(merged.get("prefer_original_audio"), False),
        hdr=_as_bool(merged.get("hdr"), True),
        dolby_vision=_as_bool(merged.get("dolby_vision"), True),
        auto_pick=_as_bool(merged.get("auto_pick"), True),
        max_size_gb=_as_float(merged.get("max_size_gb"), None),
    )

    known = {
        "resolution", "audio", "subtitles", "prefer_original_audio",
        "hdr", "dolby_vision", "auto_pick", "max_size_gb",
    }
    cfg.extras = {k: v for k, v in merged.items() if k not in known}
    return cfg