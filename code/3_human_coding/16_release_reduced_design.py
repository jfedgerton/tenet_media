# 16_release_reduced_design.py -- release the Nov 23 reduced-design files to coders (run once).
# Moves superseded files to coder_materials/_superseded/old_schedule_nov30/ and
# copies staged files from coder_review/_staging_nov30/ into place. Logs every action.
# Usage: python3 16_release_reduced_design.py <podcast_analysis_root>
# Audit note (Nov 23, 2026): already run, never to be re-run. Known limits, kept as run:
#   (1) the "refuse if coded" check looks only at stance columns and exempts the Week-1 files
#   in KEEP; (2) validation and moves are interleaved, so a mid-run failure would leave a partial
#   release, and the log is written at the end. The audit confirmed this run was complete:
#   all 23 copies match staging byte for byte, and every populated cell in the archived Emily
#   submission matches the retained Week-1 file (no decisions lost).
import sys, os, shutil, glob, datetime
import pandas as pd
R = sys.argv[1]; CM = f"{R}/coder_materials"; ST = f"{R}/coder_review/_staging_nov30"; SUP = f"{CM}/_superseded/old_schedule_nov30"
STUDENTS = ["Emily", "Josh", "Pam"]
KEEP = {"Emily": ["week_01_SUBMITTED_by_Emily (1).xlsx"], "Josh": ["week_01_due_2026-10-02-2.xlsx"], "Pam": ["week_01_due_2026-10-02.xlsx"]}
log = []
def mv(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True); assert not os.path.exists(dst), f"exists: {dst}"
    shutil.move(src, dst); log.append(f"MOVE {os.path.relpath(src, R)} -> {os.path.relpath(dst, R)}")
def cp(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True); assert not os.path.exists(dst), f"exists: {dst}"
    shutil.copy2(src, dst); log.append(f"COPY {os.path.relpath(src, R)} -> {os.path.relpath(dst, R)}")
# 1. students: move every xlsx except the Week-1 done file; refuse if any moved file has codes
for s in STUDENTS:
    for f in sorted(glob.glob(f"{CM}/{s}/*.xlsx")):
        name = os.path.basename(f)
        if name in KEEP[s]: continue
        x = pd.ExcelFile(f); d = pd.read_excel(f, sheet_name=x.sheet_names[0])
        col = "stance_russia" if "stance_russia" in d.columns else "stance"
        n = int(d[col].notna().sum())
        assert n == 0 or name == "week_01_SUBMITTED_by_Emily.xlsx", f"{s}/{name} has {n} codes; not moving"
        mv(f, f"{SUP}/{s}/{name}")
    for f in sorted(glob.glob(f"{ST}/{s}/*.xlsx")):
        cp(f, f"{CM}/{s}/{os.path.basename(f)}")
    left = sorted(os.path.basename(p) for p in glob.glob(f"{CM}/{s}/*.xlsx"))
    assert left == sorted(KEEP[s] + [os.path.basename(p) for p in glob.glob(f"{ST}/{s}/*.xlsx")]), (s, left)
# 2. codebooks + README in the shared root
for name in ["stance_codebook_v2.5.md", "stance_codebook_v2.5.docx", "stance_codebook_v2.5.pdf",
             "stance_codebook_placebo_entities_v1.2.md", "README_FOR_CODERS.md"]:
    mv(f"{CM}/{name}", f"{SUP}/{name}")
for name in ["stance_codebook_v2.6.md", "stance_codebook_v2.6.docx", "stance_codebook_v2.6.pdf",
             "stance_codebook_placebo_entities_v1.3.md", "stance_codebook_placebo_entities_v1.3.docx",
             "stance_codebook_placebo_entities_v1.3.pdf"]:
    cp(f"{ST}/codebook/{name}", f"{CM}/{name}")
cp(f"{ST}/README_FOR_CODERS.md", f"{CM}/README_FOR_CODERS.md")
# 3. Jared's winter-break batches + admin master (not visible to coders)
for name in ["jared_WB_C1_main.xlsx", "jared_WB_C2_main.xlsx", "jared_WB_D_placebo.xlsx"]:
    cp(f"{ST}/Jared/{name}", f"{R}/coder_review/Jared/{name}")
cp(f"{ST}/_admin/assignment_master_v2.csv", f"{R}/coder_review/_admin/assignment_master_v2.csv")
stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
open(f"{R}/coder_review/_admin/release_log_nov30.txt", "w").write(f"release run {stamp}\n" + "\n".join(log) + "\n")
print("\n".join(log)); print(f"\n{len(log)} actions OK")
