#!/bin/bash
#SBATCH --job-name=topic_model
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/topic_model_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/topic_model_%j.err
#SBATCH --time=12:00:00
#SBATCH --mem=200G
#SBATCH --cpus-per-task=8
#SBATCH --constraint=a100
#SBATCH --gpus=1
#SBATCH --partition=standard
#SBATCH --account=jfe4_cr_default
set -euo pipefail
COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
: ${CORPUS:=$COLLAB/data/corpus.parquet}
: ${SAMPLE_SIZE:=500000}
: ${OUTPUT_DIR:=$COLLAB/data/topic_model}
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false
export HF_HOME=/storage/home/jfe4/.cache/huggingface
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
echo "topic_model start $(hostname) $(date)"
echo "CORPUS=$CORPUS SAMPLE_SIZE=$SAMPLE_SIZE OUTPUT_DIR=$OUTPUT_DIR"
python -c "import torch; print('CUDA available:', torch.cuda.is_available(), 'device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
python $COLLAB/tenet_media_repo/code/06_topic_model.py --corpus $CORPUS --sample-size $SAMPLE_SIZE --output-dir $OUTPUT_DIR
echo "topic_model done $(date)"
