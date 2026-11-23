# Podcast Analysis Project — Session Notes

## Project Overview
- Collecting podcast audio data for a set of **treated** and **control** right-wing podcasts (290 total: 5 treated, 285 control).
- Pipeline: pull RSS → download audio → create key → transcribe (Whisper) → sentence docs → BERT embeddings → topic model → stance analysis → R analysis/figures/tables.

## Control Group Shows
| pid    | slug                   | RSS source   |
|--------|------------------------|--------------|
| 900101 | louder_with_crowder    | Libsyn       |
| 900102 | howie_carr_radio       | Simplecast   |
| 900103 | michael_knowles_show   | Megaphone    |
| 900104 | ben_ferguson_podcast   | OmnyContent  |
| 900105 | jesse_kelly_show       | OmnyContent  |
| 900106 | gold_goats_n_guns      | Spreaker     |

## What Was Done
1. **`1_pull_data.py`** — Rewrote to read from `podcast_feeds.csv` (columns: `podcast_id,title,slug,rss_url,treated`). Uses `PROJECT_ROOT = Path(__file__).resolve().parent.parent`. Supports `--only-treated`, `--only-control`, `--podcast-id`, `--feeds-csv` flags. Outputs JSON per show to `json_data/`.
2. **`2_download_audio.py`** — Reads directly from JSON files in `json_data/` instead of `missing_files.csv`. Naming convention: `{json_name}_{date_id}_{episode_number}.mp3`. Same retry/round logic preserved.
3. **`podcast_feeds.csv`** — 290 shows (5 treated, 285 control) with columns: `podcast_id,title,slug,rss_url,treated`.
4. **`run_pull_data.sbatch`** — Sbatch script for ROAR Collab. Uses `--partition=open`, `--account=jfe4_cr_default`, 4G mem, 2hr time limit. Runs `1_pull_data.py` from `/scratch/jfe4/podcast/code/`.
5. **`podcast_rss_feeds_reference.xlsx`** — Reference spreadsheet with all 290 shows, metadata, RSS URLs, power scores.
6. **`code_setup.txt`** — Planned pipeline (steps 6-11 not yet written; grad RA will work on those as a learning activity).

## What's Next
- Upload correct `podcast_feeds.csv` and `run_pull_data.sbatch` to ROAR at `/scratch/jfe4/podcast/code/`.
- Run `sbatch run_pull_data.sbatch` to pull RSS data for all 290 shows.
- Steps 3-5 exist and should work downstream once audio is downloaded.
- Steps 6-11 (BERT, topic model, stance, R analysis, figures, tables) are for the PhD student RA to implement.

## Notes
- Spreaker RSS feeds may paginate (~100 episodes). If Gold Goats 'n Guns has a larger back catalog, may need Spreaker API for older episodes.
- Transcription uses Whisper `small` model with CUDA on the supercomputer.
- `3_create_key.R` has hardcoded paths starting with `"podcast_analysis/"` — runs from the Dropbox root, not from inside `podcast_analysis/`.
