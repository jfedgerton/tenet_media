#!/bin/bash
#SBATCH --job-name=h4
#SBATCH --output=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/h4_%j.out
#SBATCH --error=/storage/group/LiberalArts/default/jfe4_collab/podcast/logs/h4_%j.err
#SBATCH --time=24:00:00
#SBATCH --mem=96G
#SBATCH --cpus-per-task=16
#SBATCH --account=jfe4_cr_default
#SBATCH --partition=standard
set -uo pipefail
export COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
cd $COLLAB/code
echo START $(date)
module load python/3.11.2
source $COLLAB/venv_analysis/bin/activate
python3 $COLLAB/code/22_agenda_divergence_panel.py
echo PANEL_EXIT=$?
module load r
Rscript $COLLAB/code/23_h4_divergence_grid.R
echo GRID_EXIT=$?
echo DONE_H4 $(date)
