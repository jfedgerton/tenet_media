# config/

## Paths
- `COLLAB` is the data root. Default:
  `/storage/group/LiberalArts/default/jfe4_collab/podcast`.
  Steps 01–04 and 07 read it with `os.environ.get("COLLAB", <default>)`. Set it to
  replicate somewhere else: `export COLLAB=/path/to/data`.
- The repo is found from each script's own location (`REPO_ROOT`). The Roar working copy
  is `$COLLAB/tenet_media_repo`, and the slurm files call scripts from there.
- Many later scripts still hard-code `/storage/...` paths or set `CO`/`SC` variables at
  the top. Moving those to `COLLAB` is pending.

## Environments
- `requirements.txt` holds exact pinned versions (formerly at the repo root). Which Roar venv it was frozen from is not recorded.
- `requirements_min.txt` is the hand-written list of minimum versions by step (formerly `code/requirements.txt`).
- The analysis venv on Roar is `$COLLAB/venv_analysis`.
- Transcription uses `$COLLAB/venv_whisper` (torch 2.4.1+cu118, openai-whisper 20250625).
- The R layer uses `fixest`, `tidyverse` and `quadprog`, loaded with `module load r`. R on Roar lacks `arrow`, so step 25 (Python) builds the panel CSVs that R reads.
- No R lockfile (renv) and no verified freeze of each Roar venv yet. That is pending for replication.
