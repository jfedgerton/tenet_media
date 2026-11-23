#!/bin/bash
#SBATCH --job-name=fig29
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/fig29_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/fig29_%j.out
#SBATCH --time=00:25:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=4
#SBATCH --account=open
#SBATCH --partition=basic
set -uo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
cd $COLLAB/tenet_media_repo/code
echo START $(date) on $(hostname)
module load r/4.2.1
( time Rscript 29_figures.R ) 2>&1; echo 29_EXIT=$?
echo DONE $(date)
