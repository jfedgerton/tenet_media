#!/bin/bash
#SBATCH --job-name=whisper_newctrl
#SBATCH --account=jfe4_cr_default
#SBATCH --partition=standard
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --array=0-2961%50
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/whisper_newctrl_%A_%a.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/whisper_newctrl_%A_%a.err
# Transcribe ONE episode per array task from file_key.csv using Whisper small.
# venv_whisper = torch 2.4.1+cu118 (P100/V100/A100), openai-whisper 20250625.
# Model + ffmpeg resolved from group storage so home dir stays clear.
set -euo pipefail
C=/storage/group/LiberalArts/default/jfe4_collab/podcast
export XDG_CACHE_HOME=$C/.cache          # whisper.load_model('small') -> $C/.cache/whisper
export PATH=$C/venv_whisper/bin:$PATH     # use the imageio-ffmpeg static binary symlink
cd $C
source $C/venv_whisper/bin/activate
echo "Host: $(hostname)"; nvidia-smi -L
python $C/code/04_transcribe.py --csv $C/file_key.csv --run-one ${SLURM_ARRAY_TASK_ID} --model small
