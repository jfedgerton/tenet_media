# test_carryover_extra_pairs.py -- test of admin/carryover_old_partial.py and the extra-pairs path in
# 17/18, on a full-size FAKE tree.          python3 tests/test_carryover_extra_pairs.py [parent_dir]
#
# Builds the fake tree with tests/test_15, releases it as step 16 did, then plays Josh: he codes the first
# half of his OLD week_02 and saves it as week_02_OLD_partial.xlsx. Checks the dry run writes nothing,
# --apply carries exactly the rows still assigned to Josh with the right codes, notes and v2.6 flags,
# leaves every other cell alone, backs up first, and refuses a second run. Negative tests: invalid code,
# a row not from the old week_02, and a student who has started all stop it before writing.
# Then 17 must turn the rows now assigned to someone else into extra student-student pairs (never
# final labels) and 18 must report them; alpha is checked against the krippendorff package.
import sys, os, subprocess, tempfile, glob, shutil, hashlib
import numpy as np, pandas as pd, openpyxl, krippendorff

HERE = os.path.dirname(os.path.abspath(__file__))
CO = os.path.join(HERE, "..", "code", "3_human_coding", "admin", "carryover_old_partial.py")
S17 = os.path.join(HERE, "..", "code", "3_human_coding", "17_build_adjudication.py")
S18 = os.path.join(HERE, "..", "code", "3_human_coding", "18_icr_report.py")
PARENT = sys.argv[1] if len(sys.argv) > 1 else None
if PARENT: os.makedirs(PARENT, exist_ok=True)
W = tempfile.mkdtemp(prefix="testcarry_", dir=PARENT)
print("workdir", W)

# ---- fake tree + release ----------------------------------------------------------------
p = subprocess.run([sys.executable, os.path.join(HERE, "test_15_rebuild_reduced_design.py"), W], capture_output=True, text=True)
assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]
T15 = glob.glob(os.path.join(W, "test15_*"))[0]
R, O = os.path.join(T15, "fake"), os.path.join(T15, "out1")
DONE = {"Emily": "week_01_SUBMITTED_by_Emily (1).xlsx", "Josh": "week_01_due_2026-10-02-2.xlsx", "Pam": "week_01_due_2026-10-02.xlsx"}
for s in DONE:
    sup = f"{R}/coder_materials/_superseded/old_schedule_nov30/{s}"; os.makedirs(sup)
    for f in glob.glob(f"{R}/coder_materials/{s}/week_*.xlsx"):
        if os.path.basename(f) != DONE[s]: shutil.move(f, sup)
    for f in glob.glob(f"{O}/{s}/*.xlsx"): shutil.copy(f, f"{R}/coder_materials/{s}/")
for f in glob.glob(f"{O}/Jared/*.xlsx"): shutil.copy(f, f"{R}/coder_review/Jared/")
os.makedirs(f"{R}/coder_review/_admin", exist_ok=True)
shutil.copy(f"{O}/_admin/assignment_master_v2.csv", f"{R}/coder_review/_admin/")
M = pd.read_csv(f"{R}/coder_review/_admin/assignment_master_v2.csv").set_index("row_id")
NEW = [f"{R}/coder_materials/Josh/{f}" for f in ["week_02_due_2026-12-04.xlsx", "week_03_due_2026-12-11.xlsx", "week_04_due_2026-12-18.xlsx"]]
OLD = f"{R}/coder_materials/_superseded/old_schedule_nov30/Josh/week_02_due_2026-10-23.xlsx"
PART = f"{R}/coder_materials/Josh/week_02_OLD_partial.xlsx"
print("[1] fake tree released")

# ---- Josh codes the first half of his old week_02 ---------------------------------------------
rng = np.random.default_rng(123)
ST = ["positive", "neutral", "negative", "unmentioned"]
d = pd.read_excel(OLD, sheet_name="main")
for c in ("stance_russia", "stance_ukraine", "confidence", "notes"): d[c] = d[c].astype(object)
half = len(d) // 2
for i in range(half):
    d.at[i, "stance_russia"] = ST[rng.choice(4, p=[.1, .15, .1, .65])]
    d.at[i, "stance_ukraine"] = ST[rng.choice(4, p=[.1, .15, .1, .65])]
    d.at[i, "historical"] = 0; d.at[i, "confidence"] = "High"          # mixed case on purpose
d.at[0, "notes"] = "his own note"
carried_ids = [r for r in d.row_id[:half] if r in M.index and "Josh" in (M.at[r, "coder1"], M.at[r, "coder2"])]
extra_ids = [r for r in d.row_id[:half] if r in M.index and "Josh" not in (M.at[r, "coder1"], M.at[r, "coder2"])]
coll = carried_ids[0]                                              # plant a collusion sentence (same in OLD)
d.loc[d.row_id == coll, "sentence"] = "the whole Russia collusion thing was nonsense"
d.loc[d.row_id == coll, ["stance_russia", "stance_ukraine"]] = ["unmentioned", "unmentioned"]
o = pd.read_excel(OLD, sheet_name="main"); o.loc[o.row_id == coll, "sentence"] = "the whole Russia collusion thing was nonsense"
o.to_excel(OLD, sheet_name="main", index=False)
d.to_excel(PART, sheet_name="main", index=False)
P = d.set_index("row_id")
assert len(carried_ids) > 20 and len(extra_ids) > 20, (len(carried_ids), len(extra_ids))
print(f"[2] Josh coded {half} old rows: {len(carried_ids)} still his, {len(extra_ids)} now another student's")

def run(*a): return subprocess.run([sys.executable, *a], capture_output=True, text=True)
def hashes(): return {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in NEW}

# ---- dry run, apply, verify --------------------------------------------------------------------
h0 = hashes()
p = run(CO, R, "Josh"); assert p.returncode == 0 and "DRY RUN" in p.stdout, p.stdout[-800:] + p.stderr[-800:]
assert hashes() == h0 and not os.path.exists(f"{R}/coder_review/_admin/carryover_Josh_log.txt"), "dry run wrote something"
p = run(CO, R, "Josh", "--apply"); assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-2000:]
assert glob.glob(f"{R}/coder_review/_admin/backups/Josh_pre_carryover_*/week_02_due_2026-12-04.xlsx")
seen = set()
for f in NEW:
    x = pd.read_excel(f, sheet_name="main")
    for i, r in enumerate(x.row_id):
        if r in carried_ids:
            seen.add(r)
            assert x.at[i, "stance_russia"] == P.at[r, "stance_russia"] and x.at[i, "stance_ukraine"] == P.at[r, "stance_ukraine"]
            assert x.at[i, "confidence"] == "high" and str(x.at[i, "notes"]).startswith("carried from old week_02")
            nonun = P.at[r, "stance_russia"] != "unmentioned" or P.at[r, "stance_ukraine"] != "unmentioned"
            assert ("RECHECK v2.6 Rule A" in x.at[i, "notes"]) == nonun, (r, x.at[i, "notes"])   # fake kw_* are all 0
            if r == coll: assert "RECHECK v2.6 collusion" in x.at[i, "notes"]
            if r == d.row_id[0]: assert x.at[i, "notes"].endswith("his own note")
        else:
            assert x.loc[i, ["stance_russia", "stance_ukraine", "historical", "uncodable", "confidence", "notes"]].isna().all()
assert seen == set(carried_ids), (len(seen), len(carried_ids))
p = run(CO, R, "Josh", "--apply"); assert p.returncode != 0 and "has started" in p.stderr
print(f"[3] dry run wrote nothing; apply carried {len(seen)} rows with codes, notes and v2.6 flags; second run refused")

# ---- negative tests on a fresh copy of the tree --------------------------------------------------
bk = glob.glob(f"{R}/coder_review/_admin/backups/Josh_pre_carryover_*")[0]
def restore():
    for f in NEW: shutil.copy2(os.path.join(bk, os.path.basename(f)), f)
restore(); h1 = hashes()
x = d.copy(); x.at[1, "stance_russia"] = "pos"; x.to_excel(PART, sheet_name="main", index=False)
p = run(CO, R, "Josh", "--apply"); assert p.returncode != 0 and "invalid stance" in p.stderr and hashes() == h1
x = d.copy(); x.at[1, "row_id"] = "rc_9999x"; x.to_excel(PART, sheet_name="main", index=False)
p = run(CO, R, "Josh", "--apply"); assert p.returncode != 0 and "not in the old week_02" in p.stderr and hashes() == h1
d.to_excel(PART, sheet_name="main", index=False)
wb = openpyxl.load_workbook(NEW[2]); ws = wb["main"]; hdr = [c.value for c in ws[1]]
ws.cell(row=5, column=hdr.index("stance_russia") + 1).value = "neutral"; wb.save(NEW[2]); h2 = hashes()
p = run(CO, R, "Josh", "--apply"); assert p.returncode != 0 and "has started" in p.stderr and hashes() == h2
restore()
p = run(CO, R, "Josh", "--apply"); assert p.returncode == 0
print("[4] negative tests stop before writing: invalid code; row not from old week_02; student already started")

# ---- 17/18: extra student-student pairs ----------------------------------------------------------
partner = {}
for r in extra_ids:
    partner[r] = [c for c in (M.at[r, "coder1"], M.at[r, "coder2"]) if c != "Jared"][0]
filled = {}
for s in ("Emily", "Pam"):
    for f in glob.glob(f"{R}/coder_materials/{s}/week_0[234]_*.xlsx"):
        x = pd.read_excel(f, sheet_name="main")
        for c in ("stance_russia", "stance_ukraine"): x[c] = x[c].astype(object)
        for i, r in enumerate(x.row_id):
            if r in partner and partner[r] == s:
                a, b = ST[rng.choice(4)], ST[rng.choice(4)]
                x.at[i, "stance_russia"], x.at[i, "stance_ukraine"] = a, b; filled[r] = (a, b)
        x.to_excel(f, sheet_name="main", index=False)
for s in ("Emily", "Pam"):                       # partners may already have coded an extra row in their Week-1
    w = pd.read_excel(f"{R}/coder_materials/{s}/{DONE[s]}", sheet_name="main")
    for r, a, b_ in zip(w.row_id, w.stance_russia, w.stance_ukraine):
        if r in partner and partner[r] == s and pd.notna(a) and r not in filled: filled[r] = (a, b_)
p = run(S17, R); assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-2000:]
SUP = pd.read_csv(f"{R}/coder_review/adjudication/supplementary_pairs.csv")
assert len(SUP) == 2 * len(filled), (len(SUP), len(filled))
for r, t, cx, cy, xc, yc in zip(SUP.row_id, SUP.target, SUP.coder_x, SUP.coder_y, SUP.code_x, SUP.code_y):
    assert cx == "Josh" and cy == partner[r] and xc == P.at[r, f"stance_{t}"] and yc == filled[r][0 if t == "russia" else 1]
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert len(U) == 15000 and not ((U.row_id.isin(extra_ids)) & ((U.coder1 == "Josh") | (U.coder2 == "Josh"))).any()
cu = U[U.row_id.isin(carried_ids) & U.target.eq("russia")]
josh_codes = [(a if c1 == "Josh" else b) for c1, a, b in zip(cu.coder1, cu.code_1, cu.code_2)]
assert josh_codes == [P.at[r, "stance_russia"] for r in cu.row_id], "carried codes not read back by 17"
p = run(S18, R); assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-2000:]
rep = pd.read_csv(f"{R}/coder_review/icr/icr_report.csv")
num = {c: i for i, c in enumerate(["positive", "neutral", "negative", "unmentioned", "uncodable"])}
for fam in ("russia", "ukraine"):
    sub = SUP[SUP.target == fam]
    ref = krippendorff.alpha(reliability_data=np.array([[num[v] for v in sub.code_x], [num[v] for v in sub.code_y]], float),
                             level_of_measurement="nominal", value_domain=list(range(5)))
    ours = rep[(rep.scope == "supplementary_student_pairs") & (rep.target == fam)].iloc[0]
    assert abs(ours.alpha - ref) < 1e-9 and ours.n_units == len(sub), (fam, ours.alpha, ref)
    assert len(rep[(rep.scope == "student_student_combined") & (rep.target == fam)]) == 1
print(f"[5] 17 made {len(SUP)} extra student-student pairs (never final labels); 18 alpha matches the krippendorff package")
print("ALL TESTS PASSED")
