#!/bin/bash
#SBATCH --job-name=build_russia
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/build_russia_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/build_russia_%j.err
#SBATCH --time=2:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=2
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
export PYTHONUNBUFFERED=1
python $COLLAB/code/09_build_russia_class.py
