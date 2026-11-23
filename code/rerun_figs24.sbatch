#!/bin/bash
#SBATCH --job-name=figs24
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/figs24_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/figs24_%j.out
#SBATCH --time=02:00:00
#SBATCH --mem=96G
#SBATCH --cpus-per-task=8
#SBATCH --account=open
#SBATCH --partition=basic
set -uo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
cd $COLLAB/tenet_media_repo/code
echo START $(date) on $(hostname)
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
export HF_HOME=/storage/home/jfe4/.cache/huggingface
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
echo '### 24_h3_topic_dist'; python3 24_h3_topic_dist.py; echo 24DIST_EXIT=$?
deactivate || true
module load r/4.2.1
echo '### 24_h3_topic_grid'; Rscript 24_h3_topic_grid.R; echo 24GRID_EXIT=$?
echo '### 29_figures'; Rscript 29_figures.R; echo 29_EXIT=$?
echo DONE $(date)
