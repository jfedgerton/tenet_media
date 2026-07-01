#!/bin/bash
#SBATCH --job-name=merge_w
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/merge_%A.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/merge_%A.err
#SBATCH --time=2:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=2
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
CODE=$COLLAB/tenet_media_repo/code
: ${WINDOW:=1}
case "$WINDOW" in 1) WDIR=one_sentence ;; 3) WDIR=three_sentence ;; 5) WDIR=five_sentence ;; *) exit 1 ;; esac
OUT=$COLLAB/data/windows/$WDIR
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
python $CODE/05_merge_corpus.py --shards_dir $OUT/corpus_shards --output $OUT/corpus.parquet
echo "MERGED window=$WINDOW $(date)"
