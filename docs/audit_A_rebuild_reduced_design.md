# GPT audit A: reduced-design rebuild (`15_rebuild_reduced_design.py`)

Everything you need is in this file. The code is pasted at the bottom.

## Context
This is a human stance-coding project (Russia/Ukraine stance in podcast sentences). Three student coders (Emily = A, Josh = B, Pam = C) received an Oct 9 assignment. Every one of 10,000 main sentences and 2,000 placebo sentences went to exactly 2 of the 3 students (pairs A+B / B+C / A+C, balanced within stratum), split into 12 weekly Excel files per student. Only Week 1 was coded. On Nov 18 the PI (Jared) built two blind batches, which he has not yet coded. Batch A is every Week-1 sentence coded by exactly one student (1,762). Batch B is 1,000 union sentences nobody has coded.

## The new design the script must implement
1. A sample of 8,000 sentences made up of all 4,000 union, all 1,000 hard negatives, 2,000 non-union random (1,000 before and 1,000 on or after 2023-10-01) and 1,000 placebo (250 per target, at random). The non-union draw keeps every non-union row already coded or left blank in Week 1 and fills the rest at random.
2. Every selected sentence gets exactly two coders, Jared plus one student. The exception is the 94 Week-1 sentences already coded by two students. They stay student-student, and Jared does not code them.
3. Week-1 codes are never modified. Week-1 rows a student left blank go back to that same student, at the top of their next file.
4. Each new sentence goes to ONE of its two originally assigned students, load-balanced so students get equal work within stratum and within placebo target.
5. Jared gets batches C (remaining main, split C1/C2) and D (placebo). Students get weeks due 2026-12-04, 12-11 and 12-18 (main) and 2027-01-08 (placebo). Seed 123 throughout. Script 15 only writes to a staging folder and never to coder_materials.
6. Script 16 (also pasted) is the one-time release. It moves the old student files to `_superseded/old_schedule_nov30/`, refusing if any contain codes, then copies the staged files into the student folders. It has already been run, so treat it as a post hoc check. Did it do anything unsafe or lossy?

## Please check
- **Logic.** Does the code implement 1–5 exactly? Could any sentence end up with 0, 1 or 3 coders, or could a student code the same sentence twice?
- **Sampling.** Is the non-union and placebo draw random within the intended frames, reproducible with seed 123, and unaffected by Python set ordering? (Sets are sorted before `rng.choice`.)
- **Load balancing.** Can the greedy assignment bias which students get which strata or time periods?
- **Edge cases.** Week-1 blank rows that another student did code. Rows in both Week-1 files. Placebo rows. A rerun after the originals were moved to `_superseded/old_schedule_nov30`.
- **Assertions.** Is anything important NOT asserted that could fail silently?
- **Output files.** Same columns and order as the originals, all coding cells blank, dropdowns on the right columns.
- **Reproducibility.** Would a rerun on the same inputs produce identical outputs?
- **The test.** Does `tests/test_15_rebuild_reduced_design.py` actually exercise the failure modes above, and does its negative test fail for the right reason?

Report concrete bugs with line references first. List lower-priority suggestions separately. Do not propose new features or methods beyond what is needed to fix a bug.

## Code

### `code/3_human_coding/15_rebuild_reduced_design.py`
```python
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
#     originally assigned students (load-balanced within stratum).
#
# Usage: python3 15_rebuild_reduced_design.py <podcast_analysis_root> <out_dir>
# Writes staged files to <out_dir>; nothing in coder_materials is modified.
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
```

### `tests/test_15_rebuild_reduced_design.py`
```python
# 13w_test_synthetic.py -- builds a full-size fake coder_materials tree with the same
# structure as the real one, then runs 13w_rebuild_reduced_design.py on it.
# Usage: python3 13w_test_synthetic.py <fake_root>     (seed 123)
import sys, os, numpy as np, pandas as pd
R = sys.argv[1]; rng = np.random.default_rng(123)
S = ["Emily", "Josh", "Pam"]; PAIRS = [("Emily", "Josh"), ("Josh", "Pam"), ("Emily", "Pam")]
MAIN = ["week_01_due_2026-10-16.xlsx","week_02_due_2026-10-23.xlsx","week_03_due_2026-10-30.xlsx","week_04_due_2026-11-06.xlsx","week_05_due_2026-11-13.xlsx","week_06_due_2026-11-20.xlsx","week_07_due_2026-12-04.xlsx","week_08_due_2026-12-11.xlsx","week_09_due_2026-12-18.xlsx","week_10_due_2027-01-08.xlsx"]
PLAC = ["week_11_due_2027-01-15.xlsx","week_12_due_2027-01-22.xlsx"]
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
DONE = {"Josh": "Josh/week_01_due_2026-10-02-2.xlsx", "Emily": "Emily/week_01_SUBMITTED_by_Emily (1).xlsx", "Pam": "Pam/week_01_due_2026-10-02.xlsx"}
BL = {"Josh": [27, 295], "Emily": list(range(433, 473)), "Pam": [143, 182, 326, 327, 328, 400, 401, 402, 403]}
coded = {}
for s, f in DONE.items():
    w = pd.read_excel(f"{R}/coder_materials/{s}/{MAIN[0]}", sheet_name="main")
    w["stance_russia"] = "unmentioned"; w["stance_ukraine"] = "unmentioned"
    w.loc[BL[s], ["stance_russia", "stance_ukraine"]] = None
    w.to_excel(f"{R}/coder_materials/{f}", sheet_name="main", index=False)
    for r in w.row_id[w.stance_russia.notna()]: coded.setdefault(r, set()).add(s)
once = sorted(r for r, v in coded.items() if len(v) == 1)
os.makedirs(f"{R}/coder_review/Jared", exist_ok=True)
MI.loc[once].reset_index().assign(coder="J").to_excel(f"{R}/coder_review/Jared/jared_TG_A_complete_week1_pairs.xlsx", sheet_name="main", index=False)
pool = sorted(r for r in Mb.row_id[Mb.stratum == "union"] if r not in coded)
B = list(rng.choice(pool, 1000, replace=False))
MI.loc[B].reset_index().assign(coder="J").to_excel(f"{R}/coder_review/Jared/jared_TG_B_union_new.xlsx", sheet_name="main", index=False)
print("fake tree built: coded once", len(once), "twice", sum(len(v) == 2 for v in coded.values()))
```

### `code/3_human_coding/16_release_reduced_design.py`
```python
# 16_release_reduced_design.py -- release the Nov 23 reduced-design files to coders (run once).
# Moves superseded files to coder_materials/_superseded/old_schedule_nov30/ and
# copies staged files from coder_review/_staging_nov30/ into place. Logs every action.
# Usage: python3 16_release_reduced_design.py <podcast_analysis_root>
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
```
