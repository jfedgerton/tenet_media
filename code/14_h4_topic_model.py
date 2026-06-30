"""
22_agenda_divergence_panel.py  --  H4 (agenda divergence): build the per-show-month
topic-distribution divergence panel that 23_h4_divergence_grid.R consumes.

H4 = the Tenet hosts are paid to push a *divisive, distinctive agenda*. We measure
how each show-month's topic mix diverges from a reference mix, then test (in 23)
H4a (pre-payment level: treated already more divergent) and H4b (DiD: treated
diverge MORE post-payment).

Only the HARD topic label is needed (corpus_with_topics.parquet `topic`), so no
model reload. Outlier topic -1 is dropped.

Operationalization grid (the user wants several; 23 estimates each):
  measure   in {jsd, kl_sm, cosine}            (columns; all computed per cell)
  reference in {contemp, frozen, external}      contemp = control pool THAT month
                                                frozen  = control pool pre-payment (<2023-10), fixed
                                                external= low-exposure controls (bottom 50% similar to
                                                          the treated pool, pre-period) that month
  topicset  in {all, drop7879, droprus}         all topics / drop 78,79 / drop Russia-adjacent
  rare      in {rare, raw}                       rare = multinomial-rarefied to RARE_N (de-biases
                                                  finite-sample JSD), averaged over R_DRAWS; raw = full
MAIN spec = measure=jsd, reference=contemp, topicset=all, rare=rare.

Finite-sample note: divergence is biased UP at small n. We rarefy each focal
show-month to a common RARE_N (constant bias across units) and also pass
n_sentences so 23 can add a log(n) control. The reference pool is large (many
shows) so it is used at full resolution.

Outputs (data/sc_results/):
  h4_divergence_panel.csv   unit,month,treated,n_sentences,topicset,reference,rare,jsd,kl_sm,cosine
  h4_tfidf_top_topics.csv   per Tenet feed: top-5 most distinctive topics (topic-level TF-IDF)

PI: Jared Edgerton (PSU). Seed 123.
"""
import re
import numpy as np, pandas as pd

SEED = 123; np.random.seed(SEED)
COLLAB = "/storage/group/LiberalArts/default/jfe4_collab/podcast"; SC = COLLAB + "/data/sc_results"
CORPUS = COLLAB + "/data/corpus_with_topics.parquet"
PANEL = SC + "/baseline_panel.csv"
TOPIC_INFO = COLLAB + "/data/topic_info.csv"
START, TRUNC, FREEZE = pd.Timestamp("2018-01-01"), pd.Timestamp("2024-09-01"), pd.Timestamp("2023-10-01")
TIM = {"timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool"}
TRU = {"tim_pool", "the_benny_show", "the_rubin_report"}
BEN = {"the_benny_show", "benny_johnson_arena"}   # Tenet Arena feed pooled into Benny
TENET_FEEDS = ["the_benny_show", "the_rubin_report"] + sorted(TIM)
RUS = [78, 79]
RARE_N = 200; R_DRAWS = 15
RUS_KW = re.compile(r"russ|ukrain|putin|kyiv|kiev|kremlin|moscow|zelens|donbas|nato", re.I)

# ---- load corpus, restrict to analysis shows + window, drop outlier topic -1 ----
units = pd.read_csv(PANEL)["unit"].unique().tolist()
shows = set()
for u in units:
    shows |= TIM if u == "tim_pool" else (BEN if u == "the_benny_show" else {u})
df = pd.read_parquet(CORPUS, columns=["show", "date", "topic"])
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df[df["date"].between(START, TRUNC, inclusive="left") & df["show"].isin(shows) & (df["topic"] != -1)].copy()
df["unit"] = np.where(df["show"].isin(TIM), "tim_pool", np.where(df["show"].isin(BEN), "the_benny_show", df["show"]))
df["month"] = df["date"].values.astype("datetime64[M]")
df["treated"] = df["unit"].isin(TRU).astype(int)
print("[load]", len(df), "sentences;", df["unit"].nunique(), "units;", df["topic"].nunique(), "topics")

# ---- Russia-adjacent topic set (for droprus) from topic keywords ----
adj = set(RUS)
try:
    ti = pd.read_csv(TOPIC_INFO)
    txtcol = "Name" if "Name" in ti.columns else ti.columns[-1]
    adj |= set(ti.loc[ti[txtcol].astype(str).str.contains(RUS_KW), "Topic"].tolist())
except Exception as e:
    print("[warn] topic_info unavailable, droprus = {78,79} only:", e)
print("[droprus] excludes", len(adj), "topics")
TOPICSETS = {"all": set(), "drop7879": set(RUS), "droprus": adj}

# ---- unit-month x topic count matrix ----
cnt = df.groupby(["unit", "month", "topic"]).size().reset_index(name="n")
UM = cnt.pivot_table(index=["unit", "month"], columns="topic", values="n", fill_value=0)
meta = UM.index.to_frame(index=False)
meta["treated"] = meta["unit"].isin(TRU).astype(int)
alltopics = list(UM.columns)
M = UM.to_numpy(dtype=np.float64)                       # (n_um, n_topics)
nsent = M.sum(1)
mon = meta["month"].to_numpy(); trt = meta["treated"].to_numpy()
print("[matrix]", M.shape)

# ---- low-exposure control set (external ref): bottom 50% cosine-similar to treated pool, pre-period ----
pre = mon < FREEZE
tre_pre = M[(trt == 1) & pre].sum(0); tre_pre = tre_pre / tre_pre.sum()
ctrl_idx = np.where(trt == 0)[0]
cu = meta["unit"].to_numpy()
def cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na > 0 and nb > 0 else 0.0
csim = {}
for u in np.unique(cu[trt == 0]):
    v = M[(cu == u) & pre].sum(0)
    csim[u] = cos(v, tre_pre) if v.sum() > 0 else 0.0
ext_units = set(sorted(csim, key=csim.get)[: max(1, len(csim) // 2)])   # least similar half
print("[external] low-exposure controls:", len(ext_units))

EPS = 1e-12
def restrict(vecs, drop):
    keep = [i for i, t in enumerate(alltopics) if t not in drop]
    return vecs[:, keep] if vecs.ndim == 2 else vecs[keep], keep
def norml(v):
    s = v.sum(); return v / s if s > 0 else v
def jsd(p, q):
    m = 0.5 * (p + q);
    def kl(a, b): a = a + EPS; b = b + EPS; return np.sum(a * np.log2(a / b))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)
def kl_sm(p, q):
    p = p + EPS; q = q + EPS; p = p / p.sum(); q = q / q.sum(); return float(np.sum(p * np.log(p / q)))
def cosd(p, q):
    return 1.0 - cos(p, q)
def measures(p, q):
    return jsd(p, q), kl_sm(p, q), cosd(p, q)

rows = []
for tsname, drop in TOPICSETS.items():
    Mt, keep = restrict(M, drop)
    rs = Mt.sum(1)                                            # n in this topicset per um
    # references for this topicset
    q_contemp = {}                                            # month -> control-pool share
    for mm in np.unique(mon):
        sel = (mon == mm) & (trt == 0)
        q_contemp[mm] = norml(Mt[sel].sum(0))
    q_frozen = norml(Mt[(trt == 0) & pre].sum(0))
    q_ext = {}
    extmask = np.array([u in ext_units for u in cu])
    for mm in np.unique(mon):
        sel = (mon == mm) & extmask
        v = Mt[sel].sum(0); q_ext[mm] = norml(v) if v.sum() > 0 else q_frozen
    REF = {"contemp": (lambda i: q_contemp[mon[i]]), "frozen": (lambda i: q_frozen), "external": (lambda i: q_ext[mon[i]])}
    for i in range(Mt.shape[0]):
        n_i = rs[i]
        if n_i < 1: continue
        p_full = norml(Mt[i])
        # rarefied p (multinomial), averaged measures; raw p
        modes = {}
        modes["raw"] = [p_full]
        if n_i >= RARE_N:
            pr = p_full
            modes["rare"] = [norml(np.random.multinomial(RARE_N, pr).astype(float)) for _ in range(R_DRAWS)]
        for rare, plist in modes.items():
            for rname, qf in REF.items():
                q = qf(i)
                vals = np.array([measures(p, q) for p in plist])  # (draws,3)
                mj, mk, mc = vals.mean(0)
                rows.append((cu[i], str(pd.Timestamp(mon[i]).date()), int(trt[i]), int(n_i), tsname, rname, rare, mj, mk, mc))
out = pd.DataFrame(rows, columns=["unit", "month", "treated", "n_sentences", "topicset", "reference", "rare", "jsd", "kl_sm", "cosine"])
out.to_csv(SC + "/h4_divergence_panel.csv", index=False)
print("[done] h4_divergence_panel.csv", len(out), "rows")

# ---- TF-IDF distinctive topics per Tenet feed (show-level; shows=docs, topics=terms) ----
sc = df.groupby(["show", "topic"]).size().reset_index(name="n")
ST = sc.pivot_table(index="show", columns="topic", values="n", fill_value=0)
TF = ST.div(ST.sum(1), axis=0)
df_t = (ST > 0).sum(0)                                        # docs per topic
IDF = np.log(len(ST) / (1.0 + df_t))
TFIDF = TF * IDF
kw = {}
try:
    ti2 = pd.read_csv(TOPIC_INFO); tc = "Name" if "Name" in ti2.columns else ti2.columns[-1]
    kw = dict(zip(ti2["Topic"], ti2[tc].astype(str)))
except Exception:
    pass
trows = []
for s in TENET_FEEDS:
    if s not in TFIDF.index: continue
    top = TFIDF.loc[s].sort_values(ascending=False).head(5)
    for rank, (tp, val) in enumerate(top.items(), 1):
        trows.append((s, rank, int(tp), round(float(val), 5), kw.get(tp, "")))
pd.DataFrame(trows, columns=["show", "rank", "topic", "tfidf", "keywords"]).to_csv(SC + "/h4_tfidf_top_topics.csv", index=False)
print("[done] h4_tfidf_top_topics.csv")
