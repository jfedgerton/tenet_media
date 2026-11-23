###############################################################################
# 15_rebuild_reduced_design.py -- rebuild the Tenet stance-coding assignments
# for the reduced design adopted Nov 23, 2026 (PI: Jared Edgerton, PSU). Seed 123.
#
# Design
#   Sample (8,000 sentences): union 4,000 (all) | hard negatives 1,000 (all) |
#   non-union random 2,000 (1,000 pre / 1,000 post 2023-10-01; all already-coded
#   rows kept) | placebo 1,000 (250 per target).
#   Every sentence is double-coded: Jared + one student. The 94 Week-1 sentences
#   already coded by two students stay student-student (Jared does not code them).
#   Jared adjudicates all disagreements; Jon Green audits a random sample.
#
# Reuses what exists
#   - Week-1 student codes (untouched).
#   - Jared Thanksgiving batches A (1,762 Week-1 rows coded once) and B (1,000 new
#     union rows), built Nov 18.
#   - The Oct 9 pair assignment: each new sentence goes to ONE of its two
#     originally assigned students. Strata are processed one at a time, but the
#     greedy balance uses each student's running total across ALL strata, so totals
#     are balanced (asserted within 3) while per-stratum counts can differ by a few
#     percent. Step [5] logs the per-stratum and per-target counts.
#
# Known behavior, kept as run (audit Nov 23, 2026). Changing it would change the
# files already released to coders.
#   - "Coded" in Week 1 means stance_russia is filled. Five rows marked uncodable=1
#     with a blank stance (Josh rc_0641, rc_3004; Pam hn_0805, rc_2362, hn_0173) were
#     therefore treated as blanks. They went back to the same student and to Jared's
#     batch C. Step 17 treats the Week-1 uncodable mark as that student's code.
#   - A Week-1 row one student left blank but the other student coded (Emily
#     hn_0013, rc_3195, coded by Pam) is NOT returned to the blank student. It is
#     already Pam + Jared (batch A), and returning it would make three coders.
#     "Every Week-1 blank goes back to its student" applies only to rows nobody coded.
#
# Usage: python3 15_rebuild_reduced_design.py <podcast_analysis_root> <out_dir>
# Writes staged files to <out_dir>; nothing in coder_materials is modified, and an
# <out_dir> inside coder_materials is refused.
# Test: tests/test_15_rebuild_reduced_design.py
###############################################################################
import sys, os
import numpy as np, pandas as pd, openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

ROOT, OUT = sys.argv[1], sys.argv[2]
SEED = 123
CUT = pd.Timestamp("2023-10-01")
STUDENTS = ["Emily", "Josh", "Pam"]
LETTER = {"Emily": "A", "Josh": "B", "Pam": "C"}
ORIG_MAIN = ["week_01_due_2026-10-16.xlsx", "week_02_due_2026-10-23.xlsx", "week_03_due_2026-10-30.xlsx",
             "week_04_due_2026-11-06.xlsx", "week_05_due_2026-11-13.xlsx", "week_06_due_2026-11-20.xlsx",
             "week_07_due_2026-12-04.xlsx", "week_08_due_2026-12-11.xlsx", "week_09_due_2026-12-18.xlsx",
             "week_10_due_2027-01-08.xlsx"]
ORIG_PLAC = ["week_11_due_2027-01-15.xlsx", "week_12_due_2027-01-22.xlsx"]
WEEK1_DONE = {"Josh": "Josh/week_01_due_2026-10-02-2.xlsx",
              "Emily": "Emily/week_01_SUBMITTED_by_Emily (1).xlsx",
              "Pam": "Pam/week_01_due_2026-10-02.xlsx"}
JARED_A = "coder_review/Jared/jared_TG_A_complete_week1_pairs.xlsx"
JARED_B = "coder_review/Jared/jared_TG_B_union_new.xlsx"
NEW_MAIN_WEEKS = [("week_02", "2026-12-04"), ("week_03", "2026-12-11"), ("week_04", "2026-12-18")]
NEW_PLAC_WEEK = ("week_05", "2027-01-08")
MAIN_COLS = ["row_id", "stratum", "show", "date", "prev_sentence", "sentence", "next_sentence",
             "stance_russia", "stance_ukraine", "historical", "uncodable", "confidence", "notes",
             "kw_russia", "kw_ukraine", "filename", "sentence_id", "uid"]
PLAC_COLS = ["row_id", "target", "show", "date", "prev_sentence", "sentence", "next_sentence",
             "stance", "uncodable", "confidence", "notes", "filename", "sentence_id", "uid"]
CODE_MAIN = ["stance_russia", "stance_ukraine", "historical", "uncodable", "confidence", "notes"]
CODE_PLAC = ["stance", "uncodable", "confidence", "notes"]
CM = os.path.join(ROOT, "coder_materials")
_cm, _out = os.path.realpath(CM), os.path.realpath(OUT)
assert _out != _cm and not _out.startswith(_cm + os.sep), f"refusing to write inside coder_materials: {OUT}"
rng = np.random.default_rng(SEED)
log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.append(s)

def orig_path(student, fname):
    p = os.path.join(CM, student, fname)
    if os.path.exists(p): return p
    p2 = os.path.join(CM, "_superseded", "old_schedule_nov30", student, fname)
    assert os.path.exists(p2), f"missing original file {student}/{fname}"
    return p2

# ---- 1. original Oct 9 assignment -------------------------------------------
M, P = [], []
for s in STUDENTS:
    for f in ORIG_MAIN:
        x = pd.read_excel(orig_path(s, f), sheet_name="main"); x["student"] = s; x["orig_file"] = f; M.append(x)
    for f in ORIG_PLAC:
        x = pd.read_excel(orig_path(s, f), sheet_name="placebo"); x["student"] = s; x["orig_file"] = f; P.append(x)
M = pd.concat(M, ignore_index=True); P = pd.concat(P, ignore_index=True)
assert len(M) == 20000 and M.row_id.nunique() == 10000, (len(M), M.row_id.nunique())
assert (M.groupby("row_id").student.nunique() == 2).all(), "main row not assigned to exactly 2 students"
assert len(P) == 4000 and P.row_id.nunique() == 2000, (len(P), P.row_id.nunique())
assert (P.groupby("row_id").student.nunique() == 2).all(), "placebo row not assigned to exactly 2 students"
cand_main = M.groupby("row_id").student.apply(lambda v: sorted(set(v))).to_dict()
cand_plac = P.groupby("row_id").student.apply(lambda v: sorted(set(v))).to_dict()
MB = M.drop_duplicates("row_id").set_index("row_id")
PB = P.drop_duplicates("row_id").set_index("row_id")
say("[1] original assignment OK: main 10,000 x2, placebo 2,000 x2")

# ---- 2. Week-1 codes ---------------------------------------------------------
coded_by = {}            # row_id -> set of students with a code
week1_blank = {}         # row_id -> student whose Week-1 row is blank
for s, f in WEEK1_DONE.items():
    d = pd.read_excel(os.path.join(CM, f), sheet_name="main")
    a = M[(M.student == s) & (M.orig_file == ORIG_MAIN[0])]
    assert list(d.row_id) == list(a.row_id), f"{s} Week-1 file rows/order differ from assignment"
    for rid, val in zip(d.row_id, d.stance_russia):
        if pd.notna(val): coded_by.setdefault(rid, set()).add(s)
        else: week1_blank[rid] = s
once = {r for r, v in coded_by.items() if len(v) == 1}
twice = {r for r, v in coded_by.items() if len(v) == 2}
say(f"[2] Week-1: coded once {len(once)}, twice {len(twice)}, blank rows {len(week1_blank)}")
assert len(once) + len(twice) == len(coded_by)

# ---- 3. Jared batches A and B -----------------------------------------------
JA = pd.read_excel(os.path.join(ROOT, JARED_A), sheet_name="main")
JB = pd.read_excel(os.path.join(ROOT, JARED_B), sheet_name="main")
A_ids, B_ids = set(JA.row_id), set(JB.row_id)
assert A_ids == once, "Batch A must equal the Week-1 coded-once set"
assert len(B_ids) == 1000 and (MB.loc[list(B_ids), "stratum"] == "union").all()
assert not (B_ids & set(coded_by)), "Batch B overlaps coded rows"
say(f"[3] Jared batches OK: A {len(A_ids)}, B {len(B_ids)}")

# ---- 4. reduced sample -------------------------------------------------------
sel_union = set(MB.index[MB.stratum == "union"])
sel_hard = set(MB.index[MB.stratum == "hard_negative"])
nu = MB[MB.stratum == "nonunion_random"].copy()
nu["post"] = pd.to_datetime(nu.date) >= CUT
keep_nu = set(nu.index) & (set(coded_by) | set(week1_blank))
sel_nu = set(keep_nu)
for half in (False, True):
    have = [r for r in keep_nu if bool(nu.loc[r, "post"]) == half]
    assert len(have) <= 1000, f"already-coded non-union {half} exceeds 1,000"
    pool = sorted(r for r in nu.index[nu.post == half] if r not in keep_nu)
    sel_nu |= set(rng.choice(pool, 1000 - len(have), replace=False))
assert len(sel_union) == 4000 and len(sel_hard) == 1000 and len(sel_nu) == 2000
assert (nu.loc[list(sel_nu), "post"].value_counts() == 1000).all()
sel_plac = set()
for tgt in sorted(PB.target.unique()):
    pool = sorted(PB.index[PB.target == tgt])
    assert len(pool) == 500, (tgt, len(pool))
    sel_plac |= set(rng.choice(pool, 250, replace=False))
assert len(sel_plac) == 1000
sel_main = sel_union | sel_hard | sel_nu
assert set(coded_by) <= sel_main and set(week1_blank) <= sel_main and B_ids <= sel_main
say(f"[4] sample: union 4000, hard 1000, non-union 2000 (1000/1000), placebo 1000 (250 x 4)")

# ---- 5. status + student assignment for new sentences -----------------------
new_main = sorted(r for r in sel_main if r not in coded_by)
new_plac = sorted(sel_plac)
student_of = {}
load = {s: 0 for s in STUDENTS}
for r in new_main:                                   # forced: Week-1 blanks stay with their coder
    if r in week1_blank:
        s = week1_blank[r]; assert s in cand_main[r]; student_of[r] = s; load[s] += 1
for strat in ["union", "hard_negative", "nonunion_random"]:
    rows = [r for r in new_main if r not in student_of and MB.loc[r, "stratum"] == strat]
    rows = [rows[i] for i in rng.permutation(len(rows))]
    for r in rows:
        c = cand_main[r]; s = c[0] if load[c[0]] <= load[c[1]] else c[1]
        student_of[r] = s; load[s] += 1
pload = {s: 0 for s in STUDENTS}
for tgt in sorted(PB.target.unique()):
    rows = [r for r in new_plac if PB.loc[r, "target"] == tgt]
    rows = [rows[i] for i in rng.permutation(len(rows))]
    for r in rows:
        c = cand_plac[r]; s = c[0] if pload[c[0]] <= pload[c[1]] else c[1]
        student_of[r] = s; pload[s] += 1
assert all(student_of[r] in cand_main[r] for r in new_main)
assert all(student_of[r] in cand_plac[r] for r in new_plac)
assert max(load.values()) - min(load.values()) <= 3 and max(pload.values()) - min(pload.values()) <= 3, (load, pload)
say(f"[5] new main per student {load}; placebo per student {pload}")
_by_grp = pd.DataFrame([(MB.loc[r, "stratum"], student_of[r]) for r in new_main] +
                       [(PB.loc[r, "target"], student_of[r]) for r in new_plac], columns=["group", "student"])
say("    per stratum / target (report only; balance is on totals):\n" +
    pd.crosstab(_by_grp.group, _by_grp.student).to_string())

# ---- 6. Jared batches C (main) and D (placebo) -------------------------------
C_ids = [r for r in new_main if r not in B_ids]; C_ids = [C_ids[i] for i in rng.permutation(len(C_ids))]
D_ids = [new_plac[i] for i in rng.permutation(len(new_plac))]
jared_batch = {**{r: "A" for r in A_ids}, **{r: "B" for r in B_ids}, **{r: "C" for r in C_ids}, **{r: "D" for r in D_ids}}

# ---- 7. coverage check: every selected sentence has exactly 2 coders ---------
rows = []
for r in sorted(sel_main) + sorted(sel_plac):
    blk = "placebo" if r in sel_plac else "main"
    done = sorted(coded_by.get(r, set()))
    coders = done + ([student_of[r]] if r in student_of else []) + (["Jared"] if r in jared_batch else [])
    assert len(coders) == 2 and len(set(coders)) == 2, (r, coders)
    status = "SS_done" if len(done) == 2 else ("SJ_week1" if len(done) == 1 else "SJ_new")
    rows.append(dict(row_id=r, block=blk,
                     grp=(PB.loc[r, "target"] if blk == "placebo" else MB.loc[r, "stratum"]),
                     uid=(PB.loc[r, "uid"] if blk == "placebo" else MB.loc[r, "uid"]),
                     status=status, coder1=coders[0], coder2=coders[1],
                     student_new=student_of.get(r, ""), jared_batch=jared_batch.get(r, "")))
MAN = pd.DataFrame(rows)
assert len(MAN) == 8000 and MAN.uid.is_unique
assert (MAN.status == "SS_done").sum() == len(twice) and (MAN.jared_batch != "").sum() == 8000 - len(twice)
say("[7] coverage OK:", MAN.groupby(["block", "status"]).size().to_dict())
say("    Jared total", int((MAN.jared_batch != "").sum()), MAN.jared_batch.value_counts().to_dict())

# ---- 8. write workbooks -------------------------------------------------------
def write(df, cols, code_cols, sheet, path, coder, info):
    df = df[cols].copy()
    for c in code_cols: df[c] = None
    df.insert(0, "coder", coder)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = sheet
    ws.append(list(df.columns))
    for t in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and np.isnan(v)) else v for v in t])
    n = len(df) + 1
    hdr = PatternFill("solid", fgColor="404040"); yel = PatternFill("solid", fgColor="FFF2CC")
    for c in ws[1]: c.fill = hdr; c.font = Font(bold=True, color="FFFFFF")
    first = list(df.columns).index(code_cols[0]); last = list(df.columns).index(code_cols[-1])
    sent = list(df.columns).index("sentence")
    for row in ws.iter_rows(min_row=2, max_row=n):
        for c in row[first:last + 1]: c.fill = yel
        row[sent].font = Font(bold=True); row[sent].alignment = Alignment(wrap_text=True)
    for i, col in enumerate(df.columns):
        L = openpyxl.utils.get_column_letter(i + 1)
        ws.column_dimensions[L].width = {"prev_sentence": 40, "sentence": 48, "next_sentence": 40, "notes": 26, "show": 16}.get(col, 11)
    ws.freeze_panes = "F2"
    letters = {c: openpyxl.utils.get_column_letter(list(df.columns).index(c) + 1) for c in df.columns}
    dvs = ([(f"{letters['stance_russia']}2:{letters['stance_ukraine']}{n}", '"positive,neutral,negative,unmentioned"'),
            (f"{letters['historical']}2:{letters['historical']}{n}", '"0,1"')] if sheet == "main"
           else [(f"{letters['stance']}2:{letters['stance']}{n}", '"positive,neutral,negative,unmentioned"')])
    dvs += [(f"{letters['uncodable']}2:{letters['uncodable']}{n}", '"1"'),
            (f"{letters['confidence']}2:{letters['confidence']}{n}", '"high,med,low"')]
    for rg, f in dvs:
        dv = DataValidation(type="list", formula1=f, allow_blank=True); dv.add(rg); ws.add_data_validation(dv)
    wi = wb.create_sheet("info")
    for line in info: wi.append([line])
    os.makedirs(os.path.dirname(path), exist_ok=True); wb.save(path)

files = []
for s in STUDENTS:
    mine = [r for r in new_main if student_of[r] == s]
    forced = [r for r in M[(M.student == s) & (M.orig_file == ORIG_MAIN[0])].row_id if r in mine and week1_blank.get(r) == s]
    rest = [r for r in mine if r not in forced]; rest = [rest[i] for i in rng.permutation(len(rest))]
    order = forced + rest
    chunks = np.array_split(np.array(order, dtype=object), len(NEW_MAIN_WEEKS))
    for (wk, due), ch in zip(NEW_MAIN_WEEKS, chunks):
        p = os.path.join(OUT, s, f"{wk}_due_{due}.xlsx")
        write(MB.loc[list(ch)].reset_index(), MAIN_COLS, CODE_MAIN, "main", p, LETTER[s],
              [f"{s} - {wk.replace('_', ' ').title()} (main coding). DUE FRIDAY {due}.", None,
               f"{len(ch)} sentences: stance_russia + stance_ukraine per row. Codebook v2.6.",
               "Code in order, top to bottom. Fill only the yellow columns; save this file in place (keep the filename).",
               "Do not compare answers with other coders. Use notes for judgment calls and devices."])
        files.append((p, list(ch), "main"))
    mp = [r for r in D_ids if student_of[r] == s]
    wk, due = NEW_PLAC_WEEK; p = os.path.join(OUT, s, f"{wk}_due_{due}.xlsx")
    write(PB.loc[mp].reset_index(), PLAC_COLS, CODE_PLAC, "placebo", p, LETTER[s],
          [f"{s} - Week 05 (PLACEBO coding). DUE FRIDAY {due}.", None,
           f"{len(mp)} sentences: single stance toward the row's target entity. Use the placebo codebook and worked examples.",
           "Code in order, top to bottom. Fill only the yellow columns; save this file in place."])
    files.append((p, mp, "placebo"))
C1, C2 = C_ids[: len(C_ids) // 2], C_ids[len(C_ids) // 2:]
for name, ids, blk in [("jared_WB_C1_main.xlsx", C1, "main"), ("jared_WB_C2_main.xlsx", C2, "main"), ("jared_WB_D_placebo.xlsx", D_ids, "placebo")]:
    p = os.path.join(OUT, "Jared", name)
    if blk == "main":
        write(MB.loc[ids].reset_index(), MAIN_COLS, CODE_MAIN, "main", p, "J",
              [f"Jared - winter-break batch {name.split('_')[2]} ({len(ids)} rows). Codebook v2.6.", None, "Shuffled across strata; blind to student codes."])
    else:
        write(PB.loc[ids].reset_index(), PLAC_COLS, CODE_PLAC, "placebo", p, "J",
              [f"Jared - placebo batch D ({len(ids)} rows).", None, "Shuffled across targets; blind to student codes."])
    files.append((p, ids, blk))
os.makedirs(os.path.join(OUT, "_admin"), exist_ok=True)
MAN.to_csv(os.path.join(OUT, "_admin", "assignment_master_v2.csv"), index=False)

# ---- 9. re-read every file and verify -----------------------------------------
seen = {}
for p, ids, blk in files:
    x = pd.read_excel(p, sheet_name=blk)
    assert list(x.row_id) == list(ids), f"row mismatch {p}"
    cc = CODE_MAIN if blk == "main" else CODE_PLAC
    assert x[cc].isna().all().all(), f"code cells not blank {p}"
    who = os.path.basename(os.path.dirname(p))
    for r in ids:
        seen.setdefault(r, []).append(who)
for r, w in seen.items():
    assert len(w) == len(set(w)), f"{r} appears twice for the same coder"
assert set(seen) == set(new_main) | set(new_plac) | set(C_ids) | set(D_ids)
say("[9] files verified:")
for p, ids, blk in files: say(f"    {os.path.relpath(p, OUT)}  {len(ids)}")
open(os.path.join(OUT, "_admin", "build_log.txt"), "w").write("\n".join(log) + "\n")
