###############################################################################
# carryover_old_partial.py -- ONE-TIME admin step after 16 (not part of the re-runnable pipeline).
# A student who kept coding an OLD (Oct 9 schedule) week_02 file on their own computer saves it as
#   coder_materials/<student>/week_02_OLD_partial.xlsx
# This script copies the codes for rows STILL ASSIGNED to that student into the student's new
# week_02/03/04 files, so they do not recode them. Decided Nov 23, 2026 (Josh).
#
#   python3 carryover_old_partial.py <podcast_analysis_root> <student>            dry run (writes nothing)
#   python3 carryover_old_partial.py <podcast_analysis_root> <student> --apply    writes
#
# Rules
#   - The partial file must be the student's old week_02: every row_id and sentence must match the
#     superseded copy in coder_materials/_superseded/old_schedule_nov30/<student>/.
#   - Coded row = a stance filled or uncodable = 1. Stance values must be valid, or nothing is written.
#   - Carried rows: coded, and assigned to this student in assignment_master_v2.csv. Their code columns
#     (stance_russia, stance_ukraine, historical, uncodable, confidence, notes) are copied into the row in
#     the new file. notes starts with "carried from old week_02".
#   - Refuses to write if ANY code cell in the student's new week_02/03/04 files is already filled (the
#     student has started), so a carry-over can never overwrite new work. Backs up the files first.
#   - Rows the v2.6 codebook changes may affect are flagged in notes for the student to recheck:
#       "RECHECK v2.6 collusion": the sentence has collusion / Russiagate / hoax / investigation / dossier terms
#       "RECHECK v2.6 Rule A": a target coded other than unmentioned while the sentence has no keyword for it
#   - Coded rows now assigned to another student (+ Jared) are NOT copied anywhere; step 17 reads the
#     partial file and uses them only as extra student-student agreement data. Rows outside the 8,000
#     sample are ignored.
# Writes coder_review/_admin/carryover_<student>_log.txt and backups in coder_review/_admin/backups/.
###############################################################################
import sys, os, re, shutil, hashlib, datetime
import numpy as np, pandas as pd, openpyxl

ROOT, STUDENT = sys.argv[1], sys.argv[2]
APPLY = "--apply" in sys.argv[3:]
assert STUDENT in ("Emily", "Josh", "Pam"), STUDENT
CM = os.path.join(ROOT, "coder_materials")
PART = os.path.join(CM, STUDENT, "week_02_OLD_partial.xlsx")
OLD = os.path.join(CM, "_superseded", "old_schedule_nov30", STUDENT, "week_02_due_2026-10-23.xlsx")
NEW = [os.path.join(CM, STUDENT, f) for f in
       ["week_02_due_2026-12-04.xlsx", "week_03_due_2026-12-11.xlsx", "week_04_due_2026-12-18.xlsx"]]
MASTER = os.path.join(ROOT, "coder_review", "_admin", "assignment_master_v2.csv")
LOG = os.path.join(ROOT, "coder_review", "_admin", f"carryover_{STUDENT}_log.txt")
CODE_COLS = ["stance_russia", "stance_ukraine", "historical", "uncodable", "confidence", "notes"]
STANCES = {"positive", "neutral", "negative", "unmentioned"}
COLLUSION = re.compile(r"collu|russia\s*gate|hoax|investigation|dossier|steele|mueller|interfer", re.I)
log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.append(s)
def blank(v):
    return v is None or (isinstance(v, float) and np.isnan(v)) or (isinstance(v, str) and not v.strip())
def norm(v):
    return None if blank(v) else str(v).strip().lower()
def is_one(v):
    return str(v).strip() in ("1", "1.0", "True", "true")
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

# ---- 1. inputs ----------------------------------------------------------------------
for p in [PART, OLD, MASTER] + NEW:
    assert os.path.exists(p), f"missing {p}"
xl = pd.ExcelFile(PART)
P = pd.read_excel(PART, sheet_name="main" if "main" in xl.sheet_names else xl.sheet_names[0])
O = pd.read_excel(OLD, sheet_name="main").set_index("row_id")
M = pd.read_csv(MASTER).set_index("row_id")
assert set(CODE_COLS) <= set(P.columns), f"partial file lacks code columns {set(CODE_COLS) - set(P.columns)}"
assert P.row_id.is_unique, "duplicate row_id in partial file"
alien = set(P.row_id) - set(O.index)
assert not alien, f"{len(alien)} rows in the partial file are not in the old week_02, e.g. {sorted(alien)[:3]}"
mism = [r for r, s in zip(P.row_id, P.sentence) if str(s) != str(O.at[r, "sentence"])]
assert not mism, f"{len(mism)} sentences differ from the old week_02, e.g. {mism[:3]}"
say(f"[1] {STUDENT}: partial file {len(P)} rows, all from the old week_02 with matching sentences")

# ---- 2. coded rows and validation -------------------------------------------------------
P["is_coded"] = [(norm(a) is not None or norm(b) is not None or is_one(u))
                 for a, b, u in zip(P.stance_russia, P.stance_ukraine, P.uncodable)]
C = P[P.is_coded].copy()
bad = [(r, c, v) for r, a, b in zip(C.row_id, C.stance_russia, C.stance_ukraine)
       for c, v in (("stance_russia", norm(a)), ("stance_ukraine", norm(b))) if v is not None and v not in STANCES]
assert not bad, f"{len(bad)} invalid stance values, e.g. {bad[:5]}; fix the partial file first"
def klass(r):
    if r not in M.index: return "out_of_sample"
    return "carry" if STUDENT in (M.at[r, "coder1"], M.at[r, "coder2"]) else "extra"
C["klass"] = C.row_id.map(klass)
say(f"[2] coded rows {len(C)}: {C.klass.value_counts().to_dict()}")

# ---- 3. locate carried rows in the new files; refuse if the student has started ------------
loc = {}
for p in NEW:
    d = pd.read_excel(p, sheet_name="main")
    started = int(d[[c for c in CODE_COLS if c != "notes"]].notna().any(axis=1).sum() + d["notes"].notna().sum())
    assert started == 0, f"{os.path.basename(p)} already has {started} filled rows; the student has started. Nothing written."
    for i, r in enumerate(d.row_id): loc[r] = (p, i + 2)          # +2: header row, 1-based
carry = C[C.klass == "carry"]
missing = [r for r in carry.row_id if r not in loc]
assert not missing, f"{len(missing)} carried rows are not in the student's new files, e.g. {missing[:3]}"

# ---- 4. recheck flags ------------------------------------------------------------------------
def flags(t):
    f = []
    if COLLUSION.search(str(t.sentence)): f.append("RECHECK v2.6 collusion")
    for tgt, kw in (("russia", "kw_russia"), ("ukraine", "kw_ukraine")):
        v = norm(getattr(t, f"stance_{tgt}"))
        if v not in (None, "unmentioned") and str(getattr(t, kw, 0)).strip() in ("0", "0.0", "False"):
            f.append(f"RECHECK v2.6 Rule A ({tgt})");
    return f
plan = []
for t in carry.itertuples(index=False):
    fl = flags(t)
    note = "; ".join(["carried from old week_02"] + fl + ([str(t.notes).strip()] if not blank(t.notes) else []))
    vals = {c: (None if blank(getattr(t, c)) else getattr(t, c)) for c in CODE_COLS if c != "notes"}
    for c in ("stance_russia", "stance_ukraine", "confidence"):
        if vals[c] is not None: vals[c] = str(vals[c]).strip().lower()
    vals["notes"] = note
    plan.append((t.row_id, loc[t.row_id][0], loc[t.row_id][1], vals, fl))
nflag = sum(1 for x in plan if x[4])
by_file = pd.Series([os.path.basename(x[1]) for x in plan]).value_counts().to_dict() if plan else {}
say(f"[4] to carry: {len(plan)} rows {by_file}; flagged for v2.6 recheck: {nflag}")

if not APPLY:
    say("DRY RUN: nothing written. Re-run with --apply to write.")
    sys.exit(0)

# ---- 5. back up, write, verify -----------------------------------------------------------------
stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
bdir = os.path.join(ROOT, "coder_review", "_admin", "backups", f"{STUDENT}_pre_carryover_{stamp}")
os.makedirs(bdir)
before = {}
for p in NEW:
    shutil.copy2(p, bdir); before[p] = pd.read_excel(p, sheet_name="main")
say(f"[5] backups: {os.path.relpath(bdir, ROOT)}")
for p in NEW:
    mine = [x for x in plan if x[1] == p]
    if not mine: continue
    wb = openpyxl.load_workbook(p); ws = wb["main"]
    hdr = [c.value for c in ws[1]]; col = {c: hdr.index(c) + 1 for c in CODE_COLS}
    for r, _, xrow, vals, _ in mine:
        assert ws.cell(row=xrow, column=hdr.index("row_id") + 1).value == r, (p, xrow, r)
        for c, v in vals.items():
            ws.cell(row=xrow, column=col[c]).value = v
    wb.save(p)
for p in NEW:
    after = pd.read_excel(p, sheet_name="main"); b = before[p]
    keep = [c for c in b.columns if c not in CODE_COLS]
    assert after[keep].equals(b[keep]), f"non-code columns changed in {p}"
    mine = {x[0]: x[3] for x in plan if x[1] == p}
    for i, r in enumerate(after.row_id):
        if r in mine:
            assert norm(after.at[i, "stance_russia"]) == norm(mine[r]["stance_russia"]) and \
                   norm(after.at[i, "stance_ukraine"]) == norm(mine[r]["stance_ukraine"]) and \
                   str(after.at[i, "notes"]).startswith("carried from old week_02"), (p, r)
        else:
            assert after.loc[i, CODE_COLS].isna().all(), f"untouched row {r} changed in {p}"
say(f"[5] written and verified: {len(plan)} rows carried; every other cell unchanged")
for r, p, _, _, fl in plan:
    if fl: say(f"    recheck {r} ({os.path.basename(p)}): {', '.join(fl)}")
open(LOG, "w").write("\n".join(log) + "\n")
