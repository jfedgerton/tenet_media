###############################################################################
# 18_icr_report.py -- inter-coder agreement from RAW (pre-adjudication) codes. Seed 123.
#
# Input: coder_review/adjudication/adjudicated_final.csv from step 17 (code_1, code_2 per
# (row_id, target) for the two assigned coders). Only complete pairs are used.
#
# Statistics
#   - Krippendorff's alpha, nominal, two coders per unit, no missing values within a unit:
#       coincidence matrix o_ck (each unit adds (a,b) and (b,a)); n_c = row sums; n = 2 * units
#       alpha = 1 - D_o / D_e,  D_o = sum_{c!=k} o_ck / n,  D_e = sum_{c!=k} n_c n_k / (n (n - 1))
#     Categories: positive, neutral, negative, unmentioned, uncodable. alpha is NaN when D_e = 0.
#   - 95% CI: nonparametric bootstrap over units (sentences for the gate, (row, target) otherwise),
#     1,000 resamples, seed 123, percentile interval.
#   - Percent agreement, and per-class specific agreement p_c = o_cc / n_c (share of a coder's
#     uses of class c that the other coder matched).
#   - Gate (mentioned vs unmentioned), per main sentence: "mentioned" if either target is
#     positive/neutral/negative for that coder, "unmentioned" if both targets are unmentioned;
#     sentences either coder marked uncodable are left out of the gate.
# Breakdowns: target (russia, ukraine, all placebo, each placebo entity), stratum x target,
# coder pair x target, and the gate overall / by stratum / by pair. Supplementary: extra student-student pairs
# from old partial files (step 17, supplementary_pairs.csv), alone and combined with the design's student pairs.
#
# Usage: python3 18_icr_report.py <podcast_analysis_root>
# Writes coder_review/icr/{icr_report.csv, icr_summary.md}
# Test: tests/test_17_18_adjudication_icr.py
###############################################################################
import sys, os
import numpy as np, pandas as pd

ROOT = sys.argv[1]
SEED = 123
B = 1000
IN = os.path.join(ROOT, "coder_review", "adjudication", "adjudicated_final.csv")
OUT = os.path.join(ROOT, "coder_review", "icr")
CODES = ["positive", "neutral", "negative", "unmentioned", "uncodable"]
GATE = ["mentioned", "unmentioned"]
cm = os.path.realpath(os.path.join(ROOT, "coder_materials")); ro = os.path.realpath(OUT)
assert not (ro == cm or ro.startswith(cm + os.sep)), "refusing to write inside coder_materials"
log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.append(s)

def coincidence(a, b, cats):
    ix = {c: i for i, c in enumerate(cats)}
    o = np.zeros((len(cats), len(cats)))
    np.add.at(o, ([ix[x] for x in a], [ix[y] for y in b]), 1)
    return o + o.T

def alpha_from(o):
    n_c = o.sum(axis=1); n = n_c.sum()
    if n < 2: return np.nan
    d_o = (o.sum() - np.trace(o)) / n
    d_e = (n_c.sum() ** 2 - (n_c ** 2).sum()) / (n * (n - 1))
    return np.nan if d_e == 0 else 1 - d_o / d_e

def stats(a, b, cats, rng):
    a, b = np.asarray(a), np.asarray(b); N = len(a)
    row = dict(n_units=N)
    if N == 0:
        return {**row, "alpha": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "pct_agree": np.nan}
    o = coincidence(a, b, cats)
    row["alpha"] = alpha_from(o)
    boots = []
    for _ in range(B):
        i = rng.integers(0, N, N)
        boots.append(alpha_from(coincidence(a[i], b[i], cats)))
    boots = np.array(boots, dtype=float); boots = boots[~np.isnan(boots)]
    row["ci_lo"], row["ci_hi"] = (np.percentile(boots, [2.5, 97.5]) if len(boots) else (np.nan, np.nan))
    row["pct_agree"] = float((a == b).mean())
    n_c = o.sum(axis=1)
    for j, c in enumerate(cats):
        row[f"n_{c}"] = int(n_c[j])
        row[f"agree_{c}"] = (o[j, j] / n_c[j]) if n_c[j] else np.nan
    return row

# ---- 1. load complete pairs -----------------------------------------------------
U = pd.read_csv(IN)
need = {"row_id", "block", "grp", "target", "coder1", "coder2", "code_1", "code_2", "status"}
assert need <= set(U.columns), need - set(U.columns)
C = U[U.status.isin(["agreed", "disagree"])].copy()
assert C.code_1.isin(CODES).all() and C.code_2.isin(CODES).all(), "unexpected code values"
C["pair"] = [" + ".join(sorted(p)) for p in zip(C.coder1, C.coder2)]
C["family"] = np.where(C.block == "placebo", "placebo", C.target)
say(f"[1] complete pairs: {len(C)} of {len(U)} units; by family {C.family.value_counts().to_dict()}")

# ---- 2. target-level breakdowns -------------------------------------------------------
rng = np.random.default_rng(SEED)
rows = []
def add(scope, group, target, sub):
    rows.append(dict(scope=scope, group=group, target=target, **stats(sub.code_1, sub.code_2, CODES, rng)))
for fam in ["russia", "ukraine", "placebo"]:
    add("overall", "all", fam, C[C.family == fam])
for ent in sorted(C.loc[C.block == "placebo", "target"].unique()):
    add("placebo_entity", ent, ent, C[(C.block == "placebo") & (C.target == ent)])
for strat in sorted(C.loc[C.block == "main", "grp"].unique()):
    for fam in ["russia", "ukraine"]:
        add("stratum", strat, fam, C[(C.grp == strat) & (C.family == fam)])
for pair in sorted(C.pair.unique()):
    for fam in ["russia", "ukraine", "placebo"]:
        sub = C[(C.pair == pair) & (C.family == fam)]
        if len(sub): add("pair", pair, fam, sub)

# ---- 2b. extra student-student pairs from old partial files (supplementary; not in the design) ----
SP = os.path.join(ROOT, "coder_review", "adjudication", "supplementary_pairs.csv")
if os.path.exists(SP):
    S = pd.read_csv(SP)
    if len(S):
        assert S.code_x.isin(CODES).all() and S.code_y.isin(CODES).all(), "unexpected code values in supplementary pairs"
        assert not (S.coder_x == "Jared").any() and not (S.coder_y == "Jared").any()
        S["family"] = np.where(S.block == "placebo", "placebo", S.target)
        for fam in ["russia", "ukraine"]:
            sub = S[S.family == fam]
            if len(sub):
                rows.append(dict(scope="supplementary_student_pairs", group="extra (old partial files)", target=fam,
                                 **stats(sub.code_x, sub.code_y, CODES, rng)))
            design_ss = C[(C.family == fam) & ~C.pair.str.contains("Jared")]
            both = pd.DataFrame({"a": list(design_ss.code_1) + list(sub.code_x), "b": list(design_ss.code_2) + list(sub.code_y)})
            if len(both):
                rows.append(dict(scope="student_student_combined", group="design + extra", target=fam,
                                 **stats(both.a, both.b, CODES, rng)))
        say(f"[2b] supplementary student-student pairs: {len(S)}")

# ---- 3. gate (mentioned vs unmentioned) per main sentence ---------------------------------
mm = C[C.block == "main"].pivot_table(index=["row_id", "grp", "pair"], columns="target",
                                      values=["code_1", "code_2"], aggfunc="first")
mm = mm.dropna()                                   # both targets complete for both coders
def gate(r, u):
    if "uncodable" in (r, u): return None
    return "mentioned" if (r in CODES[:3] or u in CODES[:3]) else "unmentioned"
G = pd.DataFrame({"g1": [gate(r, u) for r, u in zip(mm[("code_1", "russia")], mm[("code_1", "ukraine")])],
                  "g2": [gate(r, u) for r, u in zip(mm[("code_2", "russia")], mm[("code_2", "ukraine")])]},
                 index=mm.index).reset_index()
G = G.dropna(subset=["g1", "g2"])
def addg(scope, group, sub):
    rows.append(dict(scope=scope, group=group, target="gate", **stats(sub.g1, sub.g2, GATE, rng)))
addg("gate", "all", G)
for strat in sorted(G.grp.unique()): addg("gate_stratum", strat, G[G.grp == strat])
for pair in sorted(G.pair.unique()): addg("gate_pair", pair, G[G.pair == pair])

# ---- 4. write -------------------------------------------------------------------------
Rp = pd.DataFrame(rows)
os.makedirs(OUT, exist_ok=True)
Rp.to_csv(os.path.join(OUT, "icr_report.csv"), index=False)
def fmt(v): return "" if pd.isna(v) else f"{v:.2f}"
head = Rp[Rp.scope.isin(["overall", "gate"])]
md = ["# Inter-coder agreement (raw codes, before adjudication)", "",
      f"Complete pairs: {len(C)} (row, target) units; gate: {len(G)} sentences. Nominal Krippendorff's alpha; "
      f"95% CI from {B} bootstrap resamples of units (seed 123). Full breakdowns in icr_report.csv.", "",
      "| Target | Units | alpha | 95% CI | % agree |", "|---|---|---|---|---|"]
for t in head.itertuples():
    md.append(f"| {t.target} | {t.n_units} | {fmt(t.alpha)} | {fmt(t.ci_lo)}–{fmt(t.ci_hi)} | {fmt(t.pct_agree)} |")
md += ["", "| Pair | Target | Units | alpha | 95% CI |", "|---|---|---|---|---|"]
for t in Rp[Rp.scope == "pair"].itertuples():
    md.append(f"| {t.group} | {t.target} | {t.n_units} | {fmt(t.alpha)} | {fmt(t.ci_lo)}–{fmt(t.ci_hi)} |")
open(os.path.join(OUT, "icr_summary.md"), "w").write("\n".join(md) + "\n")
for t in head.itertuples():
    say(f"[4] {t.target:8s} units {t.n_units:5d}  alpha {fmt(t.alpha)}  CI {fmt(t.ci_lo)}-{fmt(t.ci_hi)}  agree {fmt(t.pct_agree)}")
