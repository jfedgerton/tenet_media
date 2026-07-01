# Tenet Media / Foreign-Influence Podcast Analysis

Did Russian funding routed through **Tenet Media** change how three treated podcasts
(Benny Johnson, Dave Rubin, and Tim Pool — his three feeds pooled) discuss
Russia/Ukraine, relative to ~280 control conservative podcasts? The project transcribes
~230K episodes, models topics, classifies **stance** toward Russia/Ukraine, and uses
difference-in-differences / synthetic-control designs to measure shifts in stance,
agenda emphasis, and agenda divergence around the payment period.

**Treatment date:** `2023-10-01` — the first RT payment to Tenet (DOJ indictment: wires
Oct 2023–Aug 2024), ~1 month before Tenet's public Nov-2023 launch. Panel 2018-01 →
2024-08, truncated at the Sept 4 2024 indictment.

## Measurement (important — this is stance, not sentiment)

The analyses use **human + machine stance labeling on the Russia/Ukraine topics**, not an
off-the-shelf sentiment model:

1. **Topics.** BERTopic locates the Russia/Ukraine topics BY KEYWORD. Topic IDs change on every refit, so the old hardcoded {78, 79} no longer applies. Documents are built at 1, 3, and 5 sentences (main = 1-sentence; 3/5 = appendix).
2. **Human coding.** A sample of topic-78/79 sentences is hand/LLM-coded for *stance toward
   the target* (the validation set).
3. **Machine labeling.** A transformer classifier distilled from that human-validated set
   labels all ~444K topic-78/79 sentences — 4 classes per target: positive / negative /
   neutral / unmentioned.

Outcomes per target: `score` = p_pos − p_neg, `pos` = positive rate, `net` = (pos − neg)
ordinal. **Combined** = Russia − Ukraine (anti-Ukraine ≈ pro-Russia). The earlier generic
**sentiment** pass is deprecated and not used anywhere in the current pipeline.

## Hypotheses
- **H1** — treated hosts were already more pro-Russia *before* the payments (selection).
- **H2** — the payments pushed them further pro-Russia / anti-Ukraine (treatment).
- **H3** — the payments changed the *agenda* (Russia's share of total discussion).
- **H4** — treated hosts ran a more *divergent overall agenda* (divisive non-Russia content).

## Pipeline (article order)

Files live in `code/`. Steps `01`–`11` are the data → topic → stance-labeling construction
(HPC/SLURM); `12` builds the panels; `13`+ is the R analysis layer. Multi-script steps use
letter suffixes (e.g. `10a–10e`, `11a–11e`). **(todo)** = not yet written.

| # | Script | What it runs |
|---|--------|--------------|
| 01 | `01_pull_data.py` | Pull podcast RSS feeds → episode metadata |
| 02 | `02_download_audio.py`, `02_transcribe_missing.sbatch` | Download episode audio |
| 03 | `03_create_key.py` / `.R` | Episode ↔ show key |
| 04 | `04_transcribe.py` | Whisper ASR → transcripts |
| 05 | `05_build_corpus_shard.*` → `05_merge_corpus.*` | Sentence corpus: sharded build → merge |
| 06 | `06_topic_model.py` | BERTopic over the corpus |
| 07 | `07_identify_russia_topics.*` | Flag the Russia/Ukraine topics (78, 79) |
| 08 | `08_merge_corpus_topics.*` | Attach topic IDs to every sentence → `corpus_with_topics.parquet` |
| 09 | `09_sample_validation.*` | Draw the human-coding sample (1,500) |
| 10 | `10a–10e_validation_*.*` | Human coding / inter-coder agreement on the stance labels |
| 11 | `11a_codebook_label` → `11b_bert_build_data` → `11c_bert_train_infer` → `11d_bert_aggregate` → `11e_merge_preds` | **Stance labeling**: codebook LLM labels (`11a`, `full_opus_patched`) → BERT trainset → fine-tune RoBERTa to 4-class stance + infer over topic-78/79 sentences → merge → `opus_c0_corpus_labeled.parquet` |
| 12 | `12_build_panels.py` | show × month stance + volume panels **+ `audience_monthly.csv`** (monthly audience) |
| 13 | `13_main_h1h3.R` | **Main H1/H2/H3** — Russia/Ukraine/Combined × score/pos/net; H1 FE + matched-FE, H2/H3 TWFE + SCM |
| 14 | `14_h4_topic_model.py` (+ `14_h4_tfidf_clean.py`) | H4 agenda-divergence panel + distinctive-topic TF-IDF |
| 15 | `15_main_h4.R` | **Main H4** — agenda-divergence DiD (JSD/KL/cosine; H4a level + H4b DiD) |
| 16 | `16_grid_h1h2.R` (+ `16_summarize_grid.py`) | H1/H2 probability mass-transfer grid (+ pos/neg comment-volume counts) |
| 17 | `17_relabel_sweep.R` | Discrete relabel robustness |
| 18 | `18_label_noise.R` | Random-flip (5/10/20%) + recode label robustness (R/`fixest`) |
| 19 | `19_loso_panel.py` | Per-feed panels (Tim split) for leave-one-show-out |
| 20 | `20_loso_models.R` | 31-config leave-one-show-out across H1–H4 |
| 21 | `21_h1_inference.R` | Randomization inference for H1 |
| 22 | `22_h1_altspecs.R` | No-listen / month-FE / year-FE / host-clustered H1 |
| 23 | `23_h1_appendix.R` | Control-set series (total words), unmentioned-as-0 |
| 24 | `24_h3_topic_dist.py`, `24_h3_topic_grid.R` | H3 topic-probability sweep |
| 25 | `25_h4_divergence_grid.R` (+ `25_run_h4.sbatch`) | H4 divergence robustness grid |
| 26 | `26_min_mention_sweep.R` | Sweep the min-mentions threshold {0,1,3,5,10,20} × conditional/zero coding → coefficient distribution |
| 27+ | `tables_figures` **(todo)** | LaTeX tables + forest / event-study / sweep plots + coding-scheme exhibit |

## Designs
OLS / Mahalanobis-matched level comparison (H1); TWFE (`fixest`) + synthetic control
(`quadprog` simplex weights, in-space placebo p-values) for H2/H3; Jensen-Shannon agenda
divergence vs. the contemporaneous control consensus for H4. Time-varying total-words and
month/host fixed effects as controls. Seed 123 throughout.

## Data (not in this repo)
Audio, transcripts, `corpus_with_topics.parquet`, the BERTopic model, and `master_*`
result files are git-ignored. The repo tracks the code and the labeled stance corpus
(`data/sc_results/opus_c0_corpus_labeled.parquet`) plus the show-month panels
(`data/sc_results/*.csv`). HPC paths assume the ROAR Collab layout
`/storage/group/LiberalArts/default/jfe4_collab/podcast/`.

## Running
HPC steps are SLURM jobs (`sbatch`); the R modeling layer (`13`, `15`, `16`, `17`, `20`,
`21`–`25`) runs in RStudio locally or on Roar with `module load r` — repoint the `CO`/`SC`
path variables at the top of each script to where the panel CSVs live. PI: Jared Edgerton (PSU).

## Changes from the earlier draft
- **Renumbered into article order** (Data → Topic → Stance → Panels → H1/H2/H3 → H4 →
  Grid → Robustness), replacing the old build-order numbering.
- **Replaced "sentiment" with human + machine stance labeling on the topics**; the prior
  off-the-shelf sentiment version is deprecated and removed from the pipeline.
- **H1/H2/H3 consolidated into one script** (`13_main_h1h3.R`), written sequentially
  (no loop), 3 outcomes × 3 operationalizations.
- **H4 split into its own script** (`15_main_h4.R`), with its topic-model panel at `14`.
- **`16_grid_h1h2.R`** to additionally output positive/negative comment-volume counts for
  Russia/Ukraine/Combined *(content edit pending)*.
- **Archived** superseded scripts (`15_main_analyses.R`, `30_h1_main.R`,
  `29_best_h1_ci.R`) under `code/archive/`.

## Revision: 1/3/5-sentence windowing + Arena/Jarrett (2026-07)

Added Benny Johnson In The Arena (43 eps, pooled into treated Benny) and The Gregg Jarrett
Show (138 eps, control); corpus + BERTopic refit (~230K transcripts). Steps 05-07 now run
per document window into data/windows/{one,three,five}_sentence/:
- 05w_build_docs.py + .sbatch: within-episode, non-overlapping W-sentence docs (last chunk < W), sharded; merge_window.sbatch merges to corpus.parquet.
- 06_topic_model.py + .sbatch: BERTopic fit per window (loads show/sentence cols only, placeholder-fills empty docs, 200G).
- 07w_identify_topics.py + identify_window.sbatch: keyword Russia/Ukraine + placebo topic ID (refits renumber topics) -> topic_labels.csv, russia_corpus.parquet.
- run_windows.sh chains build -> merge -> topic -> identify for all three windows.
- H1-H4 placebo topics: immigration/border, abortion, COVID/vaccines, cancel culture, gender/trans, supreme court, China, Syria.
- Archived in code/archive/: 05_build_corpus_shard.*, 07_identify_russia_topics.*
