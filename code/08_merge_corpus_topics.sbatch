#!/bin/bash
#SBATCH --job-name=merge_ct
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/merge_ct_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/merge_ct_%j.err
#SBATCH --time=2:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=2
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
export PYTHONUNBUFFERED=1
python $COLLAB/code/10_merge_corpus_topics.py
