#!/bin/bash
#SBATCH --job-name=bertgrid
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/bertgrid_%A_%a.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/bertgrid_%A_%a.err
#SBATCH --time=05:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=8
#SBATCH --account=open
#SBATCH --partition=basic
#SBATCH --array=0-17
set -euo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
export HF_HOME=/storage/home/jfe4/.cache/huggingface
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=8
echo "bertgrid task $SLURM_ARRAY_TASK_ID on $(hostname) $(date)"
python $COLLAB/code/bert_train_infer.py
echo "task $SLURM_ARRAY_TASK_ID done $(date)"
