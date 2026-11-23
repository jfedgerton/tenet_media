#!/bin/bash
# Full 1/3/5-sentence pipeline: build docs (array) -> merge -> BERTopic (06) -> identify Russia (07w), chained.
# Rebuilds corpora from transcript_key (now includes the 9 new control shows).
set -euo pipefail
C=/storage/group/LiberalArts/default/jfe4_collab/podcast
CODE=$C/tenet_media_repo/code
ACC=jfe4_cr_default
NFILES=$(find $C/transcript_key -name "*.txt" | wc -l)
LAST=$(( (NFILES + 4999)/5000 - 1 ))
echo "NFILES=$NFILES  array=0-$LAST"
for W in 1 3 5; do
  case $W in 1) WD=one_sentence;; 3) WD=three_sentence;; 5) WD=five_sentence;; esac
  OUT=$C/data/windows/$WD
  rm -rf $OUT/corpus_shards; mkdir -p $OUT/corpus_shards
  JB=$(WINDOW=$W sbatch --parsable --account=$ACC --array=0-$LAST $CODE/slurm/05_build_sentence_docs.sbatch)
  JM=$(WINDOW=$W sbatch --parsable --account=$ACC --dependency=afterok:$JB $CODE/slurm/06_merge_windows.sbatch)
  JT=$(CORPUS=$OUT/corpus.parquet OUTPUT_DIR=$OUT sbatch --parsable --dependency=afterok:$JM $CODE/slurm/07_topic_model.sbatch)
  JI=$(WINDOW=$W sbatch --parsable --account=$ACC --dependency=afterok:$JT $CODE/slurm/08_identify_topics.sbatch)
  echo "W=$W  build=$JB  merge=$JM  topic=$JT  identify=$JI"
done
echo ALL_SUBMITTED
