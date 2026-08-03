---
name: bt-search
description: >
  Search movies and TV shows on btbtla.com and return magnet / download links.
  Trigger when the user asks to search a movie, get a magnet, use bt-search,
  download a film or show, or similar.
version: 0.3.0
---

# bt-search

Search for films or shows on btbtla.com and retrieve their magnet / thunder download links.

This skill is **self-contained**: the full CLI (`main.py` + the `bt_search` package)
ships inside this skill directory and can be run from anywhere.

The CLI only searches, lists, and fetches links — it **never picks a resource for you**.
Picking the best resource is your job (the model's); the heuristics are below.

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

The CLI is interactive only when stdin is a TTY. When acting as an agent, stdin is not
a TTY, so each command below runs to completion without blocking.

## Agent workflow

Three runs: search → list resources → fetch the link you picked.

1. **Search** and read the movie list (printed to stderr):

   ```bash
   uv run "/Users/zhangxiao/.agents/skills/bt-search/main.py" "阿凡达"
   ```

2. **List resources** for the movie index you chose (table goes to stderr, then exits):

   ```bash
   uv run "/Users/zhangxiao/.agents/skills/bt-search/main.py" "阿凡达" --movies 1
   ```

3. **Pick one resource** using the heuristics below, then fetch its magnet
   (stdout carries the magnet, one per line):

   ```bash
   uv run "/Users/zhangxiao/.agents/skills/bt-search/main.py" "阿凡达" --movies 1 --resource-index 22 --magnet-only
   ```

For several movies, repeat steps 2–3 per movie (`--resource-index` only accepts a
single movie at a time).

## How to pick a resource

Judge from the resource title, size, and download count in the table. The user's
explicit request always wins; otherwise apply these defaults:

- **TV shows**: prefer a **complete-season pack** — titles saying `全集`/`全季`/`合集`/
  `全XX集`/`Complete`/`Season`/`S01` (whole season, not one episode) — over single
  episodes (`E01`/`S01E01`/`第X集`). Only pick single episodes when no pack exists
  or the user asks for specific episodes. A full-season pack is naturally much
  bigger than one episode, so don't penalize it on size.
- **Resolution**: default to `1080p`. Aliases: `4K`/`UHD`/`2160p` are the same tier,
  as are `FHD`/`1080p` and `HD`/`720p`. If the preferred tier is missing, prefer one
  tier **higher** over going lower.
- **Audio**: `国语`/`普通话`/`国配` = Mandarin, `粤语` = Cantonese. For foreign films
  prefer the **original audio** (i.e. not 国语/粤语 dub) with Chinese subtitles;
  `X国Y多音轨` means multiple tracks and satisfies both.
- **Subtitles**: `中字`/`中英`/`双语`/`简中`/`繁中` all count as Chinese subtitles.
  Default to wanting Chinese subtitles unless the user says otherwise.
- **HDR / Dolby Vision**: titles mark `HDR`/`HDR10`/`DV`/`DoVi`/`杜比视界`. Only pick
  these when the user's setup supports them; otherwise prefer the SDR equivalent.
- **Size**: sanity-check against the tier — a 4K movie is typically ≤ 20 GB, 1080p
  ≤ 8 GB, 720p ≤ 4 GB. Far larger usually means a REMUX/原盘 or a pack; only choose
  those if the user wants full-disc quality.
- **Download count**: the tiebreaker — higher is healthier. Be wary of 0-download
  entries when alternatives exist.

State your pick and the reason briefly before fetching the link.

## Flags

| Flag | Meaning |
| --- | --- |
| `--movies <indices>` | Skip movie selection. Accepts `1`, `1,3`, `1-3`, `1,3-5,7`, `all`. |
| `--resource-index N` | Fetch this resource's links. Single movie only. |
| `--magnet-only` | Print only magnet links, one per line, to stdout. |
| `-n N` | Limit number of search results shown (default 10). |

## Output handling

- With `--magnet-only`, magnet links go to **stdout** (one per line).
- Everything else (search results, resource tables, hints, errors) goes to **stderr**.

## Notes

- For personal research and learning only.
- If the site structure changes and parsing fails, report the HTML fragment.
- Offline tests live in `tests/` (stdlib unittest, no network). Run from this directory:
  `uv run --with requests --with beautifulsoup4 --with zhconv python -m unittest discover -s tests -t .`
- The development home of this tool is the `movie-download` project; bug fixes made
  there should be synced into this skill directory (copy `main.py` and `bt_search/`).
