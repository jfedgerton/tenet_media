# GPT audit C: follow-up on fixes for audits A and B (commit b3fec03)

You (or another GPT session) audited this repo earlier. This packet contains ONLY the fixes made in response. Everything you need is pasted below.

## What each earlier finding became
| Finding | Decision | Fix |
|---|---|---|
| A1 uncodable-with-blank rows treated as blanks | Keep as run (changing 15 would change files already released to coders) | Documented in 15's header; adjudication rule written into the 17 placeholder |
| A2 blanks coded by the other student not returned | Correct by design (returning would make 3 coders) | Documented as an explicit exception in 15's header |
| A3 balance on totals, not per stratum | Keep as run (same reason as A1) | Docstring corrected; per-stratum and per-target counts now logged at step [5] |
| A4/A5 release script limits | Already run once, never re-run; audit found nothing lost | Note added to 16's header |
| A6 test did not run 15 | Fixed | New end-to-end test (pasted in full) |
| A minor: output folder inside coder_materials accepted | Fixed | Guard right after argument parsing |
| B1/B2 run_all.sh ordering, literal 0-N | Fixed | Cluster stages print-only even with --run; --run needs --stage |
| B3 COLLAB overwritten in slurm | Fixed | `${COLLAB:-default}`; run_corpus exports it and guards its rm -rf |
| B4 25/30 need archived producer | No change | Planned step 24 |
| B5 corpus_with_topics not produced | Fold into step 24 | Six consumers repointed to data/windows/one_sentence/corpus_with_topics.parquet; output contract in 24's header |
| B6 .gitignore inline comments | Fixed | Exceptions removed; data/ never tracked (nothing under data/ was ever on GitHub) |
| B minor: merger writer on error | Fixed | try/finally closes the writer and deletes a partial output |

## Already verified
- Edited 15 produces an identical manifest and identical contents in all 15 workbooks compared with the pre-edit script on the same fake tree.
- The new test passes (about 30 seconds). Its two negative tests fail with the expected messages.
- 06_merge_windows merges 3 toy shards correctly; with a corrupt shard it exits nonzero and leaves no output file.
- run_all.sh: `--stage 2 --run` prints only; `--run` with no stage exits 1.
- All .py compile; all paths named in README, run_all.sh and slurm files resolve.

## Please check
- Does any change to 15 alter its random draws or assignment (it must not)? Is the coder_materials guard correct for symlinks, relative paths and a path that merely shares a prefix (e.g. coder_materials_old)?
- Is the test independent of 15's own logic, or does it re-derive anything the same (possibly wrong) way? Can it pass when 15 is wrong? Name a concrete mutation of 15 it would miss, if any.
- run_all.sh: can anything still execute a cluster command? Does `set -e` interact badly with the new `case` / `&&` lines?
- slurm: does `export COLLAB=$C` plus default sbatch environment propagation make every job use the same root? Is the rm -rf guard correct (quoting, trailing slashes)?
- Are the six repointed paths and the step-24 output contract consistent with the columns each consumer reads?
- Is any "keep as run" decision actually unsafe?

Report concrete bugs with file and line references first. List lower-priority suggestions separately. Do not propose new features or methods beyond what is needed to fix a bug.

## Diff (everything except the test)
```diff
diff --git a/.gitignore b/.gitignore
index c982a84..420e5d2 100644
--- a/.gitignore
+++ b/.gitignore
@@ -1,9 +1,8 @@
 # =============================================================================
-# Repository whitelist: track ONLY the analysis code and the sentence data.
+# Repository whitelist: track ONLY code, docs and small inputs. No data.
 # Everything else (audio, transformer models, raw transcripts, scratch files,
 # intermediate outputs, credentials) is ignored. This is a "deny-by-default"
-# .gitignore: ignore everything at the root, then re-include code/ and the
-# sentence/panel data under data/sc_results/.
+# .gitignore: ignore everything at the root, then re-include the folders below.
 # =============================================================================
 
 # 1) ignore everything at the repo root by default
@@ -11,7 +10,6 @@
 
 # 2) re-include the things we DO want to track
 !/code/
-!/data/
 !/tex/
 !/README.md
 !/requirements.txt
@@ -24,12 +22,9 @@
 !/.gitignore
 !/.gitattributes
 
-# 3) inside data/: keep only the sentence corpus + analysis-ready panels
-/data/*
-!/data/sc_results/
-/data/sc_results/*
-!/data/sc_results/opus_c0_corpus_labeled.parquet   # the labeled sentences
-!/data/sc_results/*.csv                             # show x month panels + result tables
+# 3) data/ is never tracked (it is not re-included above). Data live on Roar ($COLLAB); the
+#    replication deposit is decided separately. The old data/sc_results exceptions never worked
+#    because inline comments broke the patterns, so nothing under data/ was ever on GitHub.
 
 # 3b) inside tex/: keep the diagram source + compiled PDF, drop LaTeX build junk
 /tex/*
diff --git a/README.md b/README.md
index cc6ca52..b29ff34 100644
--- a/README.md
+++ b/README.md
@@ -64,7 +64,7 @@ exists; **re-run** = built and run on the earlier labels, must re-run once step
 | 12 | `12_build_disney_pool.py` | Disney placebo pool | done |
 | 13 | `13_assign_coders.py` | Original coder assignment (Oct 9) | done; superseded by 15 |
 | 14 | `14_assign_placebo.py` | Placebo assignment (Oct 9) | done; superseded by 15 |
-| 15 | `15_rebuild_reduced_design.py` | Reduced 8,000-sentence design; every sentence = Jared + 1 student | done (Nov 23); GPT audit pending |
+| 15 | `15_rebuild_reduced_design.py` | Reduced 8,000-sentence design; every sentence = Jared + 1 student. Test: `tests/test_15_rebuild_reduced_design.py` | done (Nov 23); audited Nov 23 |
 | 16 | `16_release_reduced_design.py` | One-time release of 15's files to coder Dropbox folders | done (Nov 30 schedule) |
 | 17 | `17_build_adjudication.py` | Blind A/B adjudication sheets from disagreements | planned |
 | 18 | `18_icr_report.py` | Krippendorff's α from raw codes, by target/stratum/pair | planned |
@@ -74,7 +74,7 @@ exists; **re-run** = built and run on the earlier labels, must re-run once step
 | 21 | `21_gate_infer.py` | Gate over full one-sentence corpus | planned |
 | 22 | `22_stance_train.py` | Train 4-class stance × 2 targets (twitter-roberta, seed 123) | planned |
 | 23 | `23_stance_infer.py` | Stance over gate-passing sentences | planned |
-| 24 | `24_merge_predictions.py` | Corpus-level labeled file for 25 | planned |
+| 24 | `24_merge_predictions.py` | Writes `data/windows/one_sentence/corpus_with_topics.parquet` (read by 25, 27, 28, 36, 41, 46) and the sentence-level label file for 25/36/46; output contract in the script header | planned |
 | **5_analysis** | | | |
 | 25 | `25_build_panels.py` | Show × month stance/volume panels + audience | re-run |
 | 26 | `26_main_h1h3.R` | Main H1/H2/H3 (FE, matched FE, TWFE, SCM) | re-run |
@@ -120,10 +120,20 @@ human coding, in Dropbox (`podcast_analysis/coder_materials`, `coder_review`). S
 `config/README.md`. Data-access plan for replication: TBD.
 
 ## Running
-`run_all.sh` lists the steps in order (`./run_all.sh --stage 5` runs one stage; planned
-steps are skipped). Steps 01–09 and 20–23 are Roar jobs (`sbatch code/slurm/...`). The R
-layer runs with `module load r` on Roar or locally. Seed 123 throughout.
+`run_all.sh` prints every step in order (dry run). `./run_all.sh --stage 5 --run` runs one
+local stage (5, 6 or 7). Cluster stages 1, 2 and 4 are always print-only. Submit those by hand
+in order and wait for each job, because `sbatch` returns before a job finishes. Planned steps
+are skipped. Every slurm file uses `$COLLAB` if it is set. The R layer runs with `module load r`
+on Roar or locally. Seed 123 throughout. Test of step 15:
+`python3 tests/test_15_rebuild_reduced_design.py` (about 30 seconds, fake data).
 
-Known gaps: many scripts still hard-code `/storage/...` paths (to be moved to `$COLLAB`);
-01/02 slurm logs point at `/scratch` from the 2025 collection run; environments are listed
-in `config/` but not pinned. PI: Jared Edgerton (PSU).
+Known gaps
+- Steps 25–49 cannot run until step 24 exists. The old `data/corpus_with_topics.parquet` is from
+  the pre-windowing corpus, and the step that built it was deleted in July (commit 989f0a9).
+  Step 25 skips its volume panel with a warning, rather than failing, if that file is missing.
+- Many analysis scripts still hard-code `/storage/...` paths (to be moved to `$COLLAB`).
+  `#SBATCH --output` log paths cannot use variables and stay hard-coded.
+- 01/02 slurm logs point at `/scratch` from the 2025 collection run.
+- Environments are listed in `config/` but not pinned.
+
+PI: Jared Edgerton (PSU).
diff --git a/code/2_corpus/06_merge_windows.py b/code/2_corpus/06_merge_windows.py
index 53bf6dd..72339f9 100644
--- a/code/2_corpus/06_merge_windows.py
+++ b/code/2_corpus/06_merge_windows.py
@@ -16,13 +16,20 @@ def main():
     Path(a.output).parent.mkdir(parents=True, exist_ok=True)
     writer = None
     total = 0
-    for sh in shards:
-        log.info('reading %s', sh)
-        t = pq.read_table(sh)
-        if writer is None:
-            writer = pq.ParquetWriter(a.output, t.schema)
-        writer.write_table(t)
-        total += t.num_rows
-    if writer: writer.close()
+    ok = False
+    try:
+        for sh in shards:
+            log.info('reading %s', sh)
+            t = pq.read_table(sh)
+            if writer is None:
+                writer = pq.ParquetWriter(a.output, t.schema)
+            writer.write_table(t)
+            total += t.num_rows
+        ok = True
+    finally:
+        if writer: writer.close()
+        if not ok and Path(a.output).exists():
+            Path(a.output).unlink()          # never leave a partial corpus.parquet behind
+            log.error('merge failed; removed partial %s', a.output)
     log.info('MERGE_DONE rows=%d -> %s', total, a.output)
 if __name__ == '__main__': main()
diff --git a/code/3_human_coding/15_rebuild_reduced_design.py b/code/3_human_coding/15_rebuild_reduced_design.py
index 2abf4ec..6371c3c 100644
--- a/code/3_human_coding/15_rebuild_reduced_design.py
+++ b/code/3_human_coding/15_rebuild_reduced_design.py
@@ -15,10 +15,26 @@
 #   - Jared Thanksgiving batches A (1,762 Week-1 rows coded once) and B (1,000 new
 #     union rows), built Nov 18.
 #   - The Oct 9 pair assignment: each new sentence goes to ONE of its two
-#     originally assigned students (load-balanced within stratum).
+#     originally assigned students. Strata are processed one at a time, but the
+#     greedy balance uses each student's running total across ALL strata, so totals
+#     are balanced (asserted within 3) while per-stratum counts can differ by a few
+#     percent. Step [5] logs the per-stratum and per-target counts.
+#
+# Known behavior, kept as run (audit Nov 23, 2026). Changing it would change the
+# files already released to coders.
+#   - "Coded" in Week 1 means stance_russia is filled. Five rows marked uncodable=1
+#     with a blank stance (Josh rc_0641, rc_3004; Pam hn_0805, rc_2362, hn_0173) were
+#     therefore treated as blanks. They went back to the same student and to Jared's
+#     batch C. Step 17 treats the Week-1 uncodable mark as that student's code.
+#   - A Week-1 row one student left blank but the other student coded (Emily
+#     hn_0013, rc_3195, coded by Pam) is NOT returned to the blank student. It is
+#     already Pam + Jared (batch A), and returning it would make three coders.
+#     "Every Week-1 blank goes back to its student" applies only to rows nobody coded.
 #
 # Usage: python3 15_rebuild_reduced_design.py <podcast_analysis_root> <out_dir>
-# Writes staged files to <out_dir>; nothing in coder_materials is modified.
+# Writes staged files to <out_dir>; nothing in coder_materials is modified, and an
+# <out_dir> inside coder_materials is refused.
+# Test: tests/test_15_rebuild_reduced_design.py
 ###############################################################################
 import sys, os
 import numpy as np, pandas as pd, openpyxl
@@ -50,6 +66,8 @@ PLAC_COLS = ["row_id", "target", "show", "date", "prev_sentence", "sentence", "n
 CODE_MAIN = ["stance_russia", "stance_ukraine", "historical", "uncodable", "confidence", "notes"]
 CODE_PLAC = ["stance", "uncodable", "confidence", "notes"]
 CM = os.path.join(ROOT, "coder_materials")
+_cm, _out = os.path.realpath(CM), os.path.realpath(OUT)
+assert _out != _cm and not _out.startswith(_cm + os.sep), f"refusing to write inside coder_materials: {OUT}"
 rng = np.random.default_rng(SEED)
 log = []
 def say(*a):
@@ -153,6 +171,10 @@ assert all(student_of[r] in cand_main[r] for r in new_main)
 assert all(student_of[r] in cand_plac[r] for r in new_plac)
 assert max(load.values()) - min(load.values()) <= 3 and max(pload.values()) - min(pload.values()) <= 3, (load, pload)
 say(f"[5] new main per student {load}; placebo per student {pload}")
+_by_grp = pd.DataFrame([(MB.loc[r, "stratum"], student_of[r]) for r in new_main] +
+                       [(PB.loc[r, "target"], student_of[r]) for r in new_plac], columns=["group", "student"])
+say("    per stratum / target (report only; balance is on totals):\n" +
+    pd.crosstab(_by_grp.group, _by_grp.student).to_string())
 
 # ---- 6. Jared batches C (main) and D (placebo) -------------------------------
 C_ids = [r for r in new_main if r not in B_ids]; C_ids = [C_ids[i] for i in rng.permutation(len(C_ids))]
diff --git a/code/3_human_coding/16_release_reduced_design.py b/code/3_human_coding/16_release_reduced_design.py
index c3a3be8..330021a 100644
--- a/code/3_human_coding/16_release_reduced_design.py
+++ b/code/3_human_coding/16_release_reduced_design.py
@@ -2,6 +2,12 @@
 # Moves superseded files to coder_materials/_superseded/old_schedule_nov30/ and
 # copies staged files from coder_review/_staging_nov30/ into place. Logs every action.
 # Usage: python3 16_release_reduced_design.py <podcast_analysis_root>
+# Audit note (Nov 23, 2026): already run, never to be re-run. Known limits, kept as run:
+#   (1) the "refuse if coded" check looks only at stance columns and exempts the Week-1 files
+#   in KEEP; (2) validation and moves are interleaved, so a mid-run failure would leave a partial
+#   release, and the log is written at the end. The audit confirmed this run was complete:
+#   all 23 copies match staging byte for byte, and every populated cell in the archived Emily
+#   submission matches the retained Week-1 file (no decisions lost).
 import sys, os, shutil, glob, datetime
 import pandas as pd
 R = sys.argv[1]; CM = f"{R}/coder_materials"; ST = f"{R}/coder_review/_staging_nov30"; SUP = f"{CM}/_superseded/old_schedule_nov30"
diff --git a/code/3_human_coding/17_build_adjudication.py b/code/3_human_coding/17_build_adjudication.py
index 8034fad..8bd6ae7 100644
--- a/code/3_human_coding/17_build_adjudication.py
+++ b/code/3_human_coding/17_build_adjudication.py
@@ -1,4 +1,9 @@
 """17_build_adjudication.py -- PLANNED, NOT YET IMPLEMENTED.
 Collect every coder disagreement into a blind A/B adjudication sheet for the PI (labels shown without coder identity).
+Rules already decided (Nov 23, 2026):
+  - A Week-1 row a student marked uncodable=1 with a blank stance IS that student's code (uncodable). Five such rows
+    (Josh rc_0641, rc_3004; Pam hn_0805, rc_2362, hn_0173) were also re-sent to the same student in week_02 by step 15.
+    Use the Week-1 mark and ignore the week_02 repeat for ICR and adjudication; do not tell the coders.
+  - Agreement (step 18) is computed from raw pre-adjudication codes.
 See README.md (pipeline table) for status."""
 raise SystemExit("17_build_adjudication.py is a planned step and has not been implemented yet.")
diff --git a/code/4_classify/24_merge_predictions.py b/code/4_classify/24_merge_predictions.py
index f7832bd..a5d692f 100644
--- a/code/4_classify/24_merge_predictions.py
+++ b/code/4_classify/24_merge_predictions.py
@@ -1,4 +1,13 @@
 """24_merge_predictions.py -- PLANNED, NOT YET IMPLEMENTED.
-Merge gate + stance predictions into one sentence-level label file consumed by 25_build_panels.py.
+Writes the two files the analysis layer reads (decided Nov 23, 2026, audit finding B5):
+  1. $COLLAB/data/windows/one_sentence/corpus_with_topics.parquet
+     Full one-sentence corpus (data/windows/one_sentence/corpus.parquet from step 06) joined to the step-07 topic
+     assignments. Required columns: show, date, sentence_id, sentence, topic.
+     Read by 25, 27, 28, 36, 41, 46. The old data/corpus_with_topics.parquet (pre-windowing corpus; its producer was
+     deleted in July, commit 989f0a9) must not be used.
+  2. The sentence-level label file that replaces data/sc_results/opus_c0_corpus_labeled.parquet (read by 25, 36, 46),
+     from gate (21) + stance (23) predictions. Required columns: show, date, sentence_id, topic, russia_label,
+     russia_p_pos, russia_p_neg, ukraine_label, ukraine_p_pos, ukraine_p_neg. 30_grid_h1h2.R also reads
+     data/sc_results/probs_4class.csv (4-class probabilities); write that too or repoint 30.
 See README.md (pipeline table) for status."""
 raise SystemExit("24_merge_predictions.py is a planned step and has not been implemented yet.")
diff --git a/code/5_analysis/25_build_panels.py b/code/5_analysis/25_build_panels.py
index 11cd3c1..51fc4de 100644
--- a/code/5_analysis/25_build_panels.py
+++ b/code/5_analysis/25_build_panels.py
@@ -145,7 +145,7 @@ except FileNotFoundError as e:
 # ---------- total-words volume (all-topic sentence counts) -> loso_volume.csv ----------
 # Time-varying volume control consumed by 13/23/26 (19_loso_panel rebuilds the same per-feed).
 try:
-    cw = pd.read_parquet(COLLAB + "/data/corpus_with_topics.parquet", columns=["show", "date", "topic"])
+    cw = pd.read_parquet(COLLAB + "/data/windows/one_sentence/corpus_with_topics.parquet", columns=["show", "date", "topic"])
     cw["date"] = pd.to_datetime(cw["date"], errors="coerce")
     cw = cw[(cw["date"] >= START) & (cw["date"] < TRUNC) & (cw["topic"] != -1)]
     cw["month"] = cw["date"].values.astype("datetime64[M]")
diff --git a/code/5_analysis/27_h4_tfidf_clean.py b/code/5_analysis/27_h4_tfidf_clean.py
index 0bf9870..db39a98 100644
--- a/code/5_analysis/27_h4_tfidf_clean.py
+++ b/code/5_analysis/27_h4_tfidf_clean.py
@@ -12,7 +12,7 @@ FEEDS = ["the_benny_show", "benny_johnson_arena", "the_rubin_report", "timcast_i
 JUNK = re.compile(r"promo|code|slash|com slash|download|bleacher|staying connected|"
                   r"know mean|mean know|miss moment|sponsor|discount|today miss", re.I)
 
-df = pd.read_parquet(CO + "/data/corpus_with_topics.parquet", columns=["show", "topic"])
+df = pd.read_parquet(CO + "/data/windows/one_sentence/corpus_with_topics.parquet", columns=["show", "topic"])
 df = df[(df.topic != -1) & (df["show"].isin(FEEDS) | True)]   # keep all shows for IDF
 ti = pd.read_csv(CO + "/data/topic_model/topic_info.csv")
 namecol = "Name" if "Name" in ti.columns else ti.columns[-1]
diff --git a/code/5_analysis/28_h4_topic_model.py b/code/5_analysis/28_h4_topic_model.py
index 2474d69..a3b2694 100644
--- a/code/5_analysis/28_h4_topic_model.py
+++ b/code/5_analysis/28_h4_topic_model.py
@@ -37,7 +37,7 @@ import numpy as np, pandas as pd
 
 SEED = 123; np.random.seed(SEED)
 COLLAB = "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC = COLLAB + "/data/sc_results"
-CORPUS = COLLAB + "/data/corpus_with_topics.parquet"
+CORPUS = COLLAB + "/data/windows/one_sentence/corpus_with_topics.parquet"
 PANEL = SC + "/baseline_panel.csv"
 TOPIC_INFO = COLLAB + "/data/topic_info.csv"
 START, TRUNC, FREEZE = pd.Timestamp("2018-01-01"), pd.Timestamp("2024-09-01"), pd.Timestamp("2023-10-01")
diff --git a/code/6_robustness/36_loso_panel.py b/code/6_robustness/36_loso_panel.py
index 0e22c81..8932f9a 100644
--- a/code/6_robustness/36_loso_panel.py
+++ b/code/6_robustness/36_loso_panel.py
@@ -51,7 +51,7 @@ def jsd(p, q):
     m = 0.5*(p+q)
     kl = lambda a,b: np.sum((a+EPS)*np.log2((a+EPS)/(b+EPS)))
     return 0.5*kl(p,m)+0.5*kl(q,m)
-cw = pd.read_parquet(CO + "/data/corpus_with_topics.parquet", columns=["show", "date", "topic"])
+cw = pd.read_parquet(CO + "/data/windows/one_sentence/corpus_with_topics.parquet", columns=["show", "date", "topic"])
 cw["date"] = pd.to_datetime(cw["date"], errors="coerce")
 cw = cw[(cw.date >= START) & (cw.date < TRUNC) & (cw.topic != -1)].copy()
 cw["month"] = cw["date"].values.astype("datetime64[M]")
diff --git a/code/6_robustness/41_h3_topic_dist.py b/code/6_robustness/41_h3_topic_dist.py
index 64fc16a..5dbe436 100644
--- a/code/6_robustness/41_h3_topic_dist.py
+++ b/code/6_robustness/41_h3_topic_dist.py
@@ -30,7 +30,7 @@ SEED = 123
 COLLAB = "/storage/group/LiberalArts/default/jfe4_collab/podcast"
 SC = COLLAB + "/data/sc_results"
 MODEL_DIR = COLLAB + "/data/topic_model/topic_model"   # BERTopic model is in the nested dir
-CORPUS = COLLAB + "/data/corpus_with_topics.parquet"
+CORPUS = COLLAB + "/data/windows/one_sentence/corpus_with_topics.parquet"
 PANEL = SC + "/baseline_panel.csv"
 RELEVANT = [78, 79]
 START, TRUNC = pd.Timestamp("2018-01-01"), pd.Timestamp("2024-09-01")
diff --git a/code/7_outputs/46_label_examples.py b/code/7_outputs/46_label_examples.py
index dcde93a..77ccacd 100644
--- a/code/7_outputs/46_label_examples.py
+++ b/code/7_outputs/46_label_examples.py
@@ -16,7 +16,7 @@ import pandas as pd, numpy as np, re
 import pyarrow.dataset as ds, pyarrow.compute as pc
 
 CO = "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC = CO + "/data/sc_results"
-CORPUS = CO + "/data/corpus_with_topics.parquet"
+CORPUS = CO + "/data/windows/one_sentence/corpus_with_topics.parquet"
 N_EX, MAXLEN, CAND = 4, 240, 60          # examples per cell; truncation; candidates to fetch per cell
 np.random.seed(123)
 
diff --git a/code/slurm/04_transcribe.sbatch b/code/slurm/04_transcribe.sbatch
index 7aa3aa4..476d180 100644
--- a/code/slurm/04_transcribe.sbatch
+++ b/code/slurm/04_transcribe.sbatch
@@ -13,7 +13,7 @@
 # venv_whisper = torch 2.4.1+cu118 (P100/V100/A100), openai-whisper 20250625.
 # Model + ffmpeg resolved from group storage so home dir stays clear.
 set -euo pipefail
-C=/storage/group/LiberalArts/default/jfe4_collab/podcast
+C=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}
 export XDG_CACHE_HOME=$C/.cache          # whisper.load_model('small') -> $C/.cache/whisper
 export PATH=$C/venv_whisper/bin:$PATH     # use the imageio-ffmpeg static binary symlink
 cd $C
diff --git a/code/slurm/05_build_sentence_docs.sbatch b/code/slurm/05_build_sentence_docs.sbatch
index 519e2e1..668d934 100644
--- a/code/slurm/05_build_sentence_docs.sbatch
+++ b/code/slurm/05_build_sentence_docs.sbatch
@@ -12,7 +12,7 @@
 # WINDOW={1,3,5} via env (default 1). Documents are within-episode, non-overlapping,
 # final chunk < W. Output: data/windows/{one,three,five}_sentence/corpus_shards/
 set -euo pipefail
-COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
+COLLAB=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}
 CODE=$COLLAB/tenet_media_repo/code
 : ${WINDOW:=1}
 : ${FILES_PER_SHARD:=5000}
diff --git a/code/slurm/06_merge_windows.sbatch b/code/slurm/06_merge_windows.sbatch
index b1a0875..8a2289b 100644
--- a/code/slurm/06_merge_windows.sbatch
+++ b/code/slurm/06_merge_windows.sbatch
@@ -8,7 +8,7 @@
 #SBATCH --account=open
 #SBATCH --partition=basic
 set -euo pipefail
-COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
+COLLAB=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}
 CODE=$COLLAB/tenet_media_repo/code
 : ${WINDOW:=1}
 case "$WINDOW" in 1) WDIR=one_sentence ;; 3) WDIR=three_sentence ;; 5) WDIR=five_sentence ;; *) exit 1 ;; esac
diff --git a/code/slurm/07_topic_model.sbatch b/code/slurm/07_topic_model.sbatch
index de6c837..3305302 100644
--- a/code/slurm/07_topic_model.sbatch
+++ b/code/slurm/07_topic_model.sbatch
@@ -10,7 +10,7 @@
 #SBATCH --partition=standard
 #SBATCH --account=jfe4_cr_default
 set -euo pipefail
-COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
+COLLAB=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}
 : ${CORPUS:=$COLLAB/data/corpus.parquet}
 : ${SAMPLE_SIZE:=500000}
 : ${OUTPUT_DIR:=$COLLAB/data/topic_model}
diff --git a/code/slurm/08_identify_topics.sbatch b/code/slurm/08_identify_topics.sbatch
index fbdde36..924696a 100644
--- a/code/slurm/08_identify_topics.sbatch
+++ b/code/slurm/08_identify_topics.sbatch
@@ -8,7 +8,7 @@
 #SBATCH --account=open
 #SBATCH --partition=basic
 set -euo pipefail
-COLLAB=/storage/group/LiberalArts/default/jfe4_collab/podcast
+COLLAB=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}
 CODE=$COLLAB/tenet_media_repo/code
 : ${WINDOW:=1}
 case "$WINDOW" in 1) WD=one_sentence;; 3) WD=three_sentence;; 5) WD=five_sentence;; *) exit 1;; esac
diff --git a/code/slurm/09_build_label_pools.sbatch b/code/slurm/09_build_label_pools.sbatch
index 4694b2a..9e3f42e 100644
--- a/code/slurm/09_build_label_pools.sbatch
+++ b/code/slurm/09_build_label_pools.sbatch
@@ -8,7 +8,7 @@
 #SBATCH --account=open
 #SBATCH --partition=basic
 set -euo pipefail
-C=/storage/group/LiberalArts/default/jfe4_collab/podcast
+C=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}
 W=${WD:-one_sentence}
 module load python/3.11.2
 source $C/venv_analysis/bin/activate
diff --git a/code/slurm/run_corpus_05_to_08.sh b/code/slurm/run_corpus_05_to_08.sh
index 68c4aa8..c195ebf 100755
--- a/code/slurm/run_corpus_05_to_08.sh
+++ b/code/slurm/run_corpus_05_to_08.sh
@@ -1,8 +1,10 @@
 #!/bin/bash
-# Full 1/3/5-sentence pipeline: build docs (array) -> merge -> BERTopic (06) -> identify Russia (07w), chained.
+# Full 1/3/5-sentence pipeline: 05 build docs (array) -> 06 merge -> 07 BERTopic -> 08 identify topics, chained with afterok.
+# Data root = $COLLAB if set (exported to every job), else the Roar default.
 # Rebuilds corpora from transcript_key (now includes the 9 new control shows).
 set -euo pipefail
-C=/storage/group/LiberalArts/default/jfe4_collab/podcast
+C=${COLLAB:-/storage/group/LiberalArts/default/jfe4_collab/podcast}
+export COLLAB=$C
 CODE=$C/tenet_media_repo/code
 ACC=jfe4_cr_default
 NFILES=$(find $C/transcript_key -name "*.txt" | wc -l)
@@ -11,7 +13,8 @@ echo "NFILES=$NFILES  array=0-$LAST"
 for W in 1 3 5; do
   case $W in 1) WD=one_sentence;; 3) WD=three_sentence;; 5) WD=five_sentence;; esac
   OUT=$C/data/windows/$WD
-  rm -rf $OUT/corpus_shards; mkdir -p $OUT/corpus_shards
+  case "$OUT" in "$C"/data/windows/*_sentence) ;; *) echo "refusing to delete shards outside $C/data/windows: $OUT"; exit 1;; esac
+  rm -rf "$OUT/corpus_shards"; mkdir -p "$OUT/corpus_shards"
   JB=$(WINDOW=$W sbatch --parsable --account=$ACC --array=0-$LAST $CODE/slurm/05_build_sentence_docs.sbatch)
   JM=$(WINDOW=$W sbatch --parsable --account=$ACC --dependency=afterok:$JB $CODE/slurm/06_merge_windows.sbatch)
   JT=$(CORPUS=$OUT/corpus.parquet OUTPUT_DIR=$OUT sbatch --parsable --dependency=afterok:$JM $CODE/slurm/07_topic_model.sbatch)
diff --git a/run_all.sh b/run_all.sh
index c97cd76..7904ef6 100755
--- a/run_all.sh
+++ b/run_all.sh
@@ -3,8 +3,12 @@
 #
 #   ./run_all.sh                 print every command (dry run, the default)
 #   ./run_all.sh --stage 5       print stage 5 only
-#   ./run_all.sh --stage 5 --run actually run stage 5
+#   ./run_all.sh --stage 5 --run actually run stage 5 (local stages 5-7 only)
 #
+# Cluster stages (1, 2, 4) are ALWAYS print-only, even with --run. sbatch returns as soon
+# as a job is queued, so running them back to back would start later steps on missing or
+# stale inputs. Submit them by hand, in order, waiting for each job (or use the dependency
+# chain inside code/slurm/run_corpus_05_to_08.sh). --run also requires an explicit --stage.
 # Planned steps (placeholders that raise an error) are skipped and reported.
 # Design-time steps 10-16 already ran and build the coder files. They are listed but never
 # re-run here, because re-running would overwrite the files coders are working in.
@@ -23,20 +27,22 @@ while [ $# -gt 0 ]; do
 done
 
 do_cmd () { if [ $RUN -eq 1 ]; then echo "+ $*"; eval "$@"; else echo "  $*"; fi; }
+cluster () { echo "  $*"; }                       # never executed; see header
 planned () { echo "  [skip] $1 -- planned, not yet implemented"; }
 want () { [ "$STAGE" = all ] || [ "$STAGE" = "$1" ]; }
+if [ $RUN -eq 1 ] && [ "$STAGE" = all ]; then echo "--run needs --stage 5, 6 or 7"; exit 1; fi
+case "$STAGE" in 1|2|4) [ $RUN -eq 1 ] && echo "(stage $STAGE is a cluster stage: printing only, nothing is run)";; esac
 
-if want 1; then echo "== 1_collect (Roar) =="
-  do_cmd sbatch code/slurm/01_pull_data.sbatch
-  do_cmd sbatch code/slurm/02_download_audio.sbatch
-  do_cmd python code/1_collect/03_create_key.py
-  echo "  # 04 is a job array, one episode per task; set --array to the rows of file_key.csv"
-  do_cmd sbatch --array=0-N code/slurm/04_transcribe.sbatch
+if want 1; then echo "== 1_collect (Roar; run each after the previous job finishes) =="
+  cluster sbatch code/slurm/01_pull_data.sbatch
+  cluster sbatch code/slurm/02_download_audio.sbatch
+  cluster python code/1_collect/03_create_key.py
+  cluster "sbatch --array=0-<rows in \$COLLAB/file_key.csv minus 1> code/slurm/04_transcribe.sbatch"
 fi
 
 if want 2; then echo "== 2_corpus (Roar) =="
-  do_cmd bash code/slurm/run_corpus_05_to_08.sh        # 05 build -> 06 merge -> 07 topics -> 08 identify, per window
-  do_cmd sbatch code/slurm/09_build_label_pools.sbatch
+  cluster bash code/slurm/run_corpus_05_to_08.sh       # chains 05 -> 06 -> 07 -> 08 per window with afterok dependencies
+  cluster sbatch code/slurm/09_build_label_pools.sbatch # after all 08 jobs finish
 fi
 
 if want 3; then echo "== 3_human_coding =="
```

## New test, in full: tests/test_15_rebuild_reduced_design.py
```python
# test_15_rebuild_reduced_design.py -- end-to-end test of
# code/3_human_coding/15_rebuild_reduced_design.py on a full-size FAKE tree.
#
#   python3 tests/test_15_rebuild_reduced_design.py [workdir]      (seed 123)
#
# 1. Build a fake coder_materials tree with the real structure (36 student files,
#    3 Week-1 done files, Jared batches A and B). Planted cases: Week-1 blanks, one
#    uncodable=1 row with a blank stance (the A1 case), and blanks another student coded.
# 2. Run 15 twice into two folders.
# 3. Check the outputs independently of 15's own asserts, reading only the files.
# 4. Negative tests: 15 must FAIL (a) when a Week-1 file's row order is corrupted and
#    (b) when the output folder is inside coder_materials.
# Exits nonzero on the first failed check.
import sys, os, shutil, subprocess, tempfile, hashlib, glob
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "code", "3_human_coding", "15_rebuild_reduced_design.py")
W = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="test15_")
R = os.path.join(W, "fake")
shutil.rmtree(W, ignore_errors=True); os.makedirs(R)
rng = np.random.default_rng(123)
print("workdir", W)

# ---- 1. fake tree -------------------------------------------------------------
S = ["Emily", "Josh", "Pam"]; PAIRS = [("Emily", "Josh"), ("Josh", "Pam"), ("Emily", "Pam")]
MAIN = ["week_01_due_2026-10-16.xlsx","week_02_due_2026-10-23.xlsx","week_03_due_2026-10-30.xlsx","week_04_due_2026-11-06.xlsx","week_05_due_2026-11-13.xlsx","week_06_due_2026-11-20.xlsx","week_07_due_2026-12-04.xlsx","week_08_due_2026-12-11.xlsx","week_09_due_2026-12-18.xlsx","week_10_due_2027-01-08.xlsx"]
PLAC = ["week_11_due_2027-01-15.xlsx","week_12_due_2027-01-22.xlsx"]
DONE = {"Josh": "Josh/week_01_due_2026-10-02-2.xlsx", "Emily": "Emily/week_01_SUBMITTED_by_Emily (1).xlsx", "Pam": "Pam/week_01_due_2026-10-02.xlsx"}
def dates(n, post):
    lo, hi = (pd.Timestamp("2018-01-01"), pd.Timestamp("2023-09-30")) if not post else (pd.Timestamp("2023-10-01"), pd.Timestamp("2024-08-31"))
    return [lo + (hi - lo) * float(u) for u in rng.random(n)]
rows = []
for pre, n, strat in [("rc", 4000, "union"), ("nr", 5000, "nonunion_random"), ("hn", 1000, "hard_negative")]:
    d = dates(n // 2, False) + dates(n - n // 2, True) if strat != "union" else dates(int(n * .78), False) + dates(n - int(n * .78), True)
    for i in range(n):
        rows.append(dict(row_id=f"{pre}_{i:04d}", stratum=strat, show="fake_show", date=d[i], prev_sentence="p", sentence=f"s {pre}{i}",
                         next_sentence="n", stance_russia=None, stance_ukraine=None, historical=None, uncodable=None, confidence=None,
                         notes=None, kw_russia=0, kw_ukraine=0, filename="f", sentence_id=i, uid=f"u_{pre}_{i}"))
Mb = pd.DataFrame(rows)
assign = {s: [] for s in S}
for strat, g in Mb.groupby("stratum"):
    ids = list(g.row_id); ids = [ids[i] for i in rng.permutation(len(ids))]
    for k, r in enumerate(ids):
        a, b = PAIRS[k % 3]; assign[a].append(r); assign[b].append(r)
prow = []
for t in ["big_tech", "china", "supreme_court", "disney"]:
    for i in range(500):
        prow.append(dict(row_id=f"{t}_{i:04d}", target=t, show="fake", date=dates(1, False)[0], prev_sentence="p", sentence=f"s {t}{i}",
                         next_sentence="n", stance=None, uncodable=None, confidence=None, notes=None, filename="f", sentence_id=i, uid=f"u_{t}_{i}@{t}"))
Pb = pd.DataFrame(prow); passign = {s: [] for s in S}
for t, g in Pb.groupby("target"):
    ids = list(g.row_id); ids = [ids[i] for i in rng.permutation(len(ids))]
    for k, r in enumerate(ids):
        a, b = PAIRS[k % 3]; passign[a].append(r); passign[b].append(r)
MI, PI = Mb.set_index("row_id"), Pb.set_index("row_id")
for s in S:
    os.makedirs(f"{R}/coder_materials/{s}", exist_ok=True)
    ids = [assign[s][i] for i in rng.permutation(len(assign[s]))]
    for f, ch in zip(MAIN, np.array_split(np.array(ids, dtype=object), 10)):
        x = MI.loc[list(ch)].reset_index(); x.insert(0, "coder", s[0])
        x.to_excel(f"{R}/coder_materials/{s}/{f}", sheet_name="main", index=False)
    ids = [passign[s][i] for i in rng.permutation(len(passign[s]))]
    for f, ch in zip(PLAC, np.array_split(np.array(ids, dtype=object), 2)):
        x = PI.loc[list(ch)].reset_index(); x.insert(0, "coder", s[0])
        x.to_excel(f"{R}/coder_materials/{s}/{f}", sheet_name="placebo", index=False)
BL = {"Josh": [27, 295], "Emily": list(range(433, 473)), "Pam": [143, 182, 326, 327, 328, 400, 401, 402, 403]}
UNCODABLE = ("Josh", 50)                     # A1 case: uncodable=1, stance blank
week1 = {}
for s, f in DONE.items():
    w = pd.read_excel(f"{R}/coder_materials/{s}/{MAIN[0]}", sheet_name="main")
    w["stance_russia"] = "unmentioned"; w["stance_ukraine"] = "unmentioned"
    w.loc[BL[s], ["stance_russia", "stance_ukraine"]] = None
    if s == UNCODABLE[0]:
        w.loc[UNCODABLE[1], ["stance_russia", "stance_ukraine"]] = None; w.loc[UNCODABLE[1], "uncodable"] = 1
    w.to_excel(f"{R}/coder_materials/{f}", sheet_name="main", index=False)
    week1[s] = w
coded = {}
for s, w in week1.items():
    for r in w.row_id[w.stance_russia.notna()]: coded.setdefault(r, set()).add(s)
once = sorted(r for r, v in coded.items() if len(v) == 1)
twice = sorted(r for r, v in coded.items() if len(v) == 2)
os.makedirs(f"{R}/coder_review/Jared", exist_ok=True)
MI.loc[once].reset_index().assign(coder="J").to_excel(f"{R}/coder_review/Jared/jared_TG_A_complete_week1_pairs.xlsx", sheet_name="main", index=False)
pool = sorted(r for r in Mb.row_id[Mb.stratum == "union"] if r not in coded)
B = list(rng.choice(pool, 1000, replace=False))
MI.loc[B].reset_index().assign(coder="J").to_excel(f"{R}/coder_review/Jared/jared_TG_B_union_new.xlsx", sheet_name="main", index=False)
print(f"[1] fake tree: coded once {len(once)}, twice {len(twice)}")

def tree_hash(root):
    h = hashlib.sha256()
    for p in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
        if os.path.isfile(p): h.update(p.encode()); h.update(open(p, "rb").read())
    return h.hexdigest()
cm_before = tree_hash(f"{R}/coder_materials")

# ---- 2. run 15 twice -----------------------------------------------------------
def run(out):
    return subprocess.run([sys.executable, SCRIPT, R, out], capture_output=True, text=True)
O1, O2 = os.path.join(W, "out1"), os.path.join(W, "out2")
for o in (O1, O2):
    p = run(o)
    assert p.returncode == 0, "15 failed on clean fake data:\n" + p.stdout[-2000:] + p.stderr[-3000:]
print("[2] 15 ran twice on clean fake data")

# ---- 3. independent checks ------------------------------------------------------
assert tree_hash(f"{R}/coder_materials") == cm_before, "coder_materials was modified"
man = pd.read_csv(f"{O1}/_admin/assignment_master_v2.csv")
assert man.equals(pd.read_csv(f"{O2}/_admin/assignment_master_v2.csv")), "manifest differs between runs"

files = {}                                   # path relative to out -> DataFrame
for p in sorted(glob.glob(f"{O1}/*/*.xlsx")):
    rel = os.path.relpath(p, O1)
    sheet = "placebo" if ("week_05" in rel or "_D_" in rel) else "main"
    files[rel] = pd.read_excel(p, sheet_name=sheet)
    other = pd.read_excel(os.path.join(O2, rel), sheet_name=sheet)
    assert files[rel].equals(other), f"{rel} differs between runs"
print("[3a] coder_materials untouched; two runs identical")

# who codes what, from files only: Week-1 coded rows + Jared A/B + every output file
coders = {}
for s, w in week1.items():
    for r in w.row_id[w.stance_russia.notna()]: coders.setdefault(r, []).append(s)
for r in once + [str(b) for b in B]: coders.setdefault(r, []).append("Jared")
for rel, df in files.items():
    who = rel.split(os.sep)[0]
    for r in df.row_id: coders.setdefault(r, []).append(who)
sel = set(man.row_id)
assert len(sel) == 8000, len(sel)
bad = {r: c for r, c in coders.items() if r in sel and (len(c) != 2 or len(set(c)) != 2)}
assert not bad, f"{len(bad)} selected rows without exactly 2 distinct coders, e.g. {list(bad.items())[:3]}"
assert not (set(coders) - sel), "a coded or assigned row is outside the 8,000 sample"
assert sum(1 for c in coders.values() if "Jared" not in c) == len(twice), "student-student rows != Week-1 twice-coded"
print("[3b] every one of 8,000 rows has exactly 2 distinct coders (from the files)")

st = man[man.block == "main"].grp.value_counts().to_dict()
assert st == {"union": 4000, "nonunion_random": 2000, "hard_negative": 1000}, st
nu = MI.loc[man.row_id[man.grp == "nonunion_random"]]
post = (pd.to_datetime(nu.date) >= pd.Timestamp("2023-10-01")).value_counts().to_dict()
assert post == {False: 1000, True: 1000}, post
assert (man[man.block == "placebo"].grp.value_counts() == 250).all()
for rel, df in files.items():
    cc = ["stance", "uncodable", "confidence", "notes"] if "stance" in df.columns else \
         ["stance_russia", "stance_ukraine", "historical", "uncodable", "confidence", "notes"]
    assert df[cc].isna().all().all(), f"code cells not blank in {rel}"
print("[3c] strata 4000/2000/1000, non-union 1000 pre / 1000 post, placebo 250 x 4, code cells blank")

# Week-1 blanks nobody coded go to the same student, first, in Week-1 order
for s, w in week1.items():
    blank = [r for r in w.row_id[w.stance_russia.isna()] if r not in coded]
    first = list(files[f"{s}/week_02_due_2026-12-04.xlsx"].row_id[:len(blank)])
    assert first == blank, f"{s}: Week-1 blanks are not first in week_02, in order"
    # blanks another student coded are NOT returned (would be 3 coders)
    stolen = [r for r in w.row_id[w.stance_russia.isna()] if r in coded]
    mine = set().union(*[set(df.row_id) for rel, df in files.items() if rel.startswith(s + os.sep)])
    assert not (set(stolen) & mine), f"{s}: a blank coded by another student was returned"
# A1 behavior pinned: uncodable-with-blank-stance row goes back to the student AND to Jared C
r_unc = week1[UNCODABLE[0]].row_id[UNCODABLE[1]]
assert r_unc in set(files["Josh/week_02_due_2026-12-04.xlsx"].row_id), "A1 row not returned to student"
assert man.set_index("row_id").loc[r_unc, "jared_batch"] == "C", "A1 row not in Jared batch C"
print("[3d] Week-1 blanks first and in order; blanks coded by others not returned; A1 behavior as documented")

# ---- 4. negative tests ----------------------------------------------------------
f = f"{R}/coder_materials/{DONE['Pam']}"
keep = open(f, "rb").read()
w = pd.read_excel(f, sheet_name="main"); w = w.iloc[[1, 0] + list(range(2, len(w)))]
w.to_excel(f, sheet_name="main", index=False)
p = run(os.path.join(W, "out_neg_a"))
open(f, "wb").write(keep)
assert p.returncode != 0 and "rows/order differ" in p.stderr, "negative test (a) did not fail as expected:\n" + p.stderr[-1500:]
p = run(f"{R}/coder_materials/_staging_test")
assert p.returncode != 0 and "refusing to write inside coder_materials" in p.stderr, "negative test (b) did not fail as expected:\n" + p.stderr[-1500:]
assert not os.path.exists(f"{R}/coder_materials/_staging_test"), "negative test (b) wrote files"
print("[4] negative tests fail for the right reason: corrupted Week-1 order; output inside coder_materials")
print("ALL TESTS PASSED")
```
