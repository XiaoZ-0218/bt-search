---
name: bt-search
description: >
  Search movies and TV shows on btbtla.com and return magnet / download links.
  Trigger when the user asks to search a movie, get a magnet, use bt-search,
  download a film or show, or similar.
version: 0.2.0
---

# bt-search

Search for films or shows on btbtla.com and retrieve their magnet / thunder download links.

This skill is **self-contained**: the full CLI (`main.py` + the `bt_search` package)
ships inside this skill directory and can be run from anywhere.

## When to use

- The user asks to search for a movie or TV show.
- The user wants a magnet link, download link, or resource list for a specific title.
- The user mentions "bt-search", "btbtla", "movie download", "get magnet for ...", etc.

## How to run

The script uses [PEP 723 inline metadata](https://peps.python.org/pep-0723/), so a single
`uv run` resolves dependencies (requests / beautifulsoup4 / zhconv) into uv's cache —
no project checkout, venv, or `cd` needed:

```bash
uv run "/Users/zhangxiao/.agents/skills/bt-search/main.py" "<keyword>" [flags]
```

Requires `uv` (`brew install uv`). If uv is unavailable, install the three dependencies
into any Python ≥3.9 environment (`pip install requests beautifulsoup4 zhconv`) and run
`python3 <path>/main.py` instead.

The CLI is interactive by default. When acting as an agent, **always use non-interactive
flags** so the command completes without blocking for stdin.

## Non-interactive patterns

Single movie, auto-pick best resource, magnet only:

```bash
uv run "/Users/zhangxiao/.agents/skills/bt-search/main.py" "阿凡达" --movies 1 --magnet-only
```

Multiple movies, auto-pick best resource per movie, magnet only:

```bash
uv run "/Users/zhangxiao/.agents/skills/bt-search/main.py" "阿凡达" --movies 1,3-5 --magnet-only
```

Temporarily override preferences:

```bash
uv run "/Users/zhangxiao/.agents/skills/bt-search/main.py" "Inception" --movies 1 --resolution 2160p --prefer-original-audio --subtitles chi --magnet-only
```

## Common flags

| Flag | Meaning |
| --- | --- |
| `--movies <indices>` | Skip movie selection. Accepts `1`, `1,3`, `1-3`, `1,3-5,7`, `all`. |
| `--resource-index N` | Skip resource selection. Only valid when selecting a single movie. |
| `--magnet-only` | Print only magnet links, one per line, to stdout. |
| `--resolution` | Override resolution (`1080p`, `2160p`, `4k`, `720p`, ...). |
| `--audio` | Override audio (`guo`, `yue`, `eng`, `jpn`, `kor`). |
| `--subtitles` | Override subtitles (`chi`, `eng`, `jpn`, `kor`). |
| `--prefer-original-audio` | Prefer non-Chinese/Cantonese audio tracks. |
| `--no-hdr` / `--no-dolby-vision` | Avoid HDR / Dolby Vision resources. |
| `--max-size <size>` | Penalize oversized resources (`20`, `20GB`, `800MB`). |
| `--auto-pick` / `--interactive` | Control whether resources are auto-picked. |
| `-n N` | Limit number of search results shown. |

## Configuration

Optional user preferences live in `~/.config/bt-search/config.json` (see
`bt-search.example.json` in this skill directory for all fields: resolution, audio,
subtitles, `prefer_original_audio`, `hdr`, `dolby_vision`, `auto_pick`, `max_size_gb`).
CLI flags override the config for a single run. Note: `./bt-search.json` in the
**current working directory** is also read if present — when running as an agent the
cwd varies, so rely on `~/.config` or flags instead.

## Output handling

- With `--magnet-only`, magnet links go to **stdout** (one per line).
- Everything else (search results, tables, errors) goes to **stderr**.

## Notes

- For personal research and learning only.
- If the site structure changes and parsing fails, report the HTML fragment.
- The development home of this tool is the `movie-download` project; bug fixes made
  there should be synced into this skill directory (copy `main.py` and `bt_search/`).
