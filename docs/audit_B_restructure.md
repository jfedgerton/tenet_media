# GPT audit B: repository restructure for replication (branch `restructure-replication`, commit f150b09)

Everything you need is in this file. Diffs and new files are pasted below.

## Context
This is a research repo for a podcast stance-classification and causal-inference pipeline (Python + R, with SLURM jobs on Penn State's Roar cluster). The commit reorganizes a flat `code/` folder for publication replication. The intended changes are listed below.
1. Every active script moves into a stage folder (`code/1_collect` … `code/7_outputs`) and is renumbered so there is exactly one script per number, 01–49, in run order. SLURM files move to `code/slurm/` and are renamed for the step they run. All moves use `git mv`.
2. Superseded, exploratory and one-off code moves to `archive/` (documented in `archive/README.md`; every old → new name is in `archive/RENAMES.md`, pasted below).
3. `06_merge_windows.py` is restored. It was deleted in an earlier commit, but the corpus SLURM chain still calls it.
4. Scripts 01–04 and 07 used to set `PROJECT_ROOT = Path(__file__).resolve().parent.parent`, which pointed at the repo rather than the data. They now read the data root from env var `COLLAB` (with the Roar path as default) and read input CSVs from `REPO_ROOT/inputs`.
5. SLURM files are repointed to the new script paths. The repo on Roar lives at `$COLLAB/tenet_media_repo`.
6. Steps 17–24 and 34 are placeholders that raise an error. Steps 25–49 were run on older labels and will be re-run later.
7. A new `run_all.sh` prints commands by default (dry run) and executes only with `--run`. It never re-runs steps 10–16, because those wrote files that human coders are working in.
8. Script headers that named the old filename were updated. Apart from that, **no analysis logic was supposed to change.**

Checks already done: numbering 01–49 has no gaps, every `.py` compiles, every path named in the README, `run_all.sh` and the SLURM files resolves, and a grep for old names found none. The R scripts were NOT parse-checked (no R in the sandbox).

## Please check
- **Unintended logic changes.** Does any hunk in the diff below change behavior beyond paths, filenames and comments? Flag every one.
- **Path resolution.** With `COLLAB` unset on Roar, do 01–04 and 07 read and write exactly the same locations as before? With `COLLAB` set elsewhere, does anything still silently write to the Roar path? Is `parents[2]` right for `code/<stage>/<script>.py`?
- **SLURM.** Do the repointed SLURM files and `run_corpus_05_to_08.sh` call the right script, with arguments the script accepts? Is the restored `06_merge_windows.py` compatible with how `06_merge_windows.sbatch` calls it and with what `07_topic_model.py` expects to read?
- **Cross-script dependencies.** Does any active script read an output by a filename that only an archived script produces? (For example, the README says `31_grid_summary.R` reads the output of `30_grid_h1h2.R`, which is why `16_grid_h1h2_v2.R` was archived.)
- **Archive decisions.** From the RENAMES table, does anything in `archive/` look like it is still needed by the active pipeline?
- **`run_all.sh`.** Is it safe? Could anything run or submit jobs without `--run`? Are stage boundaries and order right?
- **`.gitignore`.** It is a deny-by-default whitelist. Is anything needed for replication still excluded?

Report concrete bugs with file and line references first. List lower-priority suggestions separately. Do not propose new features or methods beyond what is needed to fix a bug.

## Rename table

Every script moved from the old flat layout. History is preserved (git mv).

| old | new |
|---|---|
| `code/01_pull_data.py` | `code/1_collect/01_pull_data.py` |
| `code/01_pull_data.sbatch` | `code/slurm/01_pull_data.sbatch` |
| `code/02_download_audio.py` | `code/1_collect/02_download_audio.py` |
| `code/02_download_audio.sbatch` | `code/slurm/02_download_audio.sbatch` |
| `code/02_transcribe_missing.sbatch` | `archive/superseded/02_transcribe_missing.sbatch` |
| `code/03_create_key.py` | `code/1_collect/03_create_key.py` |
| `code/04_transcribe.py` | `code/1_collect/04_transcribe.py` |
| `code/04_transcribe.sbatch` | `code/slurm/04_transcribe.sbatch` |
| `code/05w_build_docs.py` | `code/2_corpus/05_build_sentence_docs.py` |
| `code/05w_build_docs.sbatch` | `code/slurm/05_build_sentence_docs.sbatch` |
| `code/06_topic_model.py` | `code/2_corpus/07_topic_model.py` |
| `code/06_topic_model.sbatch` | `code/slurm/07_topic_model.sbatch` |
| `code/07w_identify_topics.py` | `code/2_corpus/08_identify_topics.py` |
| `code/08w_draw_union_sample.py` | `code/3_human_coding/10_draw_union_sample.py` |
| `code/09_sample_validation.py` | `archive/pre_two_stage/09_sample_validation.py` |
| `code/09_sample_validation.sbatch` | `archive/pre_two_stage/09_sample_validation.sbatch` |
| `code/09w_draw_nonunion_sample.py` | `code/3_human_coding/11_draw_nonunion_sample.py` |
| `code/10a_validation_freshtest.py` | `archive/pre_two_stage/10a_validation_freshtest.py` |
| `code/10a_validation_freshtest.sbatch` | `archive/pre_two_stage/10a_validation_freshtest.sbatch` |
| `code/10b_validation_freshtest2.py` | `archive/pre_two_stage/10b_validation_freshtest2.py` |
| `code/10b_validation_freshtest2.sbatch` | `archive/pre_two_stage/10b_validation_freshtest2.sbatch` |
| `code/10c_validation_freshtest3.py` | `archive/pre_two_stage/10c_validation_freshtest3.py` |
| `code/10c_validation_freshtest3.sbatch` | `archive/pre_two_stage/10c_validation_freshtest3.sbatch` |
| `code/10d_validation_stance_sample.py` | `archive/pre_two_stage/10d_validation_stance_sample.py` |
| `code/10d_validation_stance_sample.sbatch` | `archive/pre_two_stage/10d_validation_stance_sample.sbatch` |
| `code/10e_validation_vset.py` | `archive/pre_two_stage/10e_validation_vset.py` |
| `code/10e_validation_vset.sbatch` | `archive/pre_two_stage/10e_validation_vset.sbatch` |
| `code/10w_assign_coders.py` | `code/3_human_coding/13_assign_coders.py` |
| `code/11a_codebook_label.py` | `archive/pre_two_stage/11a_codebook_label.py` |
| `code/11a_codebook_label_run.py` | `archive/pre_two_stage/11a_codebook_label_run.py` |
| `code/11a_stance_codebook.md` | `archive/pre_two_stage/11a_stance_codebook.md` |
| `code/11b_bert_build_data.py` | `archive/pre_two_stage/11b_bert_build_data.py` |
| `code/11c_bert_grid.sbatch` | `archive/pre_two_stage/11c_bert_grid.sbatch` |
| `code/11c_bert_train_infer.py` | `archive/pre_two_stage/11c_bert_train_infer.py` |
| `code/11d_bert_aggregate.py` | `archive/pre_two_stage/11d_bert_aggregate.py` |
| `code/11e_merge_preds.py` | `archive/pre_two_stage/11e_merge_preds.py` |
| `code/11w_build_disney_pool.py` | `code/3_human_coding/12_build_disney_pool.py` |
| `code/12_build_panels.py` | `code/5_analysis/25_build_panels.py` |
| `code/12w_assign_placebo.py` | `code/3_human_coding/14_assign_placebo.py` |
| `code/13_main_h1h3.R` | `code/5_analysis/26_main_h1h3.R` |
| `code/13w_GPT_AUDIT_PROMPT.md` | `docs/audit_A_rebuild_reduced_design.md` |
| `code/13w_rebuild_reduced_design.py` | `code/3_human_coding/15_rebuild_reduced_design.py` |
| `code/13w_release.py` | `code/3_human_coding/16_release_reduced_design.py` |
| `code/13w_test_synthetic.py` | `tests/test_15_rebuild_reduced_design.py` |
| `code/14_h4_tfidf_clean.py` | `code/5_analysis/27_h4_tfidf_clean.py` |
| `code/14_h4_topic_model.py` | `code/5_analysis/28_h4_topic_model.py` |
| `code/15_main_h4.R` | `code/5_analysis/29_main_h4.R` |
| `code/16_grid_h1h2.R` | `code/6_robustness/30_grid_h1h2.R` |
| `code/16_grid_h1h2_v2.R` | `archive/superseded/16_grid_h1h2_v2.R` |
| `code/16_summarize_grid.py` | `archive/superseded/16_summarize_grid.py` |
| `code/17_grid_summary.R` | `code/6_robustness/31_grid_summary.R` |
| `code/17_relabel_sweep.R` | `code/6_robustness/32_relabel_sweep.R` |
| `code/18_label_noise.R` | `code/6_robustness/33_label_noise.R` |
| `code/18_power_analysis.R` | `code/6_robustness/35_power_analysis.R` |
| `code/19_loso_panel.py` | `code/6_robustness/36_loso_panel.py` |
| `code/20_loso_models.R` | `code/6_robustness/37_loso_models.R` |
| `code/21_h1_inference.R` | `code/6_robustness/38_h1_inference.R` |
| `code/22_h1_altspecs.R` | `code/6_robustness/39_h1_altspecs.R` |
| `code/23_h1_appendix.R` | `code/6_robustness/40_h1_appendix.R` |
| `code/24_h3_topic_dist.py` | `code/6_robustness/41_h3_topic_dist.py` |
| `code/24_h3_topic_grid.R` | `code/6_robustness/42_h3_topic_grid.R` |
| `code/25_h4_divergence_grid.R` | `code/6_robustness/43_h4_divergence_grid.R` |
| `code/25_run_h4.sbatch` | `archive/superseded/25_run_h4.sbatch` |
| `code/26_min_mention_sweep.R` | `code/6_robustness/44_min_mention_sweep.R` |
| `code/27_descriptives.R` | `code/7_outputs/45_descriptives.R` |
| `code/28_label_examples.py` | `code/7_outputs/46_label_examples.py` |
| `code/29_figures.R` | `code/7_outputs/47_figures.R` |
| `code/30_make_tables.R` | `code/7_outputs/48_make_tables.R` |
| `code/30_manuscript_tables.R` | `code/7_outputs/49_manuscript_tables.R` |
| `code/31_ranked_prepost.R` | `archive/exploratory/31_ranked_prepost.R` |
| `code/CLAUDE_MEMORY.md` | `docs/CLAUDE_MEMORY.md` |
| `code/CLEANUP_REVIEW.md` | `docs/CLEANUP_REVIEW.md` |
| `code/archive/05_build_corpus_shard.py` | `archive/superseded/05_build_corpus_shard.py` |
| `code/archive/05_build_corpus_shard.sbatch` | `archive/superseded/05_build_corpus_shard.sbatch` |
| `code/archive/07_identify_russia_topics.py` | `archive/superseded/07_identify_russia_topics.py` |
| `code/archive/07_identify_russia_topics.sbatch` | `archive/superseded/07_identify_russia_topics.sbatch` |
| `code/archive/icr200.py` | `archive/coding_history/icr200.py` |
| `code/archive/icr_round3.py` | `archive/coding_history/icr_round3.py` |
| `code/archive/icr_supp.py` | `archive/coding_history/icr_supp.py` |
| `code/build_label_pools.py` | `archive/superseded/build_label_pools.py` |
| `code/build_label_pools.sbatch` | `archive/superseded/build_label_pools.sbatch` |
| `code/build_label_pools_v2.py` | `archive/superseded/build_label_pools_v2.py` |
| `code/build_label_pools_v2.sbatch` | `archive/superseded/build_label_pools_v2.sbatch` |
| `code/build_label_pools_v3.py` | `code/2_corpus/09_build_label_pools.py` |
| `code/build_label_pools_v3.sbatch` | `code/slurm/09_build_label_pools.sbatch` |
| `code/build_workbooks.py` | `archive/superseded/build_workbooks.py` |
| `code/code_setup.txt` | `docs/code_setup.txt` |
| `code/fig29.sbatch` | `archive/slurm_runs/fig29.sbatch` |
| `code/grid16_3day.sbatch` | `archive/slurm_runs/grid16_3day.sbatch` |
| `code/identify_window.sbatch` | `code/slurm/08_identify_topics.sbatch` |
| `code/merge_window.sbatch` | `code/slurm/06_merge_windows.sbatch` |
| `code/new_feeds_15.csv` | `inputs/new_feeds_15.csv` |
| `code/podcast_feeds.csv` | `inputs/podcast_feeds.csv` |
| `code/podcast_rss_feeds_reference.xlsx` | `inputs/podcast_rss_feeds_reference.xlsx` |
| `code/requirements.txt` | `config/requirements_min.txt` |
| `code/rerun_figs24.sbatch` | `archive/slurm_runs/rerun_figs24.sbatch` |
| `code/run_final_all.sbatch` | `archive/slurm_runs/run_final_all.sbatch` |
| `code/run_grid_all.sbatch` | `archive/slurm_runs/run_grid_all.sbatch` |
| `code/run_rerun_benny.sbatch` | `archive/slurm_runs/run_rerun_benny.sbatch` |
| `code/run_windows_full.sh` | `code/slurm/run_corpus_05_to_08.sh` |
| `code/sample_3sent_ru.py` | `archive/exploratory/sample_3sent_ru.py` |
| `code/sample_3sent_ru.sbatch` | `archive/exploratory/sample_3sent_ru.sbatch` |
| `code/sample_3sent_ru_v2.py` | `archive/exploratory/sample_3sent_ru_v2.py` |
| `code/sample_3sent_ru_v2.sbatch` | `archive/exploratory/sample_3sent_ru_v2.sbatch` |
| `requirements.txt` | `config/requirements.txt` |
| `code/05_merge_corpus.py` (deleted in 989f0a9, restored) | `code/2_corpus/06_merge_windows.py` |


## Content diff (renamed-and-edited files only; pure renames omitted)
```diff
diff --git a/.gitignore b/.gitignore
index 433bdd9..c982a84 100644
--- a/.gitignore
+++ b/.gitignore
@@ -15,6 +15,12 @@
 !/tex/
 !/README.md
 !/requirements.txt
+!/archive/
+!/config/
+!/docs/
+!/inputs/
+!/tests/
+!/run_all.sh
 !/.gitignore
 !/.gitattributes
 
@@ -32,6 +38,8 @@
 
 # 4) inside code/: drop caches, archived/legacy code, and transfer leftovers
 code/__pycache__/
+**/__pycache__/
+*.bak*
 code/archive/
 code/*.b64
 code/*.zip
diff --git a/code/01_pull_data.py b/code/1_collect/01_pull_data.py
similarity index 94%
rename from code/01_pull_data.py
rename to code/1_collect/01_pull_data.py
index 5b04d26..ed625e2 100644
--- a/code/01_pull_data.py
+++ b/code/1_collect/01_pull_data.py
@@ -1,6 +1,6 @@
 #!/usr/bin/env python3
 """
-1_pull_data.py — Fetch RSS feeds and extract episode metadata
+01_pull_data.py — Fetch RSS feeds and extract episode metadata
 =============================================================
 
 For each podcast in podcast_feeds.csv, this script:
@@ -25,16 +25,18 @@ import json
 import logging
 import sys
 import time
+import os
 from pathlib import Path
 
 import requests
 from bs4 import BeautifulSoup
 
 # ── Project paths ────────────────────────────────────────────────────────────
-# PROJECT_ROOT is the *pipeline* directory (parent of code/).
-# All data directories hang off PROJECT_ROOT.
+# PROJECT_ROOT is the data root on Roar ($COLLAB; see config/README.md).
+# All data directories hang off PROJECT_ROOT. Inputs come from REPO_ROOT/inputs.
 
-PROJECT_ROOT = Path(__file__).resolve().parent.parent
+PROJECT_ROOT = Path(os.environ.get("COLLAB", "/storage/group/LiberalArts/default/jfe4_collab/podcast"))  # data root
+REPO_ROOT = Path(__file__).resolve().parents[2]
 
 # ── Configuration ────────────────────────────────────────────────────────────
 
@@ -48,7 +50,7 @@ REQUEST_HEADERS = {
 }
 
 # Where to read / write data (all relative to PROJECT_ROOT).
-DEFAULT_FEEDS_CSV = PROJECT_ROOT / "code" / "podcast_feeds.csv"
+DEFAULT_FEEDS_CSV = REPO_ROOT / "inputs" / "podcast_feeds.csv"
 JSON_OUTPUT_DIR   = PROJECT_ROOT / "json_data"
 PODCHASER_DIR     = PROJECT_ROOT / "data" / "episodes"
 
@@ -276,7 +278,7 @@ def main():
         "--feeds-csv",
         type=Path,
         default=DEFAULT_FEEDS_CSV,
-        help="Path to the CSV of podcast feeds (default: code/podcast_feeds.csv)",
+        help="Path to the CSV of podcast feeds (default: inputs/podcast_feeds.csv)",
     )
     args = parser.parse_args()
 
diff --git a/code/02_download_audio.py b/code/1_collect/02_download_audio.py
similarity index 97%
rename from code/02_download_audio.py
rename to code/1_collect/02_download_audio.py
index 8dc2937..a3a1ca8 100644
--- a/code/02_download_audio.py
+++ b/code/1_collect/02_download_audio.py
@@ -1,6 +1,6 @@
 #!/usr/bin/env python3
 """
-2_download_audio.py — Download MP3 audio for every episode
+02_download_audio.py — Download MP3 audio for every episode
 ==========================================================
 
 Reads all JSON files produced by 1_pull_data.py (in json_data/) and
@@ -32,13 +32,15 @@ import time
 from concurrent.futures import ThreadPoolExecutor, as_completed
 from datetime import datetime
 from email.utils import parsedate_to_datetime
+import os
 from pathlib import Path
 
 import requests
 
 # ── Project paths ────────────────────────────────────────────────────────────
 
-PROJECT_ROOT = Path(__file__).resolve().parent.parent
+PROJECT_ROOT = Path(os.environ.get("COLLAB", "/storage/group/LiberalArts/default/jfe4_collab/podcast"))  # data root
+REPO_ROOT = Path(__file__).resolve().parents[2]
 
 # ── Configuration ────────────────────────────────────────────────────────────
 
diff --git a/code/03_create_key.py b/code/1_collect/03_create_key.py
similarity index 96%
rename from code/03_create_key.py
rename to code/1_collect/03_create_key.py
index 00f95ff..8c4ae81 100644
--- a/code/03_create_key.py
+++ b/code/1_collect/03_create_key.py
@@ -1,6 +1,6 @@
 #!/usr/bin/env python3
 """
-3_create_key.py — Build a file key and identify missing transcripts
+03_create_key.py — Build a file key and identify missing transcripts
 ====================================================================
 
 Reads all JSON files produced by 1_pull_data.py and creates a master
@@ -26,11 +26,13 @@ import json
 import logging
 from datetime import datetime
 from email.utils import parsedate_to_datetime
+import os
 from pathlib import Path
 
 # ── Project paths ────────────────────────────────────────────────────────────
 
-PROJECT_ROOT = Path(__file__).resolve().parent.parent
+PROJECT_ROOT = Path(os.environ.get("COLLAB", "/storage/group/LiberalArts/default/jfe4_collab/podcast"))  # data root
+REPO_ROOT = Path(__file__).resolve().parents[2]
 
 # ── Configuration ────────────────────────────────────────────────────────────
 
diff --git a/code/04_transcribe.py b/code/1_collect/04_transcribe.py
similarity index 96%
rename from code/04_transcribe.py
rename to code/1_collect/04_transcribe.py
index d5de357..226c137 100644
--- a/code/04_transcribe.py
+++ b/code/1_collect/04_transcribe.py
@@ -1,6 +1,6 @@
 #!/usr/bin/env python3
 """
-4_transcribe.py — Transcribe podcast audio with Whisper
+04_transcribe.py — Transcribe podcast audio with Whisper
 ========================================================
 
 Reads a CSV (typically missing_files.csv from step 3) and transcribes
@@ -35,13 +35,15 @@ import argparse
 import csv
 import logging
 import sys
+import os
 from pathlib import Path
 
 import whisper
 
 # ── Project paths ────────────────────────────────────────────────────────────
 
-PROJECT_ROOT = Path(__file__).resolve().parent.parent
+PROJECT_ROOT = Path(os.environ.get("COLLAB", "/storage/group/LiberalArts/default/jfe4_collab/podcast"))  # data root
+REPO_ROOT = Path(__file__).resolve().parents[2]
 
 # ── Configuration ────────────────────────────────────────────────────────────
 
diff --git a/code/05w_build_docs.py b/code/2_corpus/05_build_sentence_docs.py
similarity index 94%
rename from code/05w_build_docs.py
rename to code/2_corpus/05_build_sentence_docs.py
index a9e8fef..736e96f 100644
--- a/code/05w_build_docs.py
+++ b/code/2_corpus/05_build_sentence_docs.py
@@ -1,5 +1,5 @@
 """
-05w_build_docs.py -- Windowed document builder (generalizes 05_build_corpus_shard.py).
+05_build_sentence_docs.py -- Windowed document builder (generalizes 05_build_corpus_shard.py).
 
 Splits each transcript into sentences with nltk, then groups every W consecutive
 sentences (non-overlapping) within an episode into ONE document. W=1 reproduces
@@ -7,13 +7,13 @@ the original sentence-level corpus exactly.
 
 Output schema is IDENTICAL to 05_build_corpus_shard.py
     (show, date, episode_number, filename, sentence_id, sentence)
-so that 06_topic_model.py, 07_identify_russia_topics_windowed.py, the stance
+so that 07_topic_model.py, 07_identify_russia_topics_windowed.py, the stance
 pipeline, and the panels all run UNCHANGED -- the "sentence" column simply holds
 a W-sentence document, and "sentence_id" is the document index within the episode.
 An extra column n_sent records how many sentences each document contains.
 
 Usage (sharded, memory-safe, like 05):
-    python 05w_build_docs.py --window 3 --transcript_dir $C/transcript_key \
+    python 05_build_sentence_docs.py --window 3 --transcript_dir $C/transcript_key \
         --output $C/data/corpus_shards_w3/corpus_part_0000.parquet --start 0 --end 1000
 """
 import argparse, logging, os, re
diff --git a/code/06_topic_model.py b/code/2_corpus/07_topic_model.py
similarity index 97%
rename from code/06_topic_model.py
rename to code/2_corpus/07_topic_model.py
index 8462b4f..71d7698 100644
--- a/code/06_topic_model.py
+++ b/code/2_corpus/07_topic_model.py
@@ -1,5 +1,5 @@
 """
-6_topic_model.py
+07_topic_model.py
 Fit a BERTopic model on the sentence corpus and assign topics to all sentences.
 
 Loads data/corpus.parquet, samples up to 500K sentences for fitting, then
@@ -9,6 +9,7 @@ the serialized model.
 
 import argparse
 import logging
+import os
 from pathlib import Path
 
 import numpy as np
@@ -18,7 +19,8 @@ from hdbscan import HDBSCAN
 from sklearn.feature_extraction.text import CountVectorizer
 from umap import UMAP
 
-PROJECT_ROOT = Path(__file__).resolve().parent.parent
+PROJECT_ROOT = Path(os.environ.get("COLLAB", "/storage/group/LiberalArts/default/jfe4_collab/podcast"))  # data root
+REPO_ROOT = Path(__file__).resolve().parents[2]
 
 SEED = 123
 TRANSFORM_BATCH = 200_000
diff --git a/code/07w_identify_topics.py b/code/2_corpus/08_identify_topics.py
similarity index 100%
rename from code/07w_identify_topics.py
rename to code/2_corpus/08_identify_topics.py
diff --git a/code/build_label_pools_v3.py b/code/2_corpus/09_build_label_pools.py
similarity index 100%
rename from code/build_label_pools_v3.py
rename to code/2_corpus/09_build_label_pools.py
diff --git a/code/08w_draw_union_sample.py b/code/3_human_coding/10_draw_union_sample.py
similarity index 100%
rename from code/08w_draw_union_sample.py
rename to code/3_human_coding/10_draw_union_sample.py
diff --git a/code/09w_draw_nonunion_sample.py b/code/3_human_coding/11_draw_nonunion_sample.py
similarity index 98%
rename from code/09w_draw_nonunion_sample.py
rename to code/3_human_coding/11_draw_nonunion_sample.py
index 97f8973..bd60f86 100644
--- a/code/09w_draw_nonunion_sample.py
+++ b/code/3_human_coding/11_draw_nonunion_sample.py
@@ -1,4 +1,4 @@
-"""09w_draw_nonunion_sample.py -- two-stage (gate+stance) design: draw non-union coding strata.
+"""11_draw_nonunion_sample.py -- two-stage (gate+stance) design: draw non-union coding strata.
 
 Outputs to data/label_sheets_fixed/one_sentence/:
   nonunion_random_5000.csv   2,500 pre / 2,500 post Oct 2023, random non-union
diff --git a/code/11w_build_disney_pool.py b/code/3_human_coding/12_build_disney_pool.py
similarity index 94%
rename from code/11w_build_disney_pool.py
rename to code/3_human_coding/12_build_disney_pool.py
index 47ed97f..6f2b2e3 100644
--- a/code/11w_build_disney_pool.py
+++ b/code/3_human_coding/12_build_disney_pool.py
@@ -1,5 +1,5 @@
-"""11w_build_disney_pool.py -- build the Disney placebo label pool (missing from the
-July build_label_pools_v3 run). Mirrors the big_tech regex path exactly: stream the
+"""12_build_disney_pool.py -- build the Disney placebo label pool (missing from the
+July 09_build_label_pools run, then named build_label_pools_v3). Mirrors the big_tech regex path exactly: stream the
 one_sentence corpus, collect regex matches with prev/next context, polarity-balance
 175 pos / 175 neg / 150 neu (fill remainder at random), N=500, seed 123.
 Writes label_sheets_fixed/one_sentence/label_disney.csv with the v3 schema.
diff --git a/code/10w_assign_coders.py b/code/3_human_coding/13_assign_coders.py
similarity index 96%
rename from code/10w_assign_coders.py
rename to code/3_human_coding/13_assign_coders.py
index ab6ff56..9c1b25e 100644
--- a/code/10w_assign_coders.py
+++ b/code/3_human_coding/13_assign_coders.py
@@ -1,4 +1,4 @@
-"""10w_assign_coders.py -- combine union (4,000) + nonunion random (5,000) + hard negatives
+"""13_assign_coders.py -- combine union (4,000) + nonunion random (5,000) + hard negatives
 (1,000), split into three pair-parts (A-B, B-C, A-C) balanced within stratum, so every
 sentence is coded by exactly two of three coders. Writes:
   assignments/assignment_master.csv   (uid -> part, pair)
diff --git a/code/12w_assign_placebo.py b/code/3_human_coding/14_assign_placebo.py
similarity index 96%
rename from code/12w_assign_placebo.py
rename to code/3_human_coding/14_assign_placebo.py
index a4f86a6..8a97523 100644
--- a/code/12w_assign_placebo.py
+++ b/code/3_human_coding/14_assign_placebo.py
@@ -1,4 +1,4 @@
-"""12w_assign_placebo.py -- split the four placebo label pools (big_tech, china,
+"""14_assign_placebo.py -- split the four placebo label pools (big_tech, china,
 supreme_court, disney; 500 each) into the same three coder pair-parts (A-B, B-C, A-C),
 balanced within target, every sentence coded twice. Separate files from the main split
 because the placebo codebook has a single stance column.
diff --git a/code/13w_rebuild_reduced_design.py b/code/3_human_coding/15_rebuild_reduced_design.py
similarity index 98%
rename from code/13w_rebuild_reduced_design.py
rename to code/3_human_coding/15_rebuild_reduced_design.py
index 402b7da..2abf4ec 100644
--- a/code/13w_rebuild_reduced_design.py
+++ b/code/3_human_coding/15_rebuild_reduced_design.py
@@ -1,5 +1,5 @@
 ###############################################################################
-# 13w_rebuild_reduced_design.py -- rebuild the Tenet stance-coding assignments
+# 15_rebuild_reduced_design.py -- rebuild the Tenet stance-coding assignments
 # for the reduced design adopted Nov 23, 2026 (PI: Jared Edgerton, PSU). Seed 123.
 #
 # Design
@@ -17,7 +17,7 @@
 #   - The Oct 9 pair assignment: each new sentence goes to ONE of its two
 #     originally assigned students (load-balanced within stratum).
 #
-# Usage: python3 13w_rebuild_reduced_design.py <podcast_analysis_root> <out_dir>
+# Usage: python3 15_rebuild_reduced_design.py <podcast_analysis_root> <out_dir>
 # Writes staged files to <out_dir>; nothing in coder_materials is modified.
 ###############################################################################
 import sys, os
diff --git a/code/13w_release.py b/code/3_human_coding/16_release_reduced_design.py
similarity index 94%
rename from code/13w_release.py
rename to code/3_human_coding/16_release_reduced_design.py
index b132cc4..c3a3be8 100644
--- a/code/13w_release.py
+++ b/code/3_human_coding/16_release_reduced_design.py
@@ -1,7 +1,7 @@
-# 13w_release.py -- release the Nov 23 reduced-design files to coders (run once).
+# 16_release_reduced_design.py -- release the Nov 23 reduced-design files to coders (run once).
 # Moves superseded files to coder_materials/_superseded/old_schedule_nov30/ and
 # copies staged files from coder_review/_staging_nov30/ into place. Logs every action.
-# Usage: python3 13w_release.py <podcast_analysis_root>
+# Usage: python3 16_release_reduced_design.py <podcast_analysis_root>
 import sys, os, shutil, glob, datetime
 import pandas as pd
 R = sys.argv[1]; CM = f"{R}/coder_materials"; ST = f"{R}/coder_review/_staging_nov30"; SUP = f"{CM}/_superseded/old_schedule_nov30"
diff --git a/code/12_build_panels.py b/code/5_analysis/25_build_panels.py
similarity index 99%
rename from code/12_build_panels.py
rename to code/5_analysis/25_build_panels.py
index da69293..11cd3c1 100644
--- a/code/12_build_panels.py
+++ b/code/5_analysis/25_build_panels.py
@@ -1,5 +1,5 @@
 """
-build_h_panels.py  --  the ONLY data-prep step (R lacks `arrow` on Roar).
+25_build_panels.py  --  the ONLY data-prep step (R lacks `arrow` on Roar).
 Aggregates the c0-labeled topic-78/79 corpus into show-month panel CSVs that the
 two R scripts consume. Does no modeling.
 
diff --git a/code/13_main_h1h3.R b/code/5_analysis/26_main_h1h3.R
similarity index 99%
rename from code/13_main_h1h3.R
rename to code/5_analysis/26_main_h1h3.R
index 8d40328..e26a3f3 100644
--- a/code/13_main_h1h3.R
+++ b/code/5_analysis/26_main_h1h3.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 13_main_h1h3.R  --  MAIN H1/H2/H3 with EVERY model written out explicitly
+# 26_main_h1h3.R  --  MAIN H1/H2/H3 with EVERY model written out explicitly
 # (no outcome for-loop, no per-outcome helper): each model is its own named object
 # so you can inspect them one at a time, e.g. summary(h1_rs_ctrl), h2_rs_scm.
 #
diff --git a/code/14_h4_tfidf_clean.py b/code/5_analysis/27_h4_tfidf_clean.py
similarity index 95%
rename from code/14_h4_tfidf_clean.py
rename to code/5_analysis/27_h4_tfidf_clean.py
index b4896ee..0bf9870 100644
--- a/code/14_h4_tfidf_clean.py
+++ b/code/5_analysis/27_h4_tfidf_clean.py
@@ -1,4 +1,4 @@
-"""clean_tfidf.py -- H4 companion: topic-level TF-IDF distinctive topics per Tenet
+"""27_h4_tfidf_clean.py -- H4 companion: topic-level TF-IDF distinctive topics per Tenet
 feed, with sponsor/ad-read and filler topics removed. Run as a job (corpus read
 is memory-heavy). Output: data/sc_results/h4_tfidf_clean.csv
 PI: Jared Edgerton (PSU)."""
diff --git a/code/14_h4_topic_model.py b/code/5_analysis/28_h4_topic_model.py
similarity index 99%
rename from code/14_h4_topic_model.py
rename to code/5_analysis/28_h4_topic_model.py
index 811c258..2474d69 100644
--- a/code/14_h4_topic_model.py
+++ b/code/5_analysis/28_h4_topic_model.py
@@ -1,5 +1,5 @@
 """
-22_agenda_divergence_panel.py  --  H4 (agenda divergence): build the per-show-month
+28_h4_topic_model.py  --  H4 (agenda divergence): build the per-show-month
 topic-distribution divergence panel that 23_h4_divergence_grid.R consumes.
 
 H4 = the Tenet hosts are paid to push a *divisive, distinctive agenda*. We measure
diff --git a/code/15_main_h4.R b/code/5_analysis/29_main_h4.R
similarity index 98%
rename from code/15_main_h4.R
rename to code/5_analysis/29_main_h4.R
index 3810039..3ca69d0 100644
--- a/code/15_main_h4.R
+++ b/code/5_analysis/29_main_h4.R
@@ -1,8 +1,8 @@
 ###############################################################################
-# 15_main_h4.R  --  MAIN H4 (agenda divergence) with EVERY model written out
+# 29_main_h4.R  --  MAIN H4 (agenda divergence) with EVERY model written out
 # explicitly (no loop, no helper-per-measure): each model is its own named object.
 #
-# Divergence panel from 14_h4_topic_model.py; MAIN spec rows only:
+# Divergence panel from 28_h4_topic_model.py; MAIN spec rows only:
 #   topicset = all, reference = contemp, rare = rare. One row per unit-month.
 # Measures: jsd (headline), kl_sm, cosine.
 # Controls ("ctrl" specs) = time-varying monthly audience (log_aud_m) + total words
diff --git a/code/16_grid_h1h2.R b/code/6_robustness/30_grid_h1h2.R
similarity index 99%
rename from code/16_grid_h1h2.R
rename to code/6_robustness/30_grid_h1h2.R
index 5b9a2f7..d7b9bf3 100644
--- a/code/16_grid_h1h2.R
+++ b/code/6_robustness/30_grid_h1h2.R
@@ -1,7 +1,7 @@
 ###############################################################################
-# 16_grid_h1h2.R  --  MASTER robustness grid for H1 (pre-payment level) and
-# H2 (post-payment DiD), one-factor-at-a-time off the MAIN spec (13_main_h1h3.R).
-# Supersedes the old probshift-only 16 AND 26_min_mention_sweep.R (folded in here).
+# 30_grid_h1h2.R  --  MASTER robustness grid for H1 (pre-payment level) and
+# H2 (post-payment DiD), one-factor-at-a-time off the MAIN spec (26_main_h1h3.R).
+# Supersedes the old probshift-only 16 AND 44_min_mention_sweep.R (folded in here).
 #
 # SAME BASIS AS 13/15:  time-varying monthly audience (log_aud_m) + total words
 # (log_words), month FE, TWO-WAY clustering (H1: month+unit ; H2: unit+month).
diff --git a/code/17_grid_summary.R b/code/6_robustness/31_grid_summary.R
similarity index 99%
rename from code/17_grid_summary.R
rename to code/6_robustness/31_grid_summary.R
index 24473ce..7b016a7 100644
--- a/code/17_grid_summary.R
+++ b/code/6_robustness/31_grid_summary.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 17_grid_summary.R  --  robustness summary of the H1/H2 master grid (16).
+# 31_grid_summary.R  --  robustness summary of the H1/H2 master grid (16).
 #   Reads master_grid_h1h2.csv (~993k rows) and produces a summary table +
 #   FOUR figures:
 #     (1) fig_prob_sweep.pdf   how shifting probability mass BETWEEN sentiment
diff --git a/code/17_relabel_sweep.R b/code/6_robustness/32_relabel_sweep.R
similarity index 98%
rename from code/17_relabel_sweep.R
rename to code/6_robustness/32_relabel_sweep.R
index 1a7e0f4..e2558fc 100644
--- a/code/17_relabel_sweep.R
+++ b/code/6_robustness/32_relabel_sweep.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# grid_sweep.R  --  perturbation-robustness sweep for H1 and H2 (NOT H3).
+# 32_relabel_sweep.R  --  perturbation-robustness sweep for H1 and H2 (NOT H3).
 #
 # Sweeps the 20 deterministic relabeling rules (R0 baseline .. G5) applied to the
 # c0 faithful labels, re-estimating H1 and H2 for all 9 stance outcomes.
diff --git a/code/18_label_noise.R b/code/6_robustness/33_label_noise.R
similarity index 98%
rename from code/18_label_noise.R
rename to code/6_robustness/33_label_noise.R
index 1b6e81c..0a94026 100644
--- a/code/18_label_noise.R
+++ b/code/6_robustness/33_label_noise.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 18_label_noise.R  --  label-perturbation robustness for H1/H2, in R (ports the
+# 33_label_noise.R  --  label-perturbation robustness for H1/H2, in R (ports the
 # old 18_label_noise.py so every regression is in R and runs interactively).
 #
 # Two families of perturbation to the discrete stance LABELS of mentioned
diff --git a/code/18_power_analysis.R b/code/6_robustness/35_power_analysis.R
similarity index 99%
rename from code/18_power_analysis.R
rename to code/6_robustness/35_power_analysis.R
index faffef8..4728023 100644
--- a/code/18_power_analysis.R
+++ b/code/6_robustness/35_power_analysis.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 18_power_analysis.R  --  minimum-detectable-effect / power for the post-payment
+# 35_power_analysis.R  --  minimum-detectable-effect / power for the post-payment
 # nulls (H2 stance, H3 agenda, H4 divergence). Turns "we found nothing" into
 # "we can rule out anything larger than X".
 #
diff --git a/code/19_loso_panel.py b/code/6_robustness/36_loso_panel.py
similarity index 98%
rename from code/19_loso_panel.py
rename to code/6_robustness/36_loso_panel.py
index 2b568fe..0e22c81 100644
--- a/code/19_loso_panel.py
+++ b/code/6_robustness/36_loso_panel.py
@@ -1,5 +1,5 @@
 """
-25_loso_panel.py  --  build PER-INDIVIDUAL-FEED panels for the leave-one-show-out
+36_loso_panel.py  --  build PER-INDIVIDUAL-FEED panels for the leave-one-show-out
 robustness (Tim Pool's three feeds are kept separate, unlike build_h_panels which
 pools them into tim_pool). Two outputs feed 26_loso.R:
 
diff --git a/code/20_loso_models.R b/code/6_robustness/37_loso_models.R
similarity index 98%
rename from code/20_loso_models.R
rename to code/6_robustness/37_loso_models.R
index d72a8ac..f2422d6 100644
--- a/code/20_loso_models.R
+++ b/code/6_robustness/37_loso_models.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 26_loso.R  --  leave-one-show-out / subset robustness. For every non-empty subset
+# 37_loso_models.R  --  leave-one-show-out / subset robustness. For every non-empty subset
 # of the 5 Tenet feeds (31 configs), re-estimate the MAIN specs for H1-H4 and record
 # the headline coefficient, to see whether any single host (or Tim feed) drives results.
 #
diff --git a/code/21_h1_inference.R b/code/6_robustness/38_h1_inference.R
similarity index 98%
rename from code/21_h1_inference.R
rename to code/6_robustness/38_h1_inference.R
index aa1b547..d5ed5e6 100644
--- a/code/21_h1_inference.R
+++ b/code/6_robustness/38_h1_inference.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 27_h1_inference.R  --  design-based / few-cluster-robust inference for H1.
+# 38_h1_inference.R  --  design-based / few-cluster-robust inference for H1.
 # The grid showed H1 is "never null"; with only 3 treated clusters the analytic
 # cluster-robust p-values are likely too small, so we use design-based inference:
 #
diff --git a/code/22_h1_altspecs.R b/code/6_robustness/39_h1_altspecs.R
similarity index 98%
rename from code/22_h1_altspecs.R
rename to code/6_robustness/39_h1_altspecs.R
index 63d0335..ff0e141 100644
--- a/code/22_h1_altspecs.R
+++ b/code/6_robustness/39_h1_altspecs.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 27b_h1_altspecs.R  --  alternative H1 (pre-payment "more pro-Russia") specs that
+# 39_h1_altspecs.R  --  alternative H1 (pre-payment "more pro-Russia") specs that
 # (1) drop the static listenership control [mean_audience is invariant per show, so
 #     it adds nothing under FE and is a cross-sectional nuisance under OLS],
 # (2) add month-FE and year-FE variants, and
diff --git a/code/23_h1_appendix.R b/code/6_robustness/40_h1_appendix.R
similarity index 98%
rename from code/23_h1_appendix.R
rename to code/6_robustness/40_h1_appendix.R
index 397a97a..c4844f5 100644
--- a/code/23_h1_appendix.R
+++ b/code/6_robustness/40_h1_appendix.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 27c_h1_appendix.R  --  appendix series of H1 (pre-payment "more pro-Russia") models,
+# 40_h1_appendix.R  --  appendix series of H1 (pre-payment "more pro-Russia") models,
 # varying the volume/exposure control set and the fixed-effects structure. Built on the
 # pooled baseline_panel (3 treated units: tim_pool, benny, rubin) to match the main spec.
 #
diff --git a/code/24_h3_topic_dist.py b/code/6_robustness/41_h3_topic_dist.py
similarity index 98%
rename from code/24_h3_topic_dist.py
rename to code/6_robustness/41_h3_topic_dist.py
index 3c704d4..64fc16a 100644
--- a/code/24_h3_topic_dist.py
+++ b/code/6_robustness/41_h3_topic_dist.py
@@ -1,5 +1,5 @@
 """
-20_topic_distribution.py  --  recover the per-sentence topic probabilities needed
+41_h3_topic_dist.py  --  recover the per-sentence topic probabilities needed
 for the H3 topic mass-transfer grid (21_h3_topic_grid.py). 6_topic_model.py ran
 with calculate_probabilities=False, so only the hard `topic` was saved; here we
 reload the fitted BERTopic model and recompute a distribution via
diff --git a/code/24_h3_topic_grid.R b/code/6_robustness/42_h3_topic_grid.R
similarity index 99%
rename from code/24_h3_topic_grid.R
rename to code/6_robustness/42_h3_topic_grid.R
index bd98853..4f01427 100644
--- a/code/24_h3_topic_grid.R
+++ b/code/6_robustness/42_h3_topic_grid.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 21_h3_topic_grid.R  --  topic mass-transfer robustness grid for H3 (agenda:
+# 42_h3_topic_grid.R  --  topic mass-transfer robustness grid for H3 (agenda:
 # share of discussion devoted to the Russia/Ukraine topics). Topic analog of
 # 19_probshift_grid.R; reuses the same TWFE + SCM (in-space placebo) machinery.
 #
diff --git a/code/25_h4_divergence_grid.R b/code/6_robustness/43_h4_divergence_grid.R
similarity index 99%
rename from code/25_h4_divergence_grid.R
rename to code/6_robustness/43_h4_divergence_grid.R
index a244680..4574add 100644
--- a/code/25_h4_divergence_grid.R
+++ b/code/6_robustness/43_h4_divergence_grid.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 23_h4_divergence_grid.R  --  H4 (agenda divergence): estimate H4a (pre-payment
+# 43_h4_divergence_grid.R  --  H4 (agenda divergence): estimate H4a (pre-payment
 # level) and H4b (post-payment DiD) across the operationalization grid built by
 # 22_agenda_divergence_panel.py. Reuses the TWFE + SCM (in-space placebo) machinery.
 #
diff --git a/code/26_min_mention_sweep.R b/code/6_robustness/44_min_mention_sweep.R
similarity index 98%
rename from code/26_min_mention_sweep.R
rename to code/6_robustness/44_min_mention_sweep.R
index 07a83ad..fe1391d 100644
--- a/code/26_min_mention_sweep.R
+++ b/code/6_robustness/44_min_mention_sweep.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 26_min_mention_sweep.R  --  robustness sweep over the MINIMUM-MENTIONS inclusion
+# 44_min_mention_sweep.R  --  robustness sweep over the MINIMUM-MENTIONS inclusion
 # threshold, crossed with the unmentioned-coding choice, to produce a DISTRIBUTION
 # of H1/H2 coefficients instead of betting on one threshold. Pure R, interactive.
 #
diff --git a/code/27_descriptives.R b/code/7_outputs/45_descriptives.R
similarity index 96%
rename from code/27_descriptives.R
rename to code/7_outputs/45_descriptives.R
index 11d5b7f..99800cc 100644
--- a/code/27_descriptives.R
+++ b/code/7_outputs/45_descriptives.R
@@ -1,6 +1,6 @@
 ###############################################################################
-# 27_descriptives.R  --  descriptive statistics table for outcomes + IVs.
-# Builds the SAME show-month panel as 13_main_h1h3.R (identical variable
+# 45_descriptives.R  --  descriptive statistics table for outcomes + IVs.
+# Builds the SAME show-month panel as 26_main_h1h3.R (identical variable
 # construction), then writes a treated-vs-control descriptives table to
 #   data/sc_results/tab_descriptives.tex   (LaTeX, booktabs)
 #   data/sc_results/tab_descriptives.csv   (machine-readable)
@@ -15,7 +15,7 @@ TIM <- c("timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim
 TRU <- c("tim_pool", "the_benny_show", "the_rubin_report")
 BEN <- c("the_benny_show", "benny_johnson_arena")   # Tenet Arena feed pooled into Benny
 
-## ---- panel build (mirrors 13_main_h1h3.R) -----------------------------------
+## ---- panel build (mirrors 26_main_h1h3.R) -----------------------------------
 P <- fread(file.path(SC, "baseline_panel.csv")); P[, month := as.Date(month)]; P <- P[month < TRUNC]
 P[, tenet := as.integer(unit %in% TRU)]
 P[, c_score := r_score - u_score]; P[, c_pos := r_pos - u_pos]; P[, c_net := r_net - u_net]
diff --git a/code/28_label_examples.py b/code/7_outputs/46_label_examples.py
similarity index 98%
rename from code/28_label_examples.py
rename to code/7_outputs/46_label_examples.py
index 079ae0f..dcde93a 100644
--- a/code/28_label_examples.py
+++ b/code/7_outputs/46_label_examples.py
@@ -1,5 +1,5 @@
 """
-28_label_examples.py  --  reviewer-facing exhibit of the stance coding scheme.
+46_label_examples.py  --  reviewer-facing exhibit of the stance coding scheme.
 For each target (Russia, Ukraine) and stance label (positive/negative/neutral),
 pull the highest-confidence example SENTENCES from the labeled corpus so a reader
 can see what the classifier calls positive vs. negative.
diff --git a/code/29_figures.R b/code/7_outputs/47_figures.R
similarity index 99%
rename from code/29_figures.R
rename to code/7_outputs/47_figures.R
index 1491fa7..92747b5 100644
--- a/code/29_figures.R
+++ b/code/7_outputs/47_figures.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 29_figures.R  --  publication figures for H1-H4, built from the same panels
+# 47_figures.R  --  publication figures for H1-H4, built from the same panels
 # as 13/15.
 #   fig1_predicted.pdf    MAIN: model-predicted headline outcome, Tenet vs
 #                         non-Tenet, one panel per hypothesis (H1-H4).
diff --git a/code/30_make_tables.R b/code/7_outputs/48_make_tables.R
similarity index 99%
rename from code/30_make_tables.R
rename to code/7_outputs/48_make_tables.R
index 4b7795c..47d5995 100644
--- a/code/30_make_tables.R
+++ b/code/7_outputs/48_make_tables.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 30_make_tables.R  --  manuscript tables (LaTeX) from the panels.
+# 48_make_tables.R  --  manuscript tables (LaTeX) from the panels.
 #   table1_summary.tex   Summary statistics: every IV and DV used in H1-H4.
 #   table2_h1.tex        H1 (selection) across the 4 model specifications
 #                        (Simple | Simple matched | + Controls | + Controls matched).
diff --git a/code/30_manuscript_tables.R b/code/7_outputs/49_manuscript_tables.R
similarity index 98%
rename from code/30_manuscript_tables.R
rename to code/7_outputs/49_manuscript_tables.R
index ea7939b..2daedad 100644
--- a/code/30_manuscript_tables.R
+++ b/code/7_outputs/49_manuscript_tables.R
@@ -1,5 +1,5 @@
 ###############################################################################
-# 30_manuscript_tables.R  --  formatted LaTeX manuscript tables (Table 1/2/3)
+# 49_manuscript_tables.R  --  formatted LaTeX manuscript tables (Table 1/2/3)
 # from the saved main_*.csv that 13/15 write. Cells = estimate with significance
 # stars and the clustered p-value in parentheses.
 #   Table 1  (tab_main1.tex)  H1 SELECTION  -- pre-payment level, 4 specs
diff --git a/code/01_pull_data.sbatch b/code/slurm/01_pull_data.sbatch
similarity index 85%
rename from code/01_pull_data.sbatch
rename to code/slurm/01_pull_data.sbatch
index 459a745..35ab8b9 100644
--- a/code/01_pull_data.sbatch
+++ b/code/slurm/01_pull_data.sbatch
@@ -21,7 +21,6 @@ module load anaconda3
 # conda activate podcast_env
 
 # ── Run the RSS puller for all 290 feeds ──
-cd /scratch/jfe4/podcast/code
-python 01_pull_data.py
+python /storage/group/LiberalArts/default/jfe4_collab/podcast/tenet_media_repo/code/1_collect/01_pull_data.py
 
 echo "Done. Exit code: $?"
diff --git a/code/02_download_audio.sbatch b/code/slurm/02_download_audio.sbatch
similarity index 91%
rename from code/02_download_audio.sbatch
rename to code/slurm/02_download_audio.sbatch
index c3bf822..fc10474 100644
--- a/code/02_download_audio.sbatch
+++ b/code/slurm/02_download_audio.sbatch
@@ -14,7 +14,7 @@
 # ------------------------------------------------
 
 PROJECT_DIR=/scratch/jfe4/podcast
-CODE_DIR=${PROJECT_DIR}/code
+CODE_DIR=/storage/group/LiberalArts/default/jfe4_collab/podcast/tenet_media_repo/code/1_collect  # repo copy on Collab
 LOG_DIR=${PROJECT_DIR}/logs
 
 mkdir -p ${LOG_DIR}
diff --git a/code/04_transcribe.sbatch b/code/slurm/04_transcribe.sbatch
similarity index 88%
rename from code/04_transcribe.sbatch
rename to code/slurm/04_transcribe.sbatch
index 510cd7a..7aa3aa4 100644
--- a/code/04_transcribe.sbatch
+++ b/code/slurm/04_transcribe.sbatch
@@ -19,4 +19,4 @@ export PATH=$C/venv_whisper/bin:$PATH     # use the imageio-ffmpeg static binary
 cd $C
 source $C/venv_whisper/bin/activate
 echo "Host: $(hostname)"; nvidia-smi -L
-python $C/code/04_transcribe.py --csv $C/file_key.csv --run-one ${SLURM_ARRAY_TASK_ID} --model small
+python $C/tenet_media_repo/code/1_collect/04_transcribe.py --csv $C/file_key.csv --run-one ${SLURM_ARRAY_TASK_ID} --model small
diff --git a/code/05w_build_docs.sbatch b/code/slurm/05_build_sentence_docs.sbatch
similarity index 88%
rename from code/05w_build_docs.sbatch
rename to code/slurm/05_build_sentence_docs.sbatch
index 31b0fb1..519e2e1 100644
--- a/code/05w_build_docs.sbatch
+++ b/code/slurm/05_build_sentence_docs.sbatch
@@ -27,5 +27,5 @@ export NLTK_DATA=/storage/home/jfe4/nltk_data
 SHARD=$(printf corpus_part_%04d.parquet $SLURM_ARRAY_TASK_ID)
 mkdir -p $OUTBASE/corpus_shards
 echo "WINDOW=$WINDOW START=$START END=$END SHARD=$SHARD $(date)"
-python $CODE/05w_build_docs.py --window $WINDOW --transcript_dir $COLLAB/transcript_key --output $OUTBASE/corpus_shards/$SHARD --start $START --end $END
+python $CODE/2_corpus/05_build_sentence_docs.py --window $WINDOW --transcript_dir $COLLAB/transcript_key --output $OUTBASE/corpus_shards/$SHARD --start $START --end $END
 echo "DONE window=$WINDOW $(date)"
diff --git a/code/merge_window.sbatch b/code/slurm/06_merge_windows.sbatch
similarity index 87%
rename from code/merge_window.sbatch
rename to code/slurm/06_merge_windows.sbatch
index dd70e4a..b1a0875 100644
--- a/code/merge_window.sbatch
+++ b/code/slurm/06_merge_windows.sbatch
@@ -15,5 +15,5 @@ case "$WINDOW" in 1) WDIR=one_sentence ;; 3) WDIR=three_sentence ;; 5) WDIR=five
 OUT=$COLLAB/data/windows/$WDIR
 module load python/3.11.2
 source $COLLAB/venv_analysis/bin/activate
-python $CODE/05_merge_corpus.py --shards_dir $OUT/corpus_shards --output $OUT/corpus.parquet
+python $CODE/2_corpus/06_merge_windows.py --shards_dir $OUT/corpus_shards --output $OUT/corpus.parquet
 echo "MERGED window=$WINDOW $(date)"
diff --git a/code/06_topic_model.sbatch b/code/slurm/07_topic_model.sbatch
similarity index 89%
rename from code/06_topic_model.sbatch
rename to code/slurm/07_topic_model.sbatch
index 03b37cf..de6c837 100644
--- a/code/06_topic_model.sbatch
+++ b/code/slurm/07_topic_model.sbatch
@@ -24,5 +24,5 @@ export TRANSFORMERS_OFFLINE=1
 echo "topic_model start $(hostname) $(date)"
 echo "CORPUS=$CORPUS SAMPLE_SIZE=$SAMPLE_SIZE OUTPUT_DIR=$OUTPUT_DIR"
 python -c "import torch; print('CUDA available:', torch.cuda.is_available(), 'device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
-python $COLLAB/tenet_media_repo/code/06_topic_model.py --corpus $CORPUS --sample-size $SAMPLE_SIZE --output-dir $OUTPUT_DIR
+python $COLLAB/tenet_media_repo/code/2_corpus/07_topic_model.py --corpus $CORPUS --sample-size $SAMPLE_SIZE --output-dir $OUTPUT_DIR
 echo "topic_model done $(date)"
diff --git a/code/identify_window.sbatch b/code/slurm/08_identify_topics.sbatch
similarity index 89%
rename from code/identify_window.sbatch
rename to code/slurm/08_identify_topics.sbatch
index 51ade07..fbdde36 100644
--- a/code/identify_window.sbatch
+++ b/code/slurm/08_identify_topics.sbatch
@@ -14,5 +14,5 @@ CODE=$COLLAB/tenet_media_repo/code
 case "$WINDOW" in 1) WD=one_sentence;; 3) WD=three_sentence;; 5) WD=five_sentence;; *) exit 1;; esac
 module load python/3.11.2
 source $COLLAB/venv_analysis/bin/activate
-python $CODE/07w_identify_topics.py --window-dir $COLLAB/data/windows/$WD
+python $CODE/2_corpus/08_identify_topics.py --window-dir $COLLAB/data/windows/$WD
 echo "IDENTIFY DONE window=$WINDOW $(date)"
diff --git a/code/build_label_pools_v3.sbatch b/code/slurm/09_build_label_pools.sbatch
similarity index 80%
rename from code/build_label_pools_v3.sbatch
rename to code/slurm/09_build_label_pools.sbatch
index a490aab..4694b2a 100644
--- a/code/build_label_pools_v3.sbatch
+++ b/code/slurm/09_build_label_pools.sbatch
@@ -13,5 +13,5 @@ W=${WD:-one_sentence}
 module load python/3.11.2
 source $C/venv_analysis/bin/activate
 export PYTHONUNBUFFERED=1
-python $C/tenet_media_repo/code/build_label_pools_v3.py --window-dir $C/data/windows/$W --out-dir $C/data/label_sheets_fixed/$W
+python $C/tenet_media_repo/code/2_corpus/09_build_label_pools.py --window-dir $C/data/windows/$W --out-dir $C/data/label_sheets_fixed/$W
 echo DONE_V3
diff --git a/code/run_windows_full.sh b/code/slurm/run_corpus_05_to_08.sh
similarity index 82%
rename from code/run_windows_full.sh
rename to code/slurm/run_corpus_05_to_08.sh
index ff8737c..68c4aa8 100755
--- a/code/run_windows_full.sh
+++ b/code/slurm/run_corpus_05_to_08.sh
@@ -12,10 +12,10 @@ for W in 1 3 5; do
   case $W in 1) WD=one_sentence;; 3) WD=three_sentence;; 5) WD=five_sentence;; esac
   OUT=$C/data/windows/$WD
   rm -rf $OUT/corpus_shards; mkdir -p $OUT/corpus_shards
-  JB=$(WINDOW=$W sbatch --parsable --account=$ACC --array=0-$LAST $CODE/05w_build_docs.sbatch)
-  JM=$(WINDOW=$W sbatch --parsable --account=$ACC --dependency=afterok:$JB $CODE/merge_window.sbatch)
-  JT=$(CORPUS=$OUT/corpus.parquet OUTPUT_DIR=$OUT sbatch --parsable --dependency=afterok:$JM $CODE/06_topic_model.sbatch)
-  JI=$(WINDOW=$W sbatch --parsable --account=$ACC --dependency=afterok:$JT $CODE/identify_window.sbatch)
+  JB=$(WINDOW=$W sbatch --parsable --account=$ACC --array=0-$LAST $CODE/slurm/05_build_sentence_docs.sbatch)
+  JM=$(WINDOW=$W sbatch --parsable --account=$ACC --dependency=afterok:$JB $CODE/slurm/06_merge_windows.sbatch)
+  JT=$(CORPUS=$OUT/corpus.parquet OUTPUT_DIR=$OUT sbatch --parsable --dependency=afterok:$JM $CODE/slurm/07_topic_model.sbatch)
+  JI=$(WINDOW=$W sbatch --parsable --account=$ACC --dependency=afterok:$JT $CODE/slurm/08_identify_topics.sbatch)
   echo "W=$W  build=$JB  merge=$JM  topic=$JT  identify=$JI"
 done
 echo ALL_SUBMITTED
```

## New files

### `code/2_corpus/06_merge_windows.py`
```python
"""06_merge_windows.py (restored from 05_merge_corpus.py, deleted in 989f0a9 but still called by the corpus chain) - Streaming merge of corpus_shards/*.parquet into one corpus.parquet (memory-safe via pyarrow ParquetWriter)."""
import argparse, logging
from pathlib import Path
import pyarrow.parquet as pq
logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(levelname)-8s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger('merge')
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--shards_dir', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    shards = sorted(Path(a.shards_dir).glob('corpus_part_*.parquet'))
    log.info('merging %d shards -> %s', len(shards), a.output)
    if not shards:
        raise SystemExit('no shards')
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    writer = None
    total = 0
    for sh in shards:
        log.info('reading %s', sh)
        t = pq.read_table(sh)
        if writer is None:
            writer = pq.ParquetWriter(a.output, t.schema)
        writer.write_table(t)
        total += t.num_rows
    if writer: writer.close()
    log.info('MERGE_DONE rows=%d -> %s', total, a.output)
if __name__ == '__main__': main()
```

### `code/3_human_coding/17_build_adjudication.py`
```python
"""17_build_adjudication.py -- PLANNED, NOT YET IMPLEMENTED.
Collect every coder disagreement into a blind A/B adjudication sheet for the PI (labels shown without coder identity).
See README.md (pipeline table) for status."""
raise SystemExit("17_build_adjudication.py is a planned step and has not been implemented yet.")
```

The other placeholders (18–24, 34) follow the same pattern.

### `run_all.sh`
```bash
#!/bin/bash
# run_all.sh -- the Tenet Media pipeline in run order (steps 01-49).
#
#   ./run_all.sh                 print every command (dry run, the default)
#   ./run_all.sh --stage 5       print stage 5 only
#   ./run_all.sh --stage 5 --run actually run stage 5
#
# Planned steps (placeholders that raise an error) are skipped and reported.
# Design-time steps 10-16 already ran and build the coder files. They are listed but never
# re-run here, because re-running would overwrite the files coders are working in.
# Roar paths: COLLAB is the data root (see config/README.md). Seed 123 throughout.
set -euo pipefail
cd "$(dirname "$0")"
export COLLAB=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}

STAGE=all; RUN=0
while [ $# -gt 0 ]; do
  case $1 in
    --stage) STAGE=$2; shift 2;;
    --run) RUN=1; shift;;
    *) echo "unknown arg $1"; exit 1;;
  esac
done

do_cmd () { if [ $RUN -eq 1 ]; then echo "+ $*"; eval "$@"; else echo "  $*"; fi; }
planned () { echo "  [skip] $1 -- planned, not yet implemented"; }
want () { [ "$STAGE" = all ] || [ "$STAGE" = "$1" ]; }

if want 1; then echo "== 1_collect (Roar) =="
  do_cmd sbatch code/slurm/01_pull_data.sbatch
  do_cmd sbatch code/slurm/02_download_audio.sbatch
  do_cmd python code/1_collect/03_create_key.py
  echo "  # 04 is a job array, one episode per task; set --array to the rows of file_key.csv"
  do_cmd sbatch --array=0-N code/slurm/04_transcribe.sbatch
fi

if want 2; then echo "== 2_corpus (Roar) =="
  do_cmd bash code/slurm/run_corpus_05_to_08.sh        # 05 build -> 06 merge -> 07 topics -> 08 identify, per window
  do_cmd sbatch code/slurm/09_build_label_pools.sbatch
fi

if want 3; then echo "== 3_human_coding =="
  echo "  [design-time, already run] 10_draw_union_sample 11_draw_nonunion_sample 12_build_disney_pool"
  echo "  [design-time, already run] 13_assign_coders 14_assign_placebo 15_rebuild_reduced_design 16_release_reduced_design"
  planned 17_build_adjudication
  planned 18_icr_report
  planned 19_lock_gold
fi

if want 4; then echo "== 4_classify (Roar GPU) =="
  planned 20_gate_train
  planned 21_gate_infer
  planned 22_stance_train
  planned 23_stance_infer
  planned 24_merge_predictions
fi

if want 5; then echo "== 5_analysis =="
  do_cmd python code/5_analysis/25_build_panels.py
  do_cmd Rscript code/5_analysis/26_main_h1h3.R
  do_cmd python code/5_analysis/27_h4_tfidf_clean.py
  do_cmd python code/5_analysis/28_h4_topic_model.py
  do_cmd Rscript code/5_analysis/29_main_h4.R
fi

if want 6; then echo "== 6_robustness =="
  do_cmd Rscript code/6_robustness/30_grid_h1h2.R
  do_cmd Rscript code/6_robustness/31_grid_summary.R
  do_cmd Rscript code/6_robustness/32_relabel_sweep.R
  do_cmd Rscript code/6_robustness/33_label_noise.R
  planned 34_error_propagation
  do_cmd Rscript code/6_robustness/35_power_analysis.R
  do_cmd python code/6_robustness/36_loso_panel.py
  do_cmd Rscript code/6_robustness/37_loso_models.R
  do_cmd Rscript code/6_robustness/38_h1_inference.R
  do_cmd Rscript code/6_robustness/39_h1_altspecs.R
  do_cmd Rscript code/6_robustness/40_h1_appendix.R
  do_cmd python code/6_robustness/41_h3_topic_dist.py
  do_cmd Rscript code/6_robustness/42_h3_topic_grid.R
  do_cmd Rscript code/6_robustness/43_h4_divergence_grid.R
  do_cmd Rscript code/6_robustness/44_min_mention_sweep.R
fi

if want 7; then echo "== 7_outputs =="
  do_cmd Rscript code/7_outputs/45_descriptives.R
  do_cmd python code/7_outputs/46_label_examples.py
  do_cmd Rscript code/7_outputs/47_figures.R
  do_cmd Rscript code/7_outputs/48_make_tables.R
  do_cmd Rscript code/7_outputs/49_manuscript_tables.R
fi

[ $RUN -eq 1 ] || echo "(dry run -- add --run to execute)"
```

### `config/README.md`
```markdown
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
```

### `archive/README.md`
```markdown
# archive/

Code that is not part of the active pipeline in `code/`. It is kept for the record and
nothing in `code/` calls it. Old → new names for every move are in `RENAMES.md`.

## pre_two_stage/ — earlier measurement design (topic 78/79 sample + LLM/BERT distillation)
| File | What it was |
|---|---|
| `09_sample_validation.*` | 1,500-sentence validation sample from topics 78/79 |
| `10a–10c_validation_freshtest*.*` | Fresh test draws excluding earlier samples |
| `10d_validation_stance_sample.*` | Stance sample with neighbor-sentence context |
| `10e_validation_vset.*` | Validation set draw |
| `11a_codebook_label.py`, `11a_codebook_label_run.py`, `11a_stance_codebook.md` | 8-condition LLM codebook labeling (bias sensitivity) |
| `11b_bert_build_data.py` | Per-(coder, condition) training tables + human-gold test |
| `11c_bert_train_infer.py`, `11c_bert_grid.sbatch` | RoBERTa fine-tune + inference grid |
| `11d_bert_aggregate.py` | Merge prediction shards per cell |
| `11e_merge_preds.py` | Merge 4-class softmax shards → `opus_c0_corpus_labeled.parquet` |

Replaced by human double-coding (`code/3_human_coding`) and the two-stage gate + stance
classifier (`code/4_classify`).

## superseded/ — replaced by a newer version in `code/`
| File | Replaced by |
|---|---|
| `02_transcribe_missing.sbatch` | `code/slurm/04_transcribe.sbatch` (legacy paths) |
| `05_build_corpus_shard.*` | `05_build_sentence_docs.py` (windowed) |
| `07_identify_russia_topics.*` | `08_identify_topics.py` (keyword topic ID; refits renumber topics) |
| `build_label_pools.*`, `build_label_pools_v2.*` | `09_build_label_pools.py` (was v3) |
| `build_workbooks.py` | `15_rebuild_reduced_design.py` |
| `16_grid_h1h2_v2.R` | `30_grid_h1h2.R` (31 reads the v1 output) |
| `16_summarize_grid.py` | `31_grid_summary.R` (read an orphaned probshift CSV) |
| `25_run_h4.sbatch` | none needed (legacy paths) |

## coding_history/ — one-off inter-coder checks from earlier rounds
| File | What it was |
|---|---|
| `icr200.py` | 200-sentence ICR round |
| `icr_round3.py` | ICR round 3 |
| `icr_supp.py` | Supplementary ICR check |

## exploratory/ — not used in the manuscript
| File | What it was |
|---|---|
| `31_ranked_prepost.R` | Standalone ranked pre/post figure |
| `sample_3sent_ru*.{py,sbatch}` (v1, v2) | 3-sentence Russia sample draws |

## slurm_runs/ — one-off batch wrappers for past runs
`fig29.sbatch`, `grid16_3day.sbatch`, `rerun_figs24.sbatch`, `run_final_all.sbatch`,
`run_grid_all.sbatch`, `run_rerun_benny.sbatch`. They call old script names and are kept
only as a record of what was run.
```

### `README.md`
```markdown
# Tenet Media / Foreign-Influence Podcast Analysis

Did Russian funding routed through **Tenet Media** change how three treated podcasts
(Benny Johnson, Dave Rubin, and Tim Pool — his three feeds pooled) discuss
Russia/Ukraine, relative to ~280 control conservative podcasts? The project transcribes
~230K episodes, models topics, classifies **stance** toward Russia/Ukraine, and uses
difference-in-differences / synthetic-control designs to measure shifts in stance,
agenda emphasis, and agenda divergence around the payment period.

**Treatment date:** `2023-10-01` — the first RT payment to Tenet (DOJ indictment: wires
Oct 2023–Aug 2024), ~1 month before Tenet's public Nov-2023 launch. Panel 2018-01 →
2024-08, truncated at the Sept 4 2024 indictment.

## Measurement (important — this is stance, not sentiment)

The analyses use **human + machine stance labeling on the Russia/Ukraine topics**, not an
off-the-shelf sentiment model:

1. **Topics.** BERTopic locates the Russia/Ukraine topics BY KEYWORD. Topic IDs change on every refit, so the old hardcoded {78, 79} no longer applies. Documents are built at 1, 3, and 5 sentences (main = 1-sentence; 3/5 = appendix).
2. **Human coding.** 8,000 one-sentence documents (union of Russia/Ukraine topic sentences,
   hard negatives, pre/post non-union draws, and 1,000 placebo-entity sentences) are
   double-coded for *stance toward each target* (codebook v2.6; placebo v1.3) and
   adjudicated to a gold set.
3. **Machine labeling (two-stage).** A relevance gate (mentioned vs. unmentioned) is
   trained on the gold set and run over the full one-sentence corpus; a 4-class stance
   model (positive / negative / neutral / unmentioned, per target) then labels the
   gate-passing sentences. Human-label error is propagated into H1/H2 (step 34).

Outcomes per target: `score` = p_pos − p_neg, `pos` = positive rate, `net` = (pos − neg)
ordinal. **Combined** = Russia − Ukraine (anti-Ukraine ≈ pro-Russia). The earlier generic
**sentiment** pass is deprecated and not used anywhere in the current pipeline.

## Hypotheses
- **H1** — treated hosts were already more pro-Russia *before* the payments (selection).
- **H2** — the payments pushed them further pro-Russia / anti-Ukraine (treatment).
- **H3** — the payments changed the *agenda* (Russia's share of total discussion).
- **H4** — treated hosts ran a more *divergent overall agenda* (divisive non-Russia content).

## Pipeline

Every active script has a unique two-digit number (01–49) in run order. Stages are folders.
`code/slurm/` holds the Roar job files (named for the step they run). Superseded and
exploratory code is in `archive/` (see `archive/README.md`; old → new names in
`archive/RENAMES.md`). Status as of 2026-11-23: **done** = has run on Roar and its output
exists; **re-run** = built and run on the earlier labels, must re-run once step 24 exists;
**planned** = placeholder that raises an error.

| # | Script | Does | Status |
|---|--------|------|--------|
| **1_collect** | | | |
| 01 | `01_pull_data.py` | RSS feeds (`inputs/podcast_feeds.csv`) → episode metadata JSON | done |
| 02 | `02_download_audio.py` | Download episode MP3s | done |
| 03 | `03_create_key.py` | File key; flag missing transcripts | done |
| 04 | `04_transcribe.py` | Whisper ASR → transcripts | done |
| **2_corpus** | | | |
| 05 | `05_build_sentence_docs.py` | Within-episode W-sentence documents (W = 1/3/5), sharded | done |
| 06 | `06_merge_windows.py` | Merge shards → `data/windows/{W}/corpus.parquet` | done |
| 07 | `07_topic_model.py` | BERTopic fit per window | done |
| 08 | `08_identify_topics.py` | Keyword-match Russia/Ukraine + placebo topics → `topic_labels.csv`, `russia_corpus.parquet` | done |
| 09 | `09_build_label_pools.py` | Regex label pools (Russia/Ukraine + placebo entities) → `label_sheets_fixed/` | done |
| **3_human_coding** | | | |
| 10 | `10_draw_union_sample.py` | Draw union-of-topics coding sample | done |
| 11 | `11_draw_nonunion_sample.py` | Draw non-union strata (pre/post) + hard negatives | done |
| 12 | `12_build_disney_pool.py` | Disney placebo pool | done |
| 13 | `13_assign_coders.py` | Original coder assignment (Oct 9) | done; superseded by 15 |
| 14 | `14_assign_placebo.py` | Placebo assignment (Oct 9) | done; superseded by 15 |
| 15 | `15_rebuild_reduced_design.py` | Reduced 8,000-sentence design; every sentence = Jared + 1 student | done (Nov 23); GPT audit pending |
| 16 | `16_release_reduced_design.py` | One-time release of 15's files to coder Dropbox folders | done (Nov 30 schedule) |
| 17 | `17_build_adjudication.py` | Blind A/B adjudication sheets from disagreements | planned |
| 18 | `18_icr_report.py` | Krippendorff's α from raw codes, by target/stratum/pair | planned |
| 19 | `19_lock_gold.py` | Freeze adjudicated gold set + confusion matrices | planned |
| **4_classify** | | | |
| 20 | `20_gate_train.py` | Train relevance gate on gold (seed 123) | planned |
| 21 | `21_gate_infer.py` | Gate over full one-sentence corpus | planned |
| 22 | `22_stance_train.py` | Train 4-class stance × 2 targets (twitter-roberta, seed 123) | planned |
| 23 | `23_stance_infer.py` | Stance over gate-passing sentences | planned |
| 24 | `24_merge_predictions.py` | Corpus-level labeled file for 25 | planned |
| **5_analysis** | | | |
| 25 | `25_build_panels.py` | Show × month stance/volume panels + audience | re-run |
| 26 | `26_main_h1h3.R` | Main H1/H2/H3 (FE, matched FE, TWFE, SCM) | re-run |
| 27 | `27_h4_tfidf_clean.py` | H4 distinctive-topic TF-IDF | re-run |
| 28 | `28_h4_topic_model.py` | H4 agenda-divergence panel | re-run |
| 29 | `29_main_h4.R` | Main H4 (JSD/KL/cosine DiD) | re-run |
| **6_robustness** | | | |
| 30 | `30_grid_h1h2.R` | H1/H2 probability mass-transfer grid | re-run |
| 31 | `31_grid_summary.R` | Summarize 30 | re-run |
| 32 | `32_relabel_sweep.R` | Discrete relabel sweep | re-run |
| 33 | `33_label_noise.R` | Random-flip / recode label noise | re-run |
| 34 | `34_error_propagation.R` | Confusion-matrix MI of human-label error through H1/H2 | planned |
| 35 | `35_power_analysis.R` | MDE / power, post-payment | re-run |
| 36 | `36_loso_panel.py` | Per-feed panels (Tim split) | re-run |
| 37 | `37_loso_models.R` | Leave-one-show-out, H1–H4 | re-run |
| 38 | `38_h1_inference.R` | Randomization inference, H1 | re-run |
| 39 | `39_h1_altspecs.R` | Alternative H1 specs | re-run |
| 40 | `40_h1_appendix.R` | H1 appendix series | re-run |
| 41 | `41_h3_topic_dist.py` | Per-sentence topic probabilities for H3 | re-run |
| 42 | `42_h3_topic_grid.R` | H3 topic mass-transfer grid | re-run |
| 43 | `43_h4_divergence_grid.R` | H4 divergence grid | re-run |
| 44 | `44_min_mention_sweep.R` | Min-mentions threshold sweep | re-run |
| **7_outputs** | | | |
| 45 | `45_descriptives.R` | Descriptives table | re-run |
| 46 | `46_label_examples.py` | Coding-scheme exhibit | re-run |
| 47 | `47_figures.R` | Publication figures H1–H4 | re-run |
| 48 | `48_make_tables.R` | Manuscript tables (LaTeX) | re-run |
| 49 | `49_manuscript_tables.R` | Formatted Tables 1–3 | re-run |

Repo layout: `code/` (pipeline), `code/slurm/` (Roar jobs), `config/` (environments,
paths), `inputs/` (feed lists), `docs/` (audit prompts, notes), `tests/`, `archive/`.

## Designs
OLS / Mahalanobis-matched level comparison (H1); TWFE (`fixest`) + synthetic control
(`quadprog` simplex weights, in-space placebo p-values) for H2/H3; Jensen-Shannon agenda
divergence vs. the contemporaneous control consensus for H4. Time-varying total-words and
month/host fixed effects as controls. Seed 123 throughout.

## Data (not in this repo)
Audio, transcripts, corpora, topic models, coder files and results live on Roar Collab
under `$COLLAB` (default `/storage/group/LiberalArts/default/jfe4_collab/podcast`) and, for
human coding, in Dropbox (`podcast_analysis/coder_materials`, `coder_review`). See
`config/README.md`. Data-access plan for replication: TBD.

## Running
`run_all.sh` lists the steps in order (`./run_all.sh --stage 5` runs one stage; planned
steps are skipped). Steps 01–09 and 20–23 are Roar jobs (`sbatch code/slurm/...`). The R
layer runs with `module load r` on Roar or locally. Seed 123 throughout.

Known gaps: many scripts still hard-code `/storage/...` paths (to be moved to `$COLLAB`);
01/02 slurm logs point at `/scratch` from the 2025 collection run; environments are listed
in `config/` but not pinned. PI: Jared Edgerton (PSU).
```
