#!/bin/bash
#SBATCH --job-name=freshtest
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/freshtest_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/freshtest_%j.err
#SBATCH --time=00:40:00
#SBATCH --mem=64G
#SBATCH --cpus-per-task=4
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
python $COLLAB/code/12a_validation_freshtest.py
echo ALLDONE
