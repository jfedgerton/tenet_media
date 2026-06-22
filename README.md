# Tenet Media / Foreign Lobbying Podcast Analysis

## Research Question

Did a cash infusion from Russia change the coverage of Tenet Media podcast
companies? This project transcribes ~212K podcast episodes and uses topic
modeling, sentiment analysis, and synthetic control methods to measure shifts
in framing, agenda emphasis, and tone around Russia/Ukraine before vs. after
the payment period.

## Directory Structure

```
podcast/
├── code/                    # All pipeline scripts (this folder)
│   ├── 1_pull_data.py       # Step 1: scrape RSS feeds → JSON metadata
│   ├── 2_download_audio.py  # Step 2: download mp3 files
│   ├── 3_create_key.py      # Step 3: build master file key + find missing
│   ├── 4_transcribe.py      # Step 4: Whisper transcription (GPU)
│   ├── 5_build_corpus.py    # Step 5: transcripts → sentence-level DataFrame
│   ├── 6_topic_model.py     # Step 6: BERTopic modeling (GPU)
│   ├── 7_sentiment.py       # Step 7: sentiment on Russia/Ukraine topics
│   ├── 8_synthetic_control.R  # Step 8: synthetic control (R)
│   ├── 9_regression.R       # Step 9: main regression models (R)
│   ├── 10_validation.R      # Step 10: validation checks (R)
│   ├── 11_robustness.R      # Step 11: robustness / sensitivity (R)
│   ├── 12_visualization.R   # Step 12: publication figures (R)
│   ├── podcast_feeds.csv    # Input: RSS feed URLs + metadata
│   └── requirements.txt     # Python dependencies
├── slurm/                   # Slurm sbatch wrappers for each step
├── json_data/               # Per-podcast JSON from step 1
├── audio_temp/              # Downloaded mp3 files (step 2, deleted after step 4)
├── transcript_key/          # Transcripts organized by show (step 4 output)
│   └── {show_name}/         # One subfolder per podcast
│       └── {show}_{date}_{ep}.txt
├── data/                    # Intermediate datasets
│   ├── corpus.parquet       # Sentence-level corpus (step 5 output)
│   ├── topics.parquet       # Topic assignments (step 6 output)
│   ├── topic_model/         # Saved BERTopic model artifacts
│   ├── sentiment.parquet    # Sentiment scores (step 7 output)
│   └── analysis_ready.csv   # Final merged dataset for R (step 7 output)
├── output/                  # R analysis outputs
│   ├── figures/             # Publication-quality plots
│   ├── tables/              # Regression tables
│   └── results/             # Model objects, diagnostics
├── file_key.csv             # Master episode key
├── missing_files.csv        # Episodes still needing transcription
└── logs/                    # Slurm log files
```

## Pipeline Overview

### Data Collection (Python)

| Step | Script | Input | Output | HPC? |
|------|--------|-------|--------|------|
| 1 | `1_pull_data.py` | `podcast_feeds.csv` | `json_data/*.json` | CPU |
| 2 | `2_download_audio.py` | `json_data/*.json` | `audio_temp/*.mp3` | CPU |
| 3 | `3_create_key.py` | `json_data/*.json` + `transcript_key/` | `file_key.csv`, `missing_files.csv` | CPU |
| 4 | `4_transcribe.py` | `missing_files.csv` + `audio_temp/` | `transcript_key/{show}/*.txt` | GPU (A100) |

### NLP Processing (Python, GPU recommended)

| Step | Script | Input | Output | HPC? |
|------|--------|-------|--------|------|
| 5 | `5_build_corpus.py` | `transcript_key/` | `data/corpus.parquet` | CPU |
| 6 | `6_topic_model.py` | `data/corpus.parquet` | `data/topics.parquet`, `data/topic_model/` | GPU |
| 7 | `7_sentiment.py` | `data/corpus.parquet` + `data/topics.parquet` | `data/sentiment.parquet`, `data/analysis_ready.csv` | GPU |

### Statistical Analysis (R)

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 8 | `8_synthetic_control.R` | `data/analysis_ready.csv` | synthetic control weights + estimates |
| 9 | `9_regression.R` | `data/analysis_ready.csv` | regression tables |
| 10 | `10_validation.R` | model outputs | placebo tests, pre-trend checks |
| 11 | `11_robustness.R` | `data/analysis_ready.csv` | alternative specifications |
| 12 | `12_visualization.R` | all outputs | `output/figures/*.pdf` |

## File Naming Convention

Audio and transcript files follow this pattern:
```
{show_name}_{YYYYMMDDHHMMSS}_{episode_number}.{ext}
```
- `show_name`: podcast slug (e.g., `bannon_s_war_room`)
- `YYYYMMDDHHMMSS`: air date as 14-digit timestamp
- `episode_number`: integer episode ID from Podchaser/RSS
- `ext`: `.mp3` for audio, `.txt` for transcripts

## Key Dates

- **Treatment window**: The period when Russian payments flowed to Tenet Media.
  Defined in `9_regression.R` as `TREATMENT_START` and `TREATMENT_END`.
- **Indictment**: DOJ indictment date, used as an alternative cutoff.

## Running on ROAR Collab

Each step has a corresponding sbatch file in `slurm/`. Example:

```bash
# Step 1: pull RSS data
sbatch slurm/01_pull_data.sbatch

# Step 4: transcribe (GPU array job)
sbatch slurm/04_transcribe.sbatch

# Step 6: topic model (single GPU)
sbatch slurm/06_topic_model.sbatch
```

GPU steps use `--constraint=a100 --partition=standard --account=jfe4_cr_default`.
CPU-only steps use `--partition=basic` (free tier).

## For the Grad Student

1. **Start here**: Read this README, then skim `file_key.csv` to understand the
   data scope (~212K episodes across ~200 podcasts).
2. **Data collection is done**: Steps 1-4 are complete. Transcripts live in
   `transcript_key/`. You should not need to rerun these unless adding new shows.
3. **Your work starts at step 5**: Run `5_build_corpus.py` to build the sentence
   dataset, then proceed sequentially.
4. **Python environment**: `module load python/3.11.2` then activate the venv at
   `../venv/`. Install any missing packages with `pip install -r requirements.txt`.
5. **R environment**: `module load r/4.3.1`. Install packages to a local library
   with `.libPaths()`.
6. **Tenet shows**: The list of Tenet-affiliated podcasts is defined in
   `7_sentiment.py` as `TENET_SHOWS`. Update if the list changes.
