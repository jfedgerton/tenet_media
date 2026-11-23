# Code folder cleanup review

Status legend:
- **KEEP-current** — part of the active BERT-distilled-stance pipeline (H1/H2/H3 + grid)
- **KEEP-upstream** — builds the corpus/topics; run-once foundation, still needed to regenerate data
- **LEGACY** — earlier sentiment/NLI-era analysis, superseded by the BERT pipeline (keep for reference/old results, but not the live path)
- **SUPERSEDED** — an earlier draft of a *current* step, replaced by a newer file here
- **SCRATCH** — temp / smoke / diagnostic; safe to delete

> Note: I authored the BERT-era + analysis files (so those statuses are certain). The numbered `1_`–`12_`/`9x_` files are the original pipeline — I'm inferring their role from names and the few I read; please sanity-check those.

## A. Upstream data → corpus → topics (KEEP-upstream)
| Script | What it does | Status |
|---|---|---|
| 1_pull_data.py, run_pull_data.sbatch | Pull podcast feed/episode metadata | KEEP-upstream |
| podcast_feeds.csv, podcast_rss_feeds_reference.xlsx | Feed list / reference | KEEP-upstream |
| 2_download_audio.py, download_audio.sbatch, transcribe_missing.sbatch | Download audio | KEEP-upstream |
| 3_create_key.py / .R | Build episode/show key | KEEP-upstream |
| 4_transcribe.py | Whisper transcription | KEEP-upstream |
| 5_build_corpus.py, 5b_build_corpus_shard.py/.sbatch, 5c_merge_corpus.py/.sbatch | Build sentence corpus (sharded + merge) | KEEP-upstream |
| 6_topic_model.py/.sbatch, 6b_build_russia_class.py/.sbatch, 6c_merge_corpus_topics.py/.sbatch | BERTopic model + merge topics → corpus_with_topics.parquet | KEEP-upstream |
| 6_topic_model.py.bak | Backup of topic script | SCRATCH |
| requirements.txt, code_setup.txt | Env setup | KEEP-upstream |

## B. Legacy sentiment / NLI analysis (pre-BERT; LEGACY)
| Script | What it does | Status |
|---|---|---|
| 7_sentiment.py/.sbatch | RoBERTa sentiment on Russia-keyword sentences | LEGACY |
| 7b_sentiment_full.py/.sbatch | Sentiment over full corpus | LEGACY |
| 7c_nli_stance.py/.sbatch, cache_nli.py | NLI-based stance scoring | LEGACY |
| 8_synthetic_control.R, 8a/8b/8c_*_agg.py/.sbatch | SC + topic/keyword aggregations | LEGACY |
| 9_regression.R, 9_monthly_sentiment_panel.py/.sbatch | DiD on sentiment; monthly panel | LEGACY |
| 9b_synthetic_control.R/.sbatch, 9c_all_topics_baseline.*, 9d_build_xlsx.py, 9e_robust.R/.sbatch | SC + baselines + robustness (sentiment era) | LEGACY |
| 9g_*(did2), 9h_*(topic_sentiment), 9i_label_did2.py, 9j_topic_breakdown.py | Agenda/topic-sentiment DiD #2 | LEGACY |
| 9k_rerun_correct_dates.R/.sbatch | Re-run with corrected treatment dates | LEGACY |
| 9l_h1_pretreatment.R/.sbatch | H1 pre-treatment (sentiment) | LEGACY |
| 9m_build_h_panels.py | Earlier H-panel builder (sentiment) | LEGACY |
| 9n_h_analysis.R/.sbatch, 9q_h_revised.R/.sbatch | H1–H4 analysis (sentiment) | LEGACY |
| 9o_text_overlap.py/.sbatch | Verbatim overlap across Tenet shows | LEGACY (one-off finding) |
| 9p_jsd_agg.py, 9r_h4_diag.py | H4 (JSD) divergence | LEGACY |
| 9t_parallel_trends.R | Parallel-trends / SC plots | LEGACY (port plotting later) |
| 9u_stance_by_topic.py, 9v_nli_target.py/.sbatch, 9w_target_panels.py, 9x_target_analysis.R | Per-target (Russia/Ukraine/Assad) NLI stance + panels | LEGACY |
| 10_validation.R, 11_robustness.R, 12_visualization.R | Validation / robustness / figures (sentiment era) | LEGACY (port figures later) |

## C. Stance hand-coding + BERT distillation (measure construction)
| Script | What it does | Status |
|---|---|---|
| 9aa_sample1500.py/.sbatch | Drew the ~1,500 sentences for hand/LLM coding | KEEP-current (provenance) |
| 9bb_freshtest.py/.sbatch, 9cc_freshtest2.*, 9dd_freshtest3.* | Built the blind validation batches | KEEP-current (validation) |
| 9s_stance_sample.py/.sbatch, 9y_vset_v2.py/.sbatch | Stance sampling / validation set | KEEP-current (validation) |
| bert_train_infer.py | **THE BERT train+infer script** (distill c0 → label 440K) | KEEP-current |
| label_opus_c0.sbatch | Sharded c0 labeling job → opus_c0_corpus_labeled.parquet | KEEP-current |
| bert_grid.sbatch, label_grid.sbatch, bert_aggregate.py, grid_did.py | 18-cell coder×condition robustness grid (codex dropped) | SUPERSEDED (mostly) |
| bert_smoke.sbatch, chk_bertenv.py, build_test_corpus.py, inv_labels.py | Smoke test / env check / scratch | SCRATCH |

## D. Current analysis: panels + H1/H2/H3 + grid (KEEP-current)
| Script | What it does | Status |
|---|---|---|
| build_h_panels.py | **Builds baseline_panel.csv + perturb_panels_all.csv** (the one Python prep) | KEEP-current |
| main_analyses.R | **Baseline H1/H2/H3** (OLS, matched, TWFE, SCM) for 9 stance outcomes + H3 | KEEP-current |
| grid_sweep.R | **20-rule perturbation sweep** of H1/H2 across 9 outcomes | KEEP-current |
| build_opus_panels.py, build_perturb_panels.py, build_perturb_panels_all.py | Earlier panel builders | SUPERSEDED by build_h_panels.py |
| h1h2_audience.R | Headline-only H1/H2 with audience (first cut) | SUPERSEDED by main_analyses.R |
| h1h2_opus_allschemes.R | Opus c0–c9 loop (first sweep) | SUPERSEDED by grid_sweep.R |
| h1h2_master.R | Combined draft | SUPERSEDED |
| h1_perturb.R | First perturbation sweep | SUPERSEDED by grid_sweep.R |
| run_did.py, run_scm.py | Python DiD/SCM (before moving to R) | SUPERSEDED by R scripts |

## E. Other
| Script | What it does | Status |
|---|---|---|
| CLAUDE_MEMORY.md | Project memory notes | KEEP |
| `_*` files (≈30) | My scratch/log/status temp files | SCRATCH |

## Suggested "clean" set (the live pipeline)
Upstream: `1_`–`6c_` → `corpus_with_topics.parquet`
Measure: `9aa`/`9bb`/`9cc`/`9dd` (coding+validation) → `bert_train_infer.py` + `label_opus_c0.sbatch` → `opus_c0_corpus_labeled.parquet`
Analysis: `build_h_panels.py` → `main_analyses.R` + `grid_sweep.R`
(Plus the pending 4-class re-inference for the probability-shift grid.)

Everything in **SUPERSEDED** and **SCRATCH** can be archived/deleted once you confirm.
