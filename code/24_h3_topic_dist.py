"""
20_topic_distribution.py  --  recover the per-sentence topic probabilities needed
for the H3 topic mass-transfer grid (21_h3_topic_grid.py). 6_topic_model.py ran
with calculate_probabilities=False, so only the hard `topic` was saved; here we
reload the fitted BERTopic model and recompute a distribution via
approximate_distribution().

Efficiency: H3 outcomes are a topic's SHARE OF ALL DISCUSSION, so the denominator
is just a sentence count (cheap). Only sentences that can FLIP into/out of the
relevant topics matter, i.e. those whose hard topic is in
  CAND = {78, 79, nn(78), nn(79)}        (nn = nearest-neighbor topic, cosine on topic embeddings)
We compute the distribution only for those, and reduce it to 5 numbers per
sentence that fully determine re-argmax under a 78<->nn78 / 79<->nn79 transfer:
  p78, p79, p_nn78, p_nn79, p_rest_max   (p_rest_max = max prob over all OTHER topics)

Outputs (data/sc_results/):
  topic_neighbors.csv            topic, nearest_neighbor, cos
  h3_ntotal.csv                  unit, month, n_total      (ALL sentences = denominator)
  topic_cand_probs.parquet       show,date,unit,month,hard_topic, p78,p79,p_nn78,p_nn79,p_rest_max

Universe = analysis shows (treated + controls from baseline_panel), 2018-01 .. 2024-09
(truncated at the indictment). PI: Jared Edgerton (PSU). Seed 123.
"""
import os
import numpy as np, pandas as pd
from bertopic import BERTopic
from sklearn.metrics.pairwise import cosine_similarity

SEED = 123
COLLAB = "/storage/group/LiberalArts/default/jfe4_collab/podcast"
SC = COLLAB + "/data/sc_results"
MODEL_DIR = COLLAB + "/data/topic_model"
CORPUS = COLLAB + "/data/corpus_with_topics.parquet"
PANEL = SC + "/baseline_panel.csv"
RELEVANT = [78, 79]
START, TRUNC = pd.Timestamp("2018-01-01"), pd.Timestamp("2024-09-01")
TIM = {"timcast_irl", "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool"}
BATCH = 10_000
np.random.seed(SEED)

print("[load] model", MODEL_DIR)
tm = BERTopic.load(MODEL_DIR)
all_ids = sorted(tm.get_topics().keys())                 # includes -1
topic_ids = [t for t in all_ids if t != -1]              # approximate_distribution column order
col = {t: i for i, t in enumerate(topic_ids)}

# nearest-neighbor topic (cosine on topic embeddings; fall back to c-TF-IDF)
emb = getattr(tm, "topic_embeddings_", None)
if emb is None:
    emb = tm.c_tf_idf_.toarray()
rowid = {t: i for i, t in enumerate(all_ids)}
sim = cosine_similarity(emb)
def nn_of(t):
    order = np.argsort(-sim[rowid[t]])
    return next(all_ids[j] for j in order if all_ids[j] not in (t, -1))
NN = {t: nn_of(t) for t in RELEVANT}
pd.DataFrame([{"topic": t, "nearest_neighbor": NN[t],
               "cos": float(sim[rowid[t], rowid[NN[t]]])} for t in RELEVANT]).to_csv(SC + "/topic_neighbors.csv", index=False)
print("[nn]", NN)
CAND = set(RELEVANT) | set(NN.values())
COLS5 = [78, 79, NN[78], NN[79]]                          # the four tracked topics

# ---- universe ----
units = pd.read_csv(PANEL)["unit"].unique().tolist()
shows = set()
for u in units:
    shows |= TIM if u == "tim_pool" else {u}
df = pd.read_parquet(CORPUS, columns=["show", "date", "sentence_id", "sentence", "topic"])
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df[df["date"].between(START, TRUNC, inclusive="left") & df["show"].isin(shows)].copy()
df["unit"] = np.where(df["show"].isin(TIM), "tim_pool", df["show"])
df["month"] = df["date"].values.astype("datetime64[M]")
print("[universe]", len(df), "sentences,", df["unit"].nunique(), "units")

# ---- denominator: n_total per unit-month (ALL sentences) ----
df.groupby(["unit", "month"]).size().reset_index(name="n_total").to_csv(SC + "/h3_ntotal.csv", index=False)
print("[ntotal] written")

# ---- distribution for candidate sentences only ----
cand = df[df["topic"].isin(CAND)].reset_index(drop=True)
print("[cand]", len(cand), "candidate sentences (topics", CAND, ")")
other_cols = [i for t, i in col.items() if t not in COLS5]
out = np.zeros((len(cand), 5), dtype=np.float32)          # p78,p79,pnn78,pnn79,p_rest_max
for s0 in range(0, len(cand), BATCH):
    s1 = min(s0 + BATCH, len(cand))
    distr, _ = tm.approximate_distribution(cand["sentence"].iloc[s0:s1].tolist(), use_embedding_model=False)
    distr = np.asarray(distr)
    out[s0:s1, 0] = distr[:, col[78]]
    out[s0:s1, 1] = distr[:, col[79]]
    out[s0:s1, 2] = distr[:, col[NN[78]]]
    out[s0:s1, 3] = distr[:, col[NN[79]]]
    out[s0:s1, 4] = distr[:, other_cols].max(axis=1)
    if (s0 // BATCH) % 10 == 0:
        print("  batch", s0, "/", len(cand))
res = cand[["unit", "month", "topic"]].rename(columns={"topic": "hard_topic"}).copy()
res["p78"], res["p79"], res["p_nn78"], res["p_nn79"], res["p_rest_max"] = (out[:, 0], out[:, 1], out[:, 2], out[:, 3], out[:, 4])
res.to_csv(SC + "/topic_cand_probs.csv", index=False)   # CSV so R (no arrow on Roar) can read it
print("[done] wrote topic_cand_probs.csv", len(res), "rows; NN78=%d NN79=%d" % (NN[78], NN[79]))
