# test_17_18_adjudication_icr.py -- end-to-end test of 17_build_adjudication.py and
# 18_icr_report.py on a full-size FAKE tree.        python3 tests/test_17_18_adjudication_icr.py [parent_dir]
#
# 1. Build the fake tree with tests/test_15 (fresh, test-owned folder), then "release" step 15's
#    output the way step 16 did (student weeks into coder_materials, Jared batches and the
#    assignment master into coder_review).
# 2. Fill every coded file with synthetic codes: a hidden true label per (row, target), each coder
#    reports it with probability 0.85, otherwise a different random stance. Week-1 blanks stay blank
#    and come back filled in week_02; the A1 row (uncodable in Week-1) gets a different code in week_02.
# 3. Check 17 independently: unit counts, disagreements, Week-1-first rule, blind sheet and key,
#    decisions kept on re-run, raw-code change clears a decision, rule required, Jon sample drawn once.
# 4. Check 18: alpha for every family and the gate equals the published `krippendorff` package
#    computed straight from the coded files; CI brackets alpha.
# 5. Negative tests: a code from an unassigned coder and a missing file must make 17 fail.
import sys, os, subprocess, tempfile, glob, shutil, hashlib
import numpy as np, pandas as pd, openpyxl, krippendorff

HERE = os.path.dirname(os.path.abspath(__file__))
S17 = os.path.join(HERE, "..", "code", "3_human_coding", "17_build_adjudication.py")
S18 = os.path.join(HERE, "..", "code", "3_human_coding", "18_icr_report.py")
PARENT = sys.argv[1] if len(sys.argv) > 1 else None
if PARENT: os.makedirs(PARENT, exist_ok=True)
W = tempfile.mkdtemp(prefix="test1718_", dir=PARENT)
print("workdir", W)

# ---- 1. fake tree + release --------------------------------------------------------
p = subprocess.run([sys.executable, os.path.join(HERE, "test_15_rebuild_reduced_design.py"), W], capture_output=True, text=True)
assert p.returncode == 0, p.stdout[-1500:] + p.stderr[-1500:]
T15 = glob.glob(os.path.join(W, "test15_*"))[0]
R, O = os.path.join(T15, "fake"), os.path.join(T15, "out1")
DONE = {"Emily": "week_01_SUBMITTED_by_Emily (1).xlsx", "Josh": "week_01_due_2026-10-02-2.xlsx", "Pam": "week_01_due_2026-10-02.xlsx"}
for s in ["Emily", "Josh", "Pam"]:                      # as step 16: originals out, staged weeks in
    sup = f"{R}/coder_materials/_superseded/old_schedule_nov30/{s}"; os.makedirs(sup)
    for f in glob.glob(f"{R}/coder_materials/{s}/week_*.xlsx"):
        if os.path.basename(f) != DONE[s]: shutil.move(f, sup)
    for f in glob.glob(f"{O}/{s}/*.xlsx"): shutil.copy(f, f"{R}/coder_materials/{s}/")
for f in glob.glob(f"{O}/Jared/*.xlsx"): shutil.copy(f, f"{R}/coder_review/Jared/")
os.makedirs(f"{R}/coder_review/_admin", exist_ok=True)
shutil.copy(f"{O}/_admin/assignment_master_v2.csv", f"{R}/coder_review/_admin/")
M = pd.read_csv(f"{R}/coder_review/_admin/assignment_master_v2.csv").set_index("row_id")
print("[1] fake tree released")

# ---- 2. synthetic codes ----------------------------------------------------------------
rng = np.random.default_rng(123)
ST = ["positive", "neutral", "negative", "unmentioned"]
truth = {}
for r, blk, grp in zip(M.index, M.block, M.grp):
    for t in (["russia", "ukraine"] if blk == "main" else [grp]):
        truth[(r, t)] = ST[rng.choice(4, p=[.15, .15, .1, .6])]
def report(r, t):
    v = truth[(r, t)]
    return v if rng.random() < .85 else rng.choice([x for x in ST if x != v])
W1 = {"Emily": "Emily/week_01_SUBMITTED_by_Emily (1).xlsx", "Josh": "Josh/week_01_due_2026-10-02-2.xlsx", "Pam": "Pam/week_01_due_2026-10-02.xlsx"}
files = [(s, f"coder_materials/{W1[s]}", "main") for s in W1]
for s in ["Emily", "Josh", "Pam"]:
    files += [(s, f, "placebo" if "week_05" in f else "main") for f in
              sorted(os.path.relpath(x, R) for x in glob.glob(f"{R}/coder_materials/{s}/week_0[2-5]_*.xlsx"))]
files += [("Jared", os.path.relpath(x, R), "placebo" if "_D_" in x else "main") for x in sorted(glob.glob(f"{R}/coder_review/Jared/*.xlsx"))]
expected = {}                               # (coder, row, target) -> code that 17 must use
a1_row = None
for coder, rel, sheet in files:
    d = pd.read_excel(f"{R}/{rel}", sheet_name=sheet)
    for c in ("stance_russia", "stance_ukraine", "stance"):
        if c in d.columns: d[c] = d[c].astype(object)
    for i, r in enumerate(d.row_id):
        if sheet == "main":
            if "week_01" in rel:
                if pd.isna(d.at[i, "stance_russia"]):
                    if str(d.at[i, "uncodable"]).strip() in ("1", "1.0"):   # A1 row: Week-1 uncodable wins
                        a1_row = r
                        for t in ("russia", "ukraine"): expected[(coder, r, t)] = "uncodable"
                    continue                                                # blank: filled later in week_02
            for t, col in (("russia", "stance_russia"), ("ukraine", "stance_ukraine")):
                v = report(r, t); d.at[i, col] = v
                expected.setdefault((coder, r, t), v)
        else:
            t = M.at[r, "grp"]; v = report(r, t); d.at[i, "stance"] = v; expected.setdefault((coder, r, t), v)
    d.to_excel(f"{R}/{rel}", sheet_name=sheet, index=False)
assert a1_row is not None
print(f"[2] synthetic codes written to {len(files)} files; A1 row {a1_row}")

def run(script):
    return subprocess.run([sys.executable, script, R], capture_output=True, text=True)

# ---- 3. 17 checks ------------------------------------------------------------------------
p = run(S17); assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-3000:]
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert len(U) == 2 * (M.block == "main").sum() + (M.block == "placebo").sum() == 15000, len(U)
assert (U.status != "incomplete").all(), U.status.value_counts()
exp_dis = 0
for r, t, c1, c2, a, b in zip(U.row_id, U.target, U.coder1, U.coder2, U.code_1, U.code_2):
    assert a == expected[(c1, r, t)] and b == expected[(c2, r, t)], (r, t, a, b)
    exp_dis += expected[(c1, r, t)] != expected[(c2, r, t)]
assert (U.status == "disagree").sum() == exp_dis
assert set(U.loc[U.row_id == a1_row, "code_1"].tolist() + U.loc[U.row_id == a1_row, "code_2"].tolist()) & {"uncodable"}
print(f"[3a] 15,000 units complete; {exp_dis} disagreements match the files; Week-1-first rule holds (A1 row uncodable)")

SH = f"{R}/coder_review/adjudication/adjudication_sheet.xlsx"
key = pd.read_csv(f"{R}/coder_review/_admin/adjudication_key.csv").set_index(["row_id", "target"])
sheets = {sh: pd.read_excel(SH, sheet_name=sh) for sh in ("main", "placebo")}
assert sum(len(x) for x in sheets.values()) == exp_dis
for sh, x in sheets.items():
    blob = " ".join(str(v) for v in x.values.ravel())
    assert not any(n in blob for n in ["Emily", "Josh", "Pam", "Jared"]), "coder name visible in the blind sheet"
    for r, t, a, b in zip(x.row_id, x.target, x.code_A, x.code_B):
        k = key.loc[(r, t)]
        assert a == expected[(k.coder_A, r, t)] and b == expected[(k.coder_B, r, t)]
p2 = run(S17); assert p2.returncode == 0
assert pd.read_csv(f"{R}/coder_review/_admin/adjudication_key.csv").equals(key.reset_index()), "A/B order changed between runs"
print("[3b] blind sheet has no coder names; key matches; A/B order stable across runs")

def fill(n, with_rule=True):
    wb = openpyxl.load_workbook(SH); ws = wb["main"]
    hdr = [c.value for c in ws[1]]; fi, ri = hdr.index("final_code") + 1, hdr.index("rule") + 1
    for i in range(2, 2 + n):
        ws.cell(row=i, column=fi, value=ws.cell(row=i, column=hdr.index("code_A") + 1).value)
        if with_rule: ws.cell(row=i, column=ri, value="Plain reading (no special rule)")
    wb.save(SH)
fill(10); assert run(S17).returncode == 0
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert (U.final_status == "adjudicated").sum() == 10, U.final_status.value_counts()
x = pd.read_excel(SH, sheet_name="main")
r0, t0 = x.row_id[0], x.target[0]
k = key.loc[(r0, t0)]
rel = [f for c, f, s in files if c == k.coder_A and s == "main" and r0 in set(pd.read_excel(f"{R}/{f}", sheet_name="main").row_id)][-1]
d = pd.read_excel(f"{R}/{rel}", sheet_name="main"); col = "stance_russia" if t0 == "russia" else "stance_ukraine"
d[col] = d[col].astype(object)
old = d.loc[d.row_id == r0, col].iloc[0]
d.loc[d.row_id == r0, col] = [v for v in ST if v not in (old, x.code_B[0])][0]
d.to_excel(f"{R}/{rel}", sheet_name="main", index=False)
assert run(S17).returncode == 0
x = pd.read_excel(SH, sheet_name="main").set_index(["row_id", "target"])
assert pd.isna(x.loc[(r0, t0), "final_code"]) and x.loc[(r0, t0), "changed_since_adjudicated"] == 1 \
       and x.loc[(r0, t0), "previous_final_code"] == old
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert (U.final_status == "adjudicated").sum() == 9
pr = pd.read_csv(f"{R}/coder_review/adjudication/problems.csv")
assert "raw_code_changed_after_adjudication" in set(pr.kind)
print("[3c] decisions kept on re-run; a raw-code change clears the decision, flags it, keeps the old one")

# rule required: fill everything but leave one final without a rule
wb = openpyxl.load_workbook(SH)
for sh in ("main", "placebo"):
    ws = wb[sh]; hdr = [c.value for c in ws[1]]
    fi, ri, ai = hdr.index("final_code") + 1, hdr.index("rule") + 1, hdr.index("code_A") + 1
    for i in range(2, ws.max_row + 1):
        if ws.cell(row=i, column=fi).value is None: ws.cell(row=i, column=fi, value=ws.cell(row=i, column=ai).value)
        if ws.cell(row=i, column=ri).value is None: ws.cell(row=i, column=ri, value="Other (see notes)")
ws = wb["placebo"]; ws.cell(row=2, column=[c.value for c in ws[1]].index("rule") + 1).value = None   # cell(value=None) is a no-op
wb.save(SH)
assert run(S17).returncode == 0
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
assert (U.final_status == "pending").sum() == 1
assert "final_code_without_rule" in set(pd.read_csv(f"{R}/coder_review/adjudication/problems.csv").kind)
JON = f"{R}/coder_review/adjudication/jon_audit_sample.xlsx"
assert not os.path.exists(JON), "Jon sample drawn while a row was pending"
wb = openpyxl.load_workbook(SH); ws = wb["placebo"]; ws.cell(row=2, column=[c.value for c in ws[1]].index("rule") + 1, value="Other (see notes)"); wb.save(SH)
assert run(S17).returncode == 0
J = pd.read_excel(JON)
assert len(J) == 200 and not J.duplicated(["row_id", "target"]).any()
fam = np.where(J.target.isin(["russia", "ukraine"]), J.target, "placebo")
Dall = pd.concat([pd.read_excel(SH, sheet_name=s) for s in ("main", "placebo")])
share = pd.Series(np.where(Dall.target.isin(["russia", "ukraine"]), Dall.target, "placebo")).value_counts(normalize=True)
got = pd.Series(fam).value_counts()
assert all(abs(got[f] - 200 * share[f]) <= 1 for f in share.index), (got.to_dict(), share.to_dict())
h = hashlib.sha256(open(JON, "rb").read()).hexdigest()
assert run(S17).returncode == 0 and hashlib.sha256(open(JON, "rb").read()).hexdigest() == h, "Jon sample redrawn"
print(f"[3d] rule required; Jon sample waits for completion, then 200 rows {got.to_dict()} drawn once")

# ---- 4. 18 checks: alpha vs the krippendorff package, straight from the files ----------------
p = run(S18); assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-3000:]
rep = pd.read_csv(f"{R}/coder_review/icr/icr_report.csv")
num = {c: i for i, c in enumerate(["positive", "neutral", "negative", "unmentioned", "uncodable"])}
U = pd.read_csv(f"{R}/coder_review/adjudication/adjudicated_final.csv")
for f in ["russia", "ukraine", "placebo"]:
    sub = U[(np.where(U.block == "placebo", "placebo", U.target)) == f]
    data = np.array([[num[a] for a in sub.code_1], [num[b] for b in sub.code_2]], dtype=float)
    ref = krippendorff.alpha(reliability_data=data, level_of_measurement="nominal", value_domain=list(range(5)))
    ours = rep[(rep.scope == "overall") & (rep.target == f)].iloc[0]
    assert abs(ours.alpha - ref) < 1e-9, (f, ours.alpha, ref)
    assert ours.ci_lo <= ours.alpha <= ours.ci_hi
    assert ours.n_units == len(sub)
# raw codes in adjudicated_final must equal the file codes (the edited one included)
chg = {(r0, t0)}
for r, t, c1, c2, a, b in zip(U.row_id, U.target, U.coder1, U.coder2, U.code_1, U.code_2):
    if (r, t) in chg: continue
    assert a == expected[(c1, r, t)] and b == expected[(c2, r, t)]
g = rep[rep.scope == "gate"].iloc[0]
mm = U[U.block == "main"]
def gl(x, y): return None if "uncodable" in (x, y) else (0 if (x in ST[:3] or y in ST[:3]) else 1)
g1, g2 = [], []
for r, sub in mm.groupby("row_id"):
    s = sub.set_index("target")
    a, b = gl(s.at["russia", "code_1"], s.at["ukraine", "code_1"]), gl(s.at["russia", "code_2"], s.at["ukraine", "code_2"])
    if a is not None and b is not None: g1.append(a); g2.append(b)
ref = krippendorff.alpha(reliability_data=np.array([g1, g2], dtype=float), level_of_measurement="nominal")
assert abs(g.alpha - ref) < 1e-9 and g.n_units == len(g1), (g.alpha, ref, g.n_units, len(g1))
assert os.path.exists(f"{R}/coder_review/icr/icr_summary.md")
print(f"[4] 18 alpha equals the krippendorff package for russia, ukraine, placebo and the gate "
      f"(russia {rep[(rep.scope=='overall')&(rep.target=='russia')].alpha.iloc[0]:.3f}); CIs bracket alpha")

# ---- 5. negative tests ----------------------------------------------------------------------------
rel = f"coder_materials/Emily/week_02_due_2026-12-04.xlsx"
keep = open(f"{R}/{rel}", "rb").read()
d = pd.read_excel(f"{R}/{rel}", sheet_name="main")
foreign = [r for r in M.index if M.at[r, "block"] == "main" and "Emily" not in (M.at[r, "coder1"], M.at[r, "coder2"])][0]
d.loc[len(d)] = d.iloc[0]; d.at[len(d) - 1, "row_id"] = foreign
d.to_excel(f"{R}/{rel}", sheet_name="main", index=False)
p = run(S17); open(f"{R}/{rel}", "wb").write(keep)
assert p.returncode != 0 and "is not assigned to it" in p.stderr, p.stderr[-800:]
os.rename(f"{R}/{rel}", f"{R}/{rel}.moved")
p = run(S17); os.rename(f"{R}/{rel}.moved", f"{R}/{rel}")
assert p.returncode != 0 and "missing coded file" in p.stderr, p.stderr[-800:]
print("[5] negative tests fail for the right reason: unassigned coder; missing file")
print("ALL TESTS PASSED")
