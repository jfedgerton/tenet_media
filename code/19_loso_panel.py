"""
25_loso_panel.py  --  build PER-INDIVIDUAL-FEED panels for the leave-one-show-out
robustness (Tim Pool's three feeds are kept separate, unlike build_h_panels which
pools them into tim_pool). Two outputs feed 26_loso.R:

  loso_stance_panel.csv   per (show, month) stance + volume for H1/H2/H3:
      n_total, n_total_78, n_total_79, n_ment_r, n_ment_r_78, n_ment_r_79, n_ment_u,
      r_score, r_pos, r_net, u_score, u_pos, u_net
  loso_divergence.csv     per (show, month) H4 main-spec agenda divergence:
      n_sentences, jsd  = JSD(show topic mix, contemporaneous control-pool mix),
      rarefied to RARE_N (finite-sample de-bias)

Window 2018-01 .. 2024-09 (indictment). Treated FEEDS kept individual; controls = the
rest. The LOSO (26_loso.R) just changes which feeds are flagged treated; these panels
are computed once. PI: Jared Edgerton (PSU). Seed 123.
"""
import numpy as np, pandas as pd

SEED = 123; np.random.seed(SEED)
CO = "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC = CO + "/data/sc_results"
START, TRUNC = pd.Timestamp("2018-01-01"), pd.Timestamp("2024-09-01")
TENET = {"the_benny_show", "benny_johnson_arena", "the_rubin_report", "timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool"}
ORD = {"positive": 1, "neutral": 0, "negative": -1}
RARE_N = 200; R_DRAWS = 15

# ---------- stance panel (per individual feed) from the 78/79 labeled corpus ----------
cols = ["show", "date", "topic", "russia_label", "russia_p_pos", "russia_p_neg",
        "ukraine_label", "ukraine_p_pos", "ukraine_p_neg"]
d = pd.read_parquet(SC + "/opus_c0_corpus_labeled.parquet", columns=cols)
d["date"] = pd.to_datetime(d["date"], errors="coerce"); d = d.dropna(subset=["date"])
d = d[(d.date >= START) & (d.date < TRUNC)].copy()
d["month"] = d["date"].values.astype("datetime64[M]")
d["rsc"] = d.russia_p_pos - d.russia_p_neg; d["usc"] = d.ukraine_p_pos - d.ukraine_p_neg
d["rment"] = d.russia_label != "unmentioned"; d["ument"] = d.ukraine_label != "unmentioned"
d["t78"] = d.topic == 78; d["t79"] = d.topic == 79
rows = []
for (s, m), g in d.groupby(["show", "month"]):
    rm = g[g.rment]; um = g[g.ument]
    rows.append(dict(show=s, month=m, n_total=len(g), n_total_78=int(g.t78.sum()), n_total_79=int(g.t79.sum()),
        n_ment_r=len(rm), n_ment_r_78=int(rm.t78.sum()), n_ment_r_79=int(rm.t79.sum()), n_ment_u=len(um),
        r_score=rm.rsc.mean() if len(rm) else np.nan, r_pos=(rm.russia_label=="positive").mean() if len(rm) else np.nan,
        r_net=rm.russia_label.map(ORD).mean() if len(rm) else np.nan,
        u_score=um.usc.mean() if len(um) else np.nan, u_pos=(um.ukraine_label=="positive").mean() if len(um) else np.nan,
        u_net=um.ukraine_label.map(ORD).mean() if len(um) else np.nan))
pd.DataFrame(rows).to_csv(SC + "/loso_stance_panel.csv", index=False)
print("STANCE rows", len(rows))

# ---------- H4 per-feed agenda divergence (jsd vs contemporaneous control pool) ----------
EPS = 1e-12
def jsd(p, q):
    m = 0.5*(p+q)
    kl = lambda a,b: np.sum((a+EPS)*np.log2((a+EPS)/(b+EPS)))
    return 0.5*kl(p,m)+0.5*kl(q,m)
cw = pd.read_parquet(CO + "/data/corpus_with_topics.parquet", columns=["show", "date", "topic"])
cw["date"] = pd.to_datetime(cw["date"], errors="coerce")
cw = cw[(cw.date >= START) & (cw.date < TRUNC) & (cw.topic != -1)].copy()
cw["month"] = cw["date"].values.astype("datetime64[M]")
cw["treated"] = cw["show"].isin(TENET)
# per-feed total volume (all topics) -> time-varying "total words" proxy control
vol = cw.groupby(["show", "month"]).size().reset_index(name="n_sent_total")
vol["month"] = vol["month"].astype(str)
vol.to_csv(SC + "/loso_volume.csv", index=False); print("VOLUME rows", len(vol))
UM = cw.groupby(["show", "month", "topic"]).size().reset_index(name="n")
mat = UM.pivot_table(index=["show", "month"], columns="topic", values="n", fill_value=0)
meta = mat.index.to_frame(index=False)
M = mat.to_numpy(np.float64); ns = M.sum(1)
mon = meta["month"].to_numpy(); shw = meta["show"].to_numpy()
treated = np.array([s in TENET for s in shw])
# contemporaneous control-pool reference per month
qref = {}
for mm in np.unique(mon):
    v = M[(mon == mm) & (~treated)].sum(0); qref[mm] = v/v.sum() if v.sum() > 0 else None
out = []
for i in range(M.shape[0]):
    q = qref.get(mon[i])
    if q is None or ns[i] < RARE_N: continue
    p0 = M[i]/M[i].sum()
    ds = [jsd(np.random.multinomial(RARE_N, p0).astype(float)/RARE_N, q) for _ in range(R_DRAWS)]
    out.append((shw[i], str(pd.Timestamp(mon[i]).date()), int(ns[i]), float(np.mean(ds))))
pd.DataFrame(out, columns=["show", "month", "n_sentences", "jsd"]).to_csv(SC + "/loso_divergence.csv", index=False)
print("DIVERGENCE rows", len(out), "LOSO_PANEL_DONE")
