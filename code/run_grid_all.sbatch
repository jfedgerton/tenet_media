#!/bin/bash
#SBATCH --job-name=gridall
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/gridall_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/gridall_%j.err
#SBATCH --time=24:00:00
#SBATCH --mem=96G
#SBATCH --cpus-per-task=16
#SBATCH --account=jfe4_cr_default
#SBATCH --partition=standard
set -uo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
cd $COLLAB/tenet_media_repo
echo START $(date) on $(hostname)
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
python code/19_loso_panel.py;    echo "EXIT 19_loso_panel = $?"
python code/24_h3_topic_dist.py; echo "EXIT 24_h3_topic_dist = $?"
deactivate 2>/dev/null || true
module purge
module load r/4.2.1
for s in 16_grid_h1h2 17_relabel_sweep 18_label_noise 20_loso_models 21_h1_inference 22_h1_altspecs 23_h1_appendix 24_h3_topic_grid 25_h4_divergence_grid 26_min_mention_sweep; do
  echo "### $s START $(date) ###"
  Rscript code/$s.R; echo "EXIT $s = $?"
done
echo DONE_GRIDALL $(date)
