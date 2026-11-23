# archive/

Code that is not part of the active pipeline in `code/`. It is kept for the record and
nothing in `code/` calls it. Old → new names for every move are in `RENAMES.md`.

## pre_two_stage/ — earlier measurement design (topic 78/79 sample + LLM/BERT distillation)
| File | What it was |
|---|---|
| `09_sample_validation.*` | 1,500-sentence validation sample from topics 78/79 |
| `10a–10c_validation_freshtest*.*` | Fresh test draws excluding earlier samples |
| `10d_validation_stance_sample.*` | Stance sample with neighbor-sentence context |
| `10e_validation_vset.*` | Validation set draw |
| `11a_codebook_label.py`, `11a_codebook_label_run.py`, `11a_stance_codebook.md` | 8-condition LLM codebook labeling (bias sensitivity) |
| `11b_bert_build_data.py` | Per-(coder, condition) training tables + human-gold test |
| `11c_bert_train_infer.py`, `11c_bert_grid.sbatch` | RoBERTa fine-tune + inference grid |
| `11d_bert_aggregate.py` | Merge prediction shards per cell |
| `11e_merge_preds.py` | Merge 4-class softmax shards → `opus_c0_corpus_labeled.parquet` |

Replaced by human double-coding (`code/3_human_coding`) and the two-stage gate + stance
classifier (`code/4_classify`).

## superseded/ — replaced by a newer version in `code/`
| File | Replaced by |
|---|---|
| `02_transcribe_missing.sbatch` | `code/slurm/04_transcribe.sbatch` (legacy paths) |
| `05_build_corpus_shard.*` | `05_build_sentence_docs.py` (windowed) |
| `07_identify_russia_topics.*` | `08_identify_topics.py` (keyword topic ID; refits renumber topics) |
| `build_label_pools.*`, `build_label_pools_v2.*` | `09_build_label_pools.py` (was v3) |
| `build_workbooks.py` | `15_rebuild_reduced_design.py` |
| `16_grid_h1h2_v2.R` | `30_grid_h1h2.R` (31 reads the v1 output) |
| `16_summarize_grid.py` | `31_grid_summary.R` (read an orphaned probshift CSV) |
| `25_run_h4.sbatch` | none needed (legacy paths) |

## coding_history/ — one-off inter-coder checks from earlier rounds
| File | What it was |
|---|---|
| `icr200.py` | 200-sentence ICR round |
| `icr_round3.py` | ICR round 3 |
| `icr_supp.py` | Supplementary ICR check |

## exploratory/ — not used in the manuscript
| File | What it was |
|---|---|
| `31_ranked_prepost.R` | Standalone ranked pre/post figure |
| `sample_3sent_ru*.{py,sbatch}` (v1, v2) | 3-sentence Russia sample draws |

## slurm_runs/ — one-off batch wrappers for past runs
`fig29.sbatch`, `grid16_3day.sbatch`, `rerun_figs24.sbatch`, `run_final_all.sbatch`,
`run_grid_all.sbatch`, `run_rerun_benny.sbatch`. They call old script names and are kept
only as a record of what was run.
