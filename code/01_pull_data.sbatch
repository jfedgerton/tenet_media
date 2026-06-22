#!/bin/bash
#SBATCH --job-name=pull_rss
#SBATCH --account=jfe4_cr_default
#SBATCH --partition=sla-prio
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=/scratch/jfe4/podcast/logs/pull_rss_%j.out
#SBATCH --error=/scratch/jfe4/podcast/logs/pull_rss_%j.err

# ── Create log directory if needed ──
mkdir -p /scratch/jfe4/podcast/logs

# ── Load Python ──
module purge
module load anaconda3

# ── Activate conda env (edit name if different) ──
# conda activate podcast_env

# ── Run the RSS puller for all 290 feeds ──
cd /scratch/jfe4/podcast/code
python 01_pull_data.py

echo "Done. Exit code: $?"
