#!/bin/bash
#SBATCH --job-name=build_corpus
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/build_corpus_%A_%a.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/build_corpus_%A_%a.err
#SBATCH --time=4:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=2
#SBATCH --account=open
#SBATCH --partition=basic
#SBATCH --requeue
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
: ${FILES_PER_SHARD:=5000}
START=$((SLURM_ARRAY_TASK_ID * FILES_PER_SHARD))
END=$((START + FILES_PER_SHARD))
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
export PYTHONUNBUFFERED=1
export NLTK_DATA=/storage/home/jfe4/nltk_data
SHARD=$(printf 'corpus_part_%04d.parquet' $SLURM_ARRAY_TASK_ID)
echo "START=$START END=$END SHARD=$SHARD on $(hostname) $(date)"
python $COLLAB/code/06_build_corpus_shard.py --transcript_dir $COLLAB/transcript_key --output $COLLAB/data/corpus_shards/$SHARD --start $START --end $END
echo "DONE $(date)"
