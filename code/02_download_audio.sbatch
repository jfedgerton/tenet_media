#!/bin/bash
#SBATCH --job-name=podcast_download
#SBATCH --output=/scratch/jfe4/podcast/logs/download_%j.out
#SBATCH --error=/scratch/jfe4/podcast/logs/download_%j.err
#SBATCH --time=24:00:00
#SBATCH --mem=4G
#SBATCH --cpus-per-task=1
#SBATCH --partition=open
#SBATCH --account=jfe4_cr_default

# ------------------------------------------------
# Download audio for all podcasts in json_data/
# Reruns automatically until 100% or max attempts
# ------------------------------------------------

PROJECT_DIR=/scratch/jfe4/podcast
CODE_DIR=${PROJECT_DIR}/code
LOG_DIR=${PROJECT_DIR}/logs

mkdir -p ${LOG_DIR}

module purge
module load anaconda3

MAX_ATTEMPTS=5
attempt=1

while [ $attempt -le $MAX_ATTEMPTS ]; do
    echo "=========================================="
    echo "DOWNLOAD ATTEMPT ${attempt} of ${MAX_ATTEMPTS}"
    echo "$(date)"
    echo "=========================================="

    python ${CODE_DIR}/02_download_audio.py

    if [ $? -eq 0 ]; then
        echo ""
        echo "ALL DOWNLOADS COMPLETE — exiting."
        exit 0
    fi

    echo ""
    echo "Some downloads failed. Waiting 60s before retry..."
    sleep 60
    attempt=$((attempt + 1))
done

echo ""
echo "WARNING: Still incomplete after ${MAX_ATTEMPTS} attempts."
echo "Check ${PROJECT_DIR}/failed_downloads.csv for remaining files."
exit 1
