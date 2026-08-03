# bt-search

> 在 [btbtla.com](https://btbtla.com) 上搜索影片 / 电视剧，并取回 magnet / 迅雷下载链接的轻量命令行工具。
>
> 配套 Claude skill — 同目录下的 [SKILL.md](SKILL.md) 描述了如何以 agent 身份调用本程序。

本仓库是 [movie-download](https://example.invalid) 项目的“skill 形态”分支：把 CLI 与站点实现打成自包含的目录，可以直接被 `uv run` 拉起，无需 clone 仓库或建 venv。

---

## 特性

- 🎬 **搜索 + 列资源 + 取链接** 三段式 CLI，结构清爽。
- 🧠 **不替你挑资源** — 程序只列资源表，挑哪个由调用方按启发式决定（避免误挑冷门 / 大小不合理的资源）。
- 🔁 **关键词 fallback** — 搜不到时自动用英文名、拼音、IMDb ID 重试，直到命中或耗尽。
- 🌐 **多源可扩展** — `BTSource` 抽象了站点抓取层；要接新站只需新增一个实现、丢进 `SourcePool`。
- 🧪 **离线测试套件** — stdlib `unittest`，无网络依赖；34 个用例覆盖 CLI / 解析 / 抓取。
- 🪶 **零安装** — 通过 [PEP 723](https://peps.python.org/pep-0723/) 内联依赖声明，`uv run` 临时解决依赖。

---

## 快速开始

需要 [uv](https://github.com/astral-sh/uv)（`brew install uv`）或 Python ≥ 3.9 + 手动安装三个依赖。

```bash
# 搜索（输出到 stderr）
uv run main.py "阿凡达"

# 列出指定影片的资源表
uv run main.py "阿凡达" --movies 1

# 取出指定资源的 magnet（stdout 一行一个）
uv run main.py "阿凡达" --movies 1 --resource-index 22 --magnet-only
```

没有 `uv` 的等价写法：

```bash
pip install requests beautifulsoup4 zhconv
python3 main.py "阿凡达"
```

### 标志一览

| Flag | 作用 |
| --- | --- |
| `keyword` | 影片名（中文 / 英文 / 拼音 / IMDb ID），可省略走交互输入 |
| `-n N` | 搜索结果数量上限，默认 10 |
| `--movies <indices>` | 跳过影片选择；支持 `1`、`1,3`、`1-3`、`1,3-5,7`、`all` |
| `--resource-index N` | 直接取该资源的 magnet；只对单部影片生效 |
| `--magnet-only` | 只把 magnet 打到 stdout，其余全部进 stderr |
| `--movie-index N` | **已废弃**，请改用 `--movies` |

### 输出分流约定

- `--magnet-only` 时：magnet → **stdout**，其它全部 → **stderr**。
- 否则：所有提示 / 列表 / 日志都进 **stderr**，方便用 `2>/dev/null` 滤掉。

---

## 架构

代码分层清晰，便于扩展：

```
main.py                       CLI 入口，组装 SourcePool + argparse
bt_search/
├── scraper.py                数据类（SearchResult / ResourceItem / DownloadLink）
├── source.py                 BTSource 抽象接口
├── lang.py                   简繁转换 + 启发式小工具
├── search.py                 关键词 fallback（中文 → 英文 / 拼音 / IMDb ID）
├── cli.py                    交互选择 + 表格输出
└── sources/
    ├── btbtla.py             btbtla.com 站点实现
    └── pool.py               多源容错（失败自动换源）
tests/
├── test_cli.py
├── test_lang.py
├── test_main.py
└── test_scraper.py           stdlib unittest，全部离线
```

加新站点只需要：

1. 继承 `BTSource` 实现 `search` / `fetch_resources` / `fetch_download` 三个方法；
2. 在 `main.py` 的 `_build_pool()` 里把它丢进 `SourcePool` 即可。

---

## 资源挑选启发式

程序只列、不挑。挑选规则总结（详见 [SKILL.md](SKILL.md)）：

- **电视剧** 默认优先全集合集（`全集` / `全季` / `S01` 整季），不是单集。
- **分辨率** 默认 4K（`2160p` / `4K` / `UHD`），缺失时**升级**一档而非降档。
- **音轨** 外国片优先原声 + 中字；`X国Y多音轨` 满足两边。
- **字幕** 默认要求中字（`中字` / `中英` / `简中` / `繁中` 等）。
- **HDR / DV** 仅在设备支持时挑，否则选 SDR。
- **大小 sanity check** — 4K ≤ 20 GB，1080p ≤ 8 GB，720p ≤ 4 GB；明显更大通常是 REMUX / 原盘。
- **下载次数** 作为最后 tie-break：越多越健康；避免 0 下载条目。

---

## 开发

```bash
# 跑离线测试
uv run --with requests --with beautifulsoup4 --with zhconv \
    python -m unittest discover -s tests -t .

# 与上游 movie-download 同步
# 上游 bug fix → 拷 main.py 与 bt_search/ 整个包过来覆盖即可
```

仓库目录即 skill 目录：

- `SKILL.md` —— 描述**给 Claude 看**，告诉它怎么调用本工具（含触发条件、三步流程、启发式）。
- `README.md` —— 描述**给人看**，解释项目是什么、怎么用、怎么改。

---

## 声明

本项目仅供**个人学习与研究**使用，请勿用于商业用途或大规模抓取。请尊重目标站点的条款与 robots 规则。

站点结构变动导致解析失败时，欢迎附带 HTML 片段提 issue。