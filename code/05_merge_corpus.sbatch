#!/bin/bash
#SBATCH --job-name=merge_corpus
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/merge_corpus_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/merge_corpus_%j.err
#SBATCH --time=2:00:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=1
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
export PYTHONUNBUFFERED=1
echo "merge start $(hostname) $(date)"
python $COLLAB/code/07_merge_corpus.py --shards_dir $COLLAB/data/corpus_shards --output $COLLAB/data/corpus.parquet
echo "merge done $(date)"
