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
