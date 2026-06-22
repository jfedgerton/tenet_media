"""
build_h_panels.py  --  the ONLY data-prep step (R lacks `arrow` on Roar).
Aggregates the c0-labeled topic-78/79 corpus into show-month panel CSVs that the
two R scripts consume. Does no modeling.

Outputs (to data/sc_results/):
  baseline_panel.csv        -- one row per unit-month; stance outcomes + H3 inputs
  perturb_panels_all.csv    -- stance perturbation grid (20 rules) for the sweep

Stance outcomes (among the relevant target's MENTIONED sentences):
  r_score/u_score = mean(p_pos - p_neg)      [probability-based; invariant to relabeling]
  r_pos/u_pos     = share labeled positive
  r_net/u_net     = mean ordinal (pos=+1, neu=0, neg=-1)
Combined (R - U) is formed in R.

H3 inputs (per unit-month):
  n_total, n_total_78, n_total_79                 -- sentence volume by topic scope
  n_ment_r, n_ment_r_78, n_ment_r_79              -- Russia-mention volume by topic scope
  => H3 proportions  = n_ment_r{,_78,_79} / n_total{,_78,_79}   (built in R)
  => H3 volume DV    = log1p(n_ment_r) and log1p(n_total)        (built in R)

Treatment = payment 2023-10-01; window 2018-01 .. 2024-09 (pre-indictment).
Treated units = the_benny_show, the_rubin_report, tim_pool (3 feeds pooled).
PI: Jared Edgerton (PSU).
"""
import pandas as pd, numpy as np

COLLAB = "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC = COLLAB + "/data/sc_results"
TREAT = pd.Timestamp("2023-10-01"); TRUNC = pd.Timestamp("2024-09-01"); START = pd.Timestamp("2018-01-01")
TIM = {"timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool"}
TRU = {"tim_pool", "the_benny_show", "the_rubin_report"}
ORD = {"positive": 1, "neutral": 0, "negative": -1}

cols = ["show", "date", "topic", "russia_label", "russia_p_pos", "russia_p_neg",
        "ukraine_label", "ukraine_p_pos", "ukraine_p_neg"]
df = pd.read_parquet(SC + "/opus_c0_corpus_labeled.parquet", columns=cols)
df["date"] = pd.to_datetime(df["date"], errors="coerce"); df = df.dropna(subset=["date"])
df = df[(df["date"] >= START) & (df["date"] < TRUNC)].copy()
df["month"] = df["date"].values.astype("datetime64[M]")
df["unit"] = df["show"].map(lambda s: "tim_pool" if s in TIM else s)
df["treated"] = df["unit"].isin(TRU).astype(int)
df["rsc"] = df["russia_p_pos"] - df["russia_p_neg"]
df["usc"] = df["ukraine_p_pos"] - df["ukraine_p_neg"]
df["rment"] = (df["russia_label"] != "unmentioned")
df["t78"] = (df["topic"] == 78); df["t79"] = (df["topic"] == 79)

# ---------- baseline panel (with H3 inputs) ----------
rows = []
for (u, m), s in df.groupby(["unit", "month"]):
    rm = s[s["rment"]]
    um = s[s["ukraine_label"] != "unmentioned"]
    rec = dict(unit=u, month=m, treated=int(s["treated"].iloc[0]),
               n_total=len(s), n_total_78=int(s["t78"].sum()), n_total_79=int(s["t79"].sum()),
               n_ment_r=len(rm), n_ment_r_78=int((rm["t78"]).sum()), n_ment_r_79=int((rm["t79"]).sum()),
               n_ment_u=len(um),
               r_score=rm["rsc"].mean() if len(rm) else np.nan,
               r_pos=(rm["russia_label"] == "positive").mean() if len(rm) else np.nan,
               r_net=rm["russia_label"].map(ORD).mean() if len(rm) else np.nan,
               u_score=um["usc"].mean() if len(um) else np.nan,
               u_pos=(um["ukraine_label"] == "positive").mean() if len(um) else np.nan,
               u_net=um["ukraine_label"].map(ORD).mean() if len(um) else np.nan)
    rows.append(rec)
base = pd.DataFrame(rows)
base["post"] = (base["month"] >= TREAT).astype(int); base["tp"] = base["treated"] * base["post"]
base.to_csv(SC + "/baseline_panel.csv", index=False)
print("BASELINE rows", len(base))

# ---------- stance perturbation grid (for the sweep; H1/H2 only) ----------
rules = {
    "R0_baseline": ({}, {}),
    "R1_RU_neu2neg": ({"neutral": "negative"}, {}), "R2_RU_neu2pos": ({"neutral": "positive"}, {}),
    "R3_UA_neu2neg": ({}, {"neutral": "negative"}), "R4_UA_neu2pos": ({}, {"neutral": "positive"}),
    "R5_both_neu2neg": ({"neutral": "negative"}, {"neutral": "negative"}),
    "R6_both_neu2pos": ({"neutral": "positive"}, {"neutral": "positive"}),
    "R7_proRU_antiUA": ({"neutral": "positive"}, {"neutral": "negative"}),
    "R8_antiRU_proUA": ({"neutral": "negative"}, {"neutral": "positive"}),
    "R9_UA_pos2neg": ({}, {"positive": "negative"}), "R10_RU_neg2pos": ({"negative": "positive"}, {}),
    "R11_RU_neu2neg_UA_pos2neg": ({"neutral": "negative"}, {"positive": "negative"}),
    "R12_RU_pos2neu": ({"positive": "neutral"}, {}),
    "R13_RU_neu2pos_UA_pos2neg": ({"neutral": "positive"}, {"positive": "negative"}),
    "R14_RU_neg2neu": ({"negative": "neutral"}, {}),
    "G1_both_pos2neu": ({"positive": "neutral"}, {"positive": "neutral"}),
    "G2_both_neg2neu": ({"negative": "neutral"}, {"negative": "neutral"}),
    "G3_both_all2neu": ({"positive": "neutral", "negative": "neutral"}, {"positive": "neutral", "negative": "neutral"}),
    "G4_both_neg2pos": ({"negative": "positive"}, {"negative": "positive"}),
    "G5_both_all2pos": ({"neutral": "positive", "negative": "positive"}, {"neutral": "positive", "negative": "positive"}),
}
def agg(sub, labcol, scol, mmap):
    lab = sub[labcol].map(lambda x: mmap.get(x, x)); ment = lab.isin(["positive", "negative", "neutral"])
    l2 = lab[ment]; n = int(ment.sum())
    if n == 0: return (0, np.nan, np.nan, np.nan)
    return (n, sub.loc[ment, scol].mean(), (l2 == "positive").mean(), l2.map(ORD).mean())
groups = [(k, v) for k, v in df.groupby(["unit", "month"])]
out = []
for name, (rmap, umap) in rules.items():
    for (u, m), s in groups:
        nr, rs, rp, rn = agg(s, "russia_label", "rsc", rmap)
        nu, us, up, un = agg(s, "ukraine_label", "usc", umap)
        out.append((name, u, m, int(s["treated"].iloc[0]), nr, rs, rp, rn, nu, us, up, un))
P = pd.DataFrame(out, columns=["rule", "unit", "month", "treated", "n_ment_r", "r_score", "r_pos", "r_net",
                               "n_ment_u", "u_score", "u_pos", "u_net"])
P["post"] = (P["month"] >= TREAT).astype(int); P["tp"] = P["treated"] * P["post"]
P.to_csv(SC + "/perturb_panels_all.csv", index=False)
print("PERTURB rules", P["rule"].nunique(), "rows", len(P))

# ---------- monthly audience series (Jon Green episode-level data) ----------
# Episodes -> show x month audience, mapped to analysis units (Tim pooled) via the
# static file's podcast_id_dd <-> norm(title) <-> unit map (same match the pipeline uses).
import re
def nrm(x): return re.sub(r"[^a-z0-9]", "", str(x).lower())
SHOWDATA = COLLAB + "/data/show_data"
try:
    ep = pd.read_csv(SHOWDATA + "/tenet_block_episode_metadata.csv",
                     usecols=["podcast_id_dd", "episode_airdate", "audience_lwr", "audience_upr", "audience_midpoint"],
                     low_memory=False)
    stt = pd.read_csv(SHOWDATA + "/treated_terminal_blocks_weightedDecay.csv", low_memory=False)
    units = sorted(set(df["unit"]))
    keymap = {nrm(u): u for u in units}
    for t in TIM:
        keymap[nrm(t)] = "tim_pool"                       # the 3 Tim feeds -> tim_pool
    stt["ukey"] = stt["title"].map(lambda s: keymap.get(nrm(s)))
    id2unit = stt.dropna(subset=["ukey"])[["podcast_id_dd", "ukey"]].copy()
    # coerce the merge key to a common numeric dtype: the static file has a mixed-type
    # column that otherwise parses podcast_id_dd inconsistently -> ~76 silent merge misses.
    id2unit["podcast_id_dd"] = pd.to_numeric(id2unit["podcast_id_dd"], errors="coerce")
    id2unit = id2unit.dropna(subset=["podcast_id_dd"]).drop_duplicates()
    ep["podcast_id_dd"] = pd.to_numeric(ep["podcast_id_dd"], errors="coerce")
    ep = ep.merge(id2unit, on="podcast_id_dd", how="inner")
    ep["airdate"] = pd.to_datetime(ep["episode_airdate"].astype(str).str[:10], errors="coerce")
    ep = ep.dropna(subset=["airdate"])
    ep["month"] = ep["airdate"].values.astype("datetime64[M]")
    am = (ep.groupby(["ukey", "month"])
            .agg(aud_mid=("audience_midpoint", "mean"), aud_lwr=("audience_lwr", "mean"),
                 aud_upr=("audience_upr", "mean"), n_eps=("audience_midpoint", "size"))
            .reset_index().rename(columns={"ukey": "unit"}))
    am.to_csv(SC + "/audience_monthly.csv", index=False)
    n_treat = am[am.unit.isin(TRU)].unit.nunique()
    print("AUDIENCE_MONTHLY rows", len(am), "units", am["unit"].nunique(),
          "(of", len(units), ") treated_units_matched", n_treat, "of 3")
except FileNotFoundError as e:
    print("AUDIENCE skipped (episode file not found):", e)

# ---------- total-words volume (all-topic sentence counts) -> loso_volume.csv ----------
# Time-varying volume control consumed by 13/23/26 (19_loso_panel rebuilds the same per-feed).
try:
    cw = pd.read_parquet(COLLAB + "/data/corpus_with_topics.parquet", columns=["show", "date", "topic"])
    cw["date"] = pd.to_datetime(cw["date"], errors="coerce")
    cw = cw[(cw["date"] >= START) & (cw["date"] < TRUNC) & (cw["topic"] != -1)]
    cw["month"] = cw["date"].values.astype("datetime64[M]")
    vol = cw.groupby(["show", "month"]).size().reset_index(name="n_sent_total")
    vol.to_csv(SC + "/loso_volume.csv", index=False)
    print("LOSO_VOLUME rows", len(vol))
except FileNotFoundError as e:
    print("VOLUME skipped (corpus_with_topics not found):", e)

print("BUILD_DONE")
