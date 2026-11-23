#!/bin/bash
#SBATCH --job-name=grid16
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/grid16_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/grid16_%j.out
#SBATCH --time=3-00:00:00
#SBATCH --mem=180G
#SBATCH --cpus-per-task=48
#SBATCH --account=jfe4_cr_default
#SBATCH --partition=standard
set -uo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
cd $COLLAB/tenet_media_repo/code
echo START $(date) on $(hostname) cpus=$SLURM_CPUS_PER_TASK
module load r/4.2.1
( time Rscript 16_grid_h1h2.R ) 2>&1; echo GRID16_EXIT=$?
echo DONE $(date)
