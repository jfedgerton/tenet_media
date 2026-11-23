#!/bin/bash
#SBATCH --job-name=s3ru2
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/s3ru2_%A.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/s3ru2_%A.err
#SBATCH --time=1:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=4
#SBATCH --account=open
#SBATCH --partition=basic
set -euo pipefail
C=/storage/group/LiberalArts/default/jfe4_collab/podcast
module load python/3.11.2
source $C/venv_analysis/bin/activate
export PYTHONUNBUFFERED=1
python $C/tenet_media_repo/code/sample_3sent_ru_v2.py
echo DONE_S3RU2
