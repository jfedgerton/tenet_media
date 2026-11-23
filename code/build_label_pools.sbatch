#!/bin/bash
#SBATCH --job-name=label_pools
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/labelpools_%A.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/labelpools_%A.err
#SBATCH --time=2:00:00
#SBATCH --mem=48G
#SBATCH --cpus-per-task=4
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
C=/storage/group/LiberalArts/default/jfe4_collab/podcast
W=${WD:-one_sentence}
module load python/3.11.2
source $C/venv_analysis/bin/activate
export PYTHONUNBUFFERED=1
python $C/tenet_media_repo/code/build_label_pools.py --window-dir $C/data/windows/$W --out-dir $C/data/label_sheets/$W
echo DONE_LABEL_POOLS
