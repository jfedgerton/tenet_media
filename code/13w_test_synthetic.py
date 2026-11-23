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
