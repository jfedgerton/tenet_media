#!/bin/bash
# Orchestrate the 1/3/5-sentence document pipeline: for each window, submit
#   build docs (array) -> merge -> BERTopic (08_topic_model.sbatch), chained.
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
CODE=$COLLAB/tenet_media_repo/code
TOPIC=$CODE/06_topic_model.sbatch
ACC=jfe4_cr_default
mkdir -p $COLLAB/logs
NFILES=$(find $COLLAB/transcript_key -name "*.txt" | wc -l)
LAST=$(( (NFILES + 4999) / 5000 - 1 ))
echo "NFILES=$NFILES  array=0-$LAST"
for W in 1 3 5; do
  case $W in 1) WD=one_sentence;; 3) WD=three_sentence;; 5) WD=five_sentence;; esac
  OUT=$COLLAB/data/windows/$WD
  mkdir -p $OUT/corpus_shards
  JB=$(WINDOW=$W sbatch --parsable --account=$ACC --array=0-$LAST $CODE/05w_build_docs.sbatch)
  JM=$(WINDOW=$W sbatch --parsable --account=$ACC --dependency=afterok:$JB $CODE/merge_window.sbatch)
  JT=$(CORPUS=$OUT/corpus.parquet OUTPUT_DIR=$OUT sbatch --parsable --dependency=afterok:$JM $TOPIC)
  echo "W=$W  build=$JB  merge=$JM  topic=$JT"
done
echo ALL_SUBMITTED
