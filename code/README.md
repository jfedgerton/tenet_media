# Tenet Media / Foreign-Influence Podcast Pipeline

Does Russian funding via Tenet Media change how treated podcasts (Benny Johnson,
Dave Rubin, Tim Pool — 3 feeds pooled) discuss Russia/Ukraine, vs ~280 control
conservative podcasts? Treatment dates (DOJ indictment timeline): **2023-10**
(first payment) and **2023-11** (join / Nov 8 launch). Panel **2018-01 → 2024-08**,
truncated at the Sept 4 2024 indictment.

Hypotheses:
- **H1** — treated shows were already more pro-Russia *before* payment (selection).
- **H2** — payment shifted them further pro-Russia / anti-Ukraine (treatment).
- **H3** — payment changed the *agenda* (share of discussion on the Russia topics).

## Pipeline order

| # | File | What it does |
|---|---|---|
| 01 | `01_pull_data.py` | Pull podcast feeds / episode metadata |
| 02 | `02_download_audio.py`, `02_transcribe_missing.sbatch` | Download audio |
| 03 | `03_create_key.py` / `.R` | Episode↔show key |
| 04 | `04_transcribe.py` | Whisper transcription |
| 05 | `05_build_corpus.py` | Sentence corpus (driver) |
| 06 | `06_build_corpus_shard.*` | Sharded corpus build (HPC) |
| 07 | `07_merge_corpus.*` | Merge shards → corpus |
| 08 | `08_topic_model.*` | BERTopic model |
| 09 | `09_build_russia_class.*` | Flag Russia/Ukraine topics (78, 79) |
| 10 | `10_merge_corpus_topics.*` | → `corpus_with_topics.parquet` |
| 11 | `11_sample1500.*` | Draw 1,500 sentences for hand/LLM coding |
| 12 | `12a–12e_validation_*` | Blind validation / coding batches |
| 13 | `13_bert_label.py` + `.sbatch` | Distill c0 → label 444K topic-78/79 sentences (2-prob) |
| 14 | `14_build_panels.py` | Show-month panels (baseline + 20-rule relabel grid) |
| 15 | `15_main_analyses.R` | **H1/H2/H3 main**: OLS, matched, TWFE, SCM |
| 16 | `16_grid_sweep.R` | Relabeling robustness sweep (H1/H2) |
| 17 | `17_bert_label_4class.py` + `.sbatch` | Re-score with full 4-class softmax (for prob-shift grid) |
| 18 | `18_merge_predsfp.py` | Merge 4-prob shards → `probs_4class.csv` |
| 19 | `19_probshift_grid.R` (+`19_run_probshift.sbatch`) | **H1/H2 probability mass-transfer grid** (date sweep + OLS/matched/TWFE/matched-DiD/SCM) |
| 20 | `20_topic_distribution.py` | Recompute BERTopic topic probabilities (nearest-neighbor of 78/79) |
| 21 | `21_h3_topic_grid.R` | **H3 topic mass-transfer grid** (TWFE + SCM) |

## Methods
- Stance: distilled BERT (cardiffnlp/twitter-roberta-base-sentiment-latest, 4-class:
  positive/negative/neutral/unmentioned), per target (Russia, Ukraine). Outcomes:
  `score` = p_pos−p_neg (probability), `pos` = positive rate, `net` = (pos−neg) diff.
  Combined = Russia − Ukraine (anti-Ukraine == pro-Russia).
- DiD: TWFE (`fixest`) + synthetic control (`quadprog` simplex weights, in-space
  placebo p-values). Matching: Mahalanobis (`Matching`). Audience control = log(mean_audience).
- Seed 123 throughout.

## Not in this repo
Data, models, and large outputs are not committed (see `.gitignore`): the audio,
transcripts, `corpus_with_topics.parquet`, the BERTopic model, the labeled parquet,
and the `master_*_coefs.csv` result files. Paths assume the ROAR Collab layout
`/storage/group/LiberalArts/default/jfe4_collab/podcast/`.

## Running
HPC (SLURM). See `00_run_pipeline.sh` for submit order and dependencies. Most steps
are `sbatch` array jobs; the R analysis steps run with `module load r`.
PI: Jared Edgerton (PSU).
