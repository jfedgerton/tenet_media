#!/bin/bash
#SBATCH --job-name=build_docs_w
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/build_docs_%A_%a.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/build_docs_%A_%a.err
#SBATCH --time=4:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=2
#SBATCH --account=open
#SBATCH --partition=basic
#SBATCH --requeue
# Build W-sentence DOCUMENTS for ONE window, sharded over the transcript corpus.
# WINDOW={1,3,5} via env (default 1). Documents are within-episode, non-overlapping,
# final chunk < W. Output: data/windows/{one,three,five}_sentence/corpus_shards/
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
CODE=$COLLAB/tenet_media_repo/code
: ${WINDOW:=1}
: ${FILES_PER_SHARD:=5000}
case "$WINDOW" in 1) WDIR=one_sentence ;; 3) WDIR=three_sentence ;; 5) WDIR=five_sentence ;; *) echo bad WINDOW; exit 1 ;; esac
OUTBASE=$COLLAB/data/windows/$WDIR
START=$((SLURM_ARRAY_TASK_ID * FILES_PER_SHARD))
END=$((START + FILES_PER_SHARD))
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
export PYTHONUNBUFFERED=1
export NLTK_DATA=/storage/home/jfe4/nltk_data
SHARD=$(printf corpus_part_%04d.parquet $SLURM_ARRAY_TASK_ID)
mkdir -p $OUTBASE/corpus_shards
echo "WINDOW=$WINDOW START=$START END=$END SHARD=$SHARD $(date)"
python $CODE/05w_build_docs.py --window $WINDOW --transcript_dir $COLLAB/transcript_key --output $OUTBASE/corpus_shards/$SHARD --start $START --end $END
echo "DONE window=$WINDOW $(date)"
