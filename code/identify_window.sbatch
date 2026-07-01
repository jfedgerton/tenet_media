#!/bin/bash
#SBATCH --job-name=identify_w
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/identify_%A.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/identify_%A.err
#SBATCH --time=2:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=2
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
CODE=$COLLAB/tenet_media_repo/code
: ${WINDOW:=1}
case "$WINDOW" in 1) WD=one_sentence;; 3) WD=three_sentence;; 5) WD=five_sentence;; *) exit 1;; esac
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
python $CODE/07w_identify_topics.py --window-dir $COLLAB/data/windows/$WD
echo "IDENTIFY DONE window=$WINDOW $(date)"
