#!/bin/bash
#SBATCH --job-name=finalall
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/finalall_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/finalall_%j.err
#SBATCH --time=24:00:00
#SBATCH --mem=96G
#SBATCH --cpus-per-task=16
#SBATCH --account=jfe4_cr_default
#SBATCH --partition=standard
set -uo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
cd $COLLAB/tenet_media_repo
echo FINAL_START $(date) on $(hostname)
# ---- python prep (loso panel, h3 topic dist, label examples) ----
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
for p in 19_loso_panel 24_h3_topic_dist 28_label_examples; do echo "### $p ###"; python code/$p.py; echo "EXIT $p = $?"; done
deactivate 2>/dev/null || true
module purge
# ---- R: main analyses, grids/sensitivity, then tables/figures ----
module load r/4.2.1
for s in 13_main_h1h3 15_main_h4 16_grid_h1h2 17_relabel_sweep 18_label_noise 20_loso_models 21_h1_inference 22_h1_altspecs 23_h1_appendix 24_h3_topic_grid 25_h4_divergence_grid 26_min_mention_sweep 27_descriptives 29_figures 30_make_tables 31_ranked_prepost; do
  echo "### $s START $(date) ###"
  Rscript code/$s.R; echo "EXIT $s = $?"
done
echo FINAL_DONE $(date)
