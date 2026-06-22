#!/bin/bash
#SBATCH --job-name=stance_samp
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/stancesamp_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/stancesamp_%j.err
#SBATCH --time=00:20:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=2
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
python $COLLAB/code/12d_validation_stance_sample.py
echo ALLDONE
