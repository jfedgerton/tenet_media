#!/bin/bash
#SBATCH --job-name=whisper_missing
#SBATCH --account=open
#SBATCH --partition=standard
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --array=0-47
#SBATCH --output=/storage/home/%u/work/podcast/logs/whisper_missing_%A_%a.out
#SBATCH --error=/storage/home/%u/work/podcast/logs/whisper_missing_%A_%a.err

set -euo pipefail

mkdir -p /storage/home/${USER}/work/podcast/logs

module purge
module load python/3.11.2
module load ffmpeg

echo "Host: $(hostname)"
echo "GPU:"
nvidia-smi -L
python -V
which python

cd /storage/home/${USER}/work/podcast/programs
source venv/bin/activate

# Slurm array index -> one episode task
OFFSET=${OFFSET:-0}
python transcribe_missing.py --run-one $((SLURM_ARRAY_TASK_ID + OFFSET))
