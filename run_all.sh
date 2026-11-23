#!/bin/bash
# run_all.sh -- the Tenet Media pipeline in run order (steps 01-49).
#
#   ./run_all.sh                 print every command (dry run, the default)
#   ./run_all.sh --stage 5       print stage 5 only
#   ./run_all.sh --stage 5 --run actually run stage 5 (local stages 5-7 only)
#
# Cluster stages (1, 2, 4) are ALWAYS print-only, even with --run. sbatch returns as soon
# as a job is queued, so running them back to back would start later steps on missing or
# stale inputs. Submit them by hand, in order, waiting for each job (or use the dependency
# chain inside code/slurm/run_corpus_05_to_08.sh). --run also requires an explicit --stage.
# Planned steps (placeholders that raise an error) are skipped and reported.
# Design-time steps 10-16 already ran and build the coder files. They are listed but never
# re-run here, because re-running would overwrite the files coders are working in.
# Roar paths: COLLAB is the data root (see config/README.md). Seed 123 throughout.
set -euo pipefail
cd "$(dirname "$0")"
export COLLAB=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}

STAGE=all; RUN=0
while [ $# -gt 0 ]; do
  case $1 in
    --stage) STAGE=$2; shift 2;;
    --run) RUN=1; shift;;
    *) echo "unknown arg $1"; exit 1;;
  esac
done

do_cmd () { if [ $RUN -eq 1 ]; then echo "+ $*"; eval "$@"; else echo "  $*"; fi; }
cluster () { echo "  $*"; }                       # never executed; see header
planned () { echo "  [skip] $1 -- planned, not yet implemented"; }
want () { [ "$STAGE" = all ] || [ "$STAGE" = "$1" ]; }
if [ $RUN -eq 1 ] && [ "$STAGE" = all ]; then echo "--run needs --stage 5, 6 or 7"; exit 1; fi
case "$STAGE" in 1|2|4) [ $RUN -eq 1 ] && echo "(stage $STAGE is a cluster stage: printing only, nothing is run)";; esac

if want 1; then echo "== 1_collect (Roar; run each after the previous job finishes) =="
  cluster sbatch code/slurm/01_pull_data.sbatch
  cluster sbatch code/slurm/02_download_audio.sbatch
  cluster python code/1_collect/03_create_key.py
  cluster "sbatch --array=0-<rows in \$COLLAB/file_key.csv minus 1> code/slurm/04_transcribe.sbatch"
fi

if want 2; then echo "== 2_corpus (Roar) =="
  cluster bash code/slurm/run_corpus_05_to_08.sh       # chains 05 -> 06 -> 07 -> 08 per window with afterok dependencies
  cluster sbatch code/slurm/09_build_label_pools.sbatch # after all 08 jobs finish
fi

if want 3; then echo "== 3_human_coding =="
  echo "  [design-time, already run] 10_draw_union_sample 11_draw_nonunion_sample 12_build_disney_pool"
  echo "  [design-time, already run] 13_assign_coders 14_assign_placebo 15_rebuild_reduced_design 16_release_reduced_design"
  planned 17_build_adjudication
  planned 18_icr_report
  planned 19_lock_gold
fi

if want 4; then echo "== 4_classify (Roar GPU) =="
  planned 20_gate_train
  planned 21_gate_infer
  planned 22_stance_train
  planned 23_stance_infer
  planned 24_merge_predictions
fi

if want 5; then echo "== 5_analysis =="
  do_cmd python code/5_analysis/25_build_panels.py
  do_cmd Rscript code/5_analysis/26_main_h1h3.R
  do_cmd python code/5_analysis/27_h4_tfidf_clean.py
  do_cmd python code/5_analysis/28_h4_topic_model.py
  do_cmd Rscript code/5_analysis/29_main_h4.R
fi

if want 6; then echo "== 6_robustness =="
  do_cmd Rscript code/6_robustness/30_grid_h1h2.R
  do_cmd Rscript code/6_robustness/31_grid_summary.R
  do_cmd Rscript code/6_robustness/32_relabel_sweep.R
  do_cmd Rscript code/6_robustness/33_label_noise.R
  planned 34_error_propagation
  do_cmd Rscript code/6_robustness/35_power_analysis.R
  do_cmd python code/6_robustness/36_loso_panel.py
  do_cmd Rscript code/6_robustness/37_loso_models.R
  do_cmd Rscript code/6_robustness/38_h1_inference.R
  do_cmd Rscript code/6_robustness/39_h1_altspecs.R
  do_cmd Rscript code/6_robustness/40_h1_appendix.R
  do_cmd python code/6_robustness/41_h3_topic_dist.py
  do_cmd Rscript code/6_robustness/42_h3_topic_grid.R
  do_cmd Rscript code/6_robustness/43_h4_divergence_grid.R
  do_cmd Rscript code/6_robustness/44_min_mention_sweep.R
fi

if want 7; then echo "== 7_outputs =="
  do_cmd Rscript code/7_outputs/45_descriptives.R
  do_cmd python code/7_outputs/46_label_examples.py
  do_cmd Rscript code/7_outputs/47_figures.R
  do_cmd Rscript code/7_outputs/48_make_tables.R
  do_cmd Rscript code/7_outputs/49_manuscript_tables.R
fi

[ $RUN -eq 1 ] || echo "(dry run -- add --run to execute)"
