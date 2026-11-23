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
2. **Human coding.** 8,000 one-sentence documents (union of Russia/Ukraine topic sentences,
   hard negatives, pre/post non-union draws, and 1,000 placebo-entity sentences) are
   double-coded for *stance toward each target* (codebook v2.6; placebo v1.3) and
   adjudicated to a gold set.
3. **Machine labeling (two-stage).** A relevance gate (mentioned vs. unmentioned) is
   trained on the gold set and run over the full one-sentence corpus; a 4-class stance
   model (positive / negative / neutral / unmentioned, per target) then labels the
   gate-passing sentences. Human-label error is propagated into H1/H2 (step 34).

Outcomes per target: `score` = p_pos − p_neg, `pos` = positive rate, `net` = (pos − neg)
ordinal. **Combined** = Russia − Ukraine (anti-Ukraine ≈ pro-Russia). The earlier generic
**sentiment** pass is deprecated and not used anywhere in the current pipeline.

## Hypotheses
- **H1** — treated hosts were already more pro-Russia *before* the payments (selection).
- **H2** — the payments pushed them further pro-Russia / anti-Ukraine (treatment).
- **H3** — the payments changed the *agenda* (Russia's share of total discussion).
- **H4** — treated hosts ran a more *divergent overall agenda* (divisive non-Russia content).

## Pipeline

Every active script has a unique two-digit number (01–49) in run order. Stages are folders.
`code/slurm/` holds the Roar job files (named for the step they run). Superseded and
exploratory code is in `archive/` (see `archive/README.md`; old → new names in
`archive/RENAMES.md`). Status as of 2026-11-23: **done** = has run on Roar and its output
exists; **re-run** = built and run on the earlier labels, must re-run once step 24 exists;
**planned** = placeholder that raises an error.

| # | Script | Does | Status |
|---|--------|------|--------|
| **1_collect** | | | |
| 01 | `01_pull_data.py` | RSS feeds (`inputs/podcast_feeds.csv`) → episode metadata JSON | done |
| 02 | `02_download_audio.py` | Download episode MP3s | done |
| 03 | `03_create_key.py` | File key; flag missing transcripts | done |
| 04 | `04_transcribe.py` | Whisper ASR → transcripts | done |
| **2_corpus** | | | |
| 05 | `05_build_sentence_docs.py` | Within-episode W-sentence documents (W = 1/3/5), sharded | done |
| 06 | `06_merge_windows.py` | Merge shards → `data/windows/{W}/corpus.parquet` | done |
| 07 | `07_topic_model.py` | BERTopic fit per window | done |
| 08 | `08_identify_topics.py` | Keyword-match Russia/Ukraine + placebo topics → `topic_labels.csv`, `russia_corpus.parquet` | done |
| 09 | `09_build_label_pools.py` | Regex label pools (Russia/Ukraine + placebo entities) → `label_sheets_fixed/` | done |
| **3_human_coding** | | | |
| 10 | `10_draw_union_sample.py` | Draw union-of-topics coding sample | done |
| 11 | `11_draw_nonunion_sample.py` | Draw non-union strata (pre/post) + hard negatives | done |
| 12 | `12_build_disney_pool.py` | Disney placebo pool | done |
| 13 | `13_assign_coders.py` | Original coder assignment (Oct 9) | done; superseded by 15 |
| 14 | `14_assign_placebo.py` | Placebo assignment (Oct 9) | done; superseded by 15 |
| 15 | `15_rebuild_reduced_design.py` | Reduced 8,000-sentence design; every sentence = Jared + 1 student. Test: `tests/test_15_rebuild_reduced_design.py` | done (Nov 23); audited Nov 23 |
| 16 | `16_release_reduced_design.py` | One-time release of 15's files to coder Dropbox folders | done (Nov 30 schedule) |
| 17 | `17_build_adjudication.py` | Blind A/B adjudication sheets from disagreements | planned |
| 18 | `18_icr_report.py` | Krippendorff's α from raw codes, by target/stratum/pair | planned |
| 19 | `19_lock_gold.py` | Freeze adjudicated gold set + confusion matrices | planned |
| **4_classify** | | | |
| 20 | `20_gate_train.py` | Train relevance gate on gold (seed 123) | planned |
| 21 | `21_gate_infer.py` | Gate over full one-sentence corpus | planned |
| 22 | `22_stance_train.py` | Train 4-class stance × 2 targets (twitter-roberta, seed 123) | planned |
| 23 | `23_stance_infer.py` | Stance over gate-passing sentences | planned |
| 24 | `24_merge_predictions.py` | Writes `data/windows/one_sentence/corpus_with_topics.parquet` (read by 25, 27, 28, 36, 41, 46) and the sentence-level label file for 25/36/46, keyed by a unique `uid`. Also repoints 27/28/41 to the windowed topic model and 46 to `uid`. Contract in the script header | planned |
| **5_analysis** | | | |
| 25 | `25_build_panels.py` | Show × month stance/volume panels + audience | re-run |
| 26 | `26_main_h1h3.R` | Main H1/H2/H3 (FE, matched FE, TWFE, SCM) | re-run |
| 27 | `27_h4_tfidf_clean.py` | H4 distinctive-topic TF-IDF | re-run |
| 28 | `28_h4_topic_model.py` | H4 agenda-divergence panel | re-run |
| 29 | `29_main_h4.R` | Main H4 (JSD/KL/cosine DiD) | re-run |
| **6_robustness** | | | |
| 30 | `30_grid_h1h2.R` | H1/H2 probability mass-transfer grid | re-run |
| 31 | `31_grid_summary.R` | Summarize 30 | re-run |
| 32 | `32_relabel_sweep.R` | Discrete relabel sweep | re-run |
| 33 | `33_label_noise.R` | Random-flip / recode label noise | re-run |
| 34 | `34_error_propagation.R` | Confusion-matrix MI of human-label error through H1/H2 | planned |
| 35 | `35_power_analysis.R` | MDE / power, post-payment | re-run |
| 36 | `36_loso_panel.py` | Per-feed panels (Tim split) | re-run |
| 37 | `37_loso_models.R` | Leave-one-show-out, H1–H4 | re-run |
| 38 | `38_h1_inference.R` | Randomization inference, H1 | re-run |
| 39 | `39_h1_altspecs.R` | Alternative H1 specs | re-run |
| 40 | `40_h1_appendix.R` | H1 appendix series | re-run |
| 41 | `41_h3_topic_dist.py` | Per-sentence topic probabilities for H3 | re-run |
| 42 | `42_h3_topic_grid.R` | H3 topic mass-transfer grid | re-run |
| 43 | `43_h4_divergence_grid.R` | H4 divergence grid | re-run |
| 44 | `44_min_mention_sweep.R` | Min-mentions threshold sweep | re-run |
| **7_outputs** | | | |
| 45 | `45_descriptives.R` | Descriptives table | re-run |
| 46 | `46_label_examples.py` | Coding-scheme exhibit | re-run |
| 47 | `47_figures.R` | Publication figures H1–H4 | re-run |
| 48 | `48_make_tables.R` | Manuscript tables (LaTeX) | re-run |
| 49 | `49_manuscript_tables.R` | Formatted Tables 1–3 | re-run |

Repo layout: `code/` (pipeline), `code/slurm/` (Roar jobs), `config/` (environments,
paths), `inputs/` (feed lists), `docs/` (audit prompts, notes), `tests/`, `archive/`.

## Designs
OLS / Mahalanobis-matched level comparison (H1); TWFE (`fixest`) + synthetic control
(`quadprog` simplex weights, in-space placebo p-values) for H2/H3; Jensen-Shannon agenda
divergence vs. the contemporaneous control consensus for H4. Time-varying total-words and
month/host fixed effects as controls. Seed 123 throughout.

## Data (not in this repo)
Audio, transcripts, corpora, topic models, coder files and results live on Roar Collab
under `$COLLAB` (default `/storage/group/LiberalArts/default/jfe4_collab/podcast`) and, for
human coding, in Dropbox (`podcast_analysis/coder_materials`, `coder_review`). See
`config/README.md`. Data-access plan for replication: TBD.

## Running
`run_all.sh` prints every step in order (dry run). `./run_all.sh --stage 5 --run` runs one
local stage (5, 6 or 7). Cluster stages 1, 2 and 4 are always print-only. Submit those by hand
in order and wait for each job, because `sbatch` returns before a job finishes. Planned steps
are skipped. Every slurm file uses `$COLLAB` if it is set. The R layer runs with `module load r`
on Roar or locally. Seed 123 throughout. Test of step 15:
`python3 tests/test_15_rebuild_reduced_design.py` (about 30 seconds, fake data).

Known gaps
- Steps 25–49 cannot run until step 24 exists. The old `data/corpus_with_topics.parquet` is from
  the pre-windowing corpus, and the step that built it was deleted in July (commit 989f0a9).
  Step 25 skips its volume panel with a warning, rather than failing, if that file is missing.
- Many analysis scripts still hard-code `/storage/...` paths (to be moved to `$COLLAB`).
  `#SBATCH --output` log paths cannot use variables and stay hard-coded.
- 01/02 slurm logs point at `/scratch` from the 2025 collection run.
- Environments are listed in `config/` but not pinned.

PI: Jared Edgerton (PSU).
