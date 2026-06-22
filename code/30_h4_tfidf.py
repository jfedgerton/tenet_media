"""clean_tfidf.py -- H4 companion: topic-level TF-IDF distinctive topics per Tenet
feed, with sponsor/ad-read and filler topics removed. Run as a job (corpus read
is memory-heavy). Output: data/sc_results/h4_tfidf_clean.csv
PI: Jared Edgerton (PSU)."""
import re
import numpy as np, pandas as pd

CO = "/storage/group/LiberalArts/default/jfe4_collab/podcast"
SC = CO + "/data/sc_results"
FEEDS = ["the_benny_show", "the_rubin_report", "timcast_irl",
         "tim_pool_daily_news", "the_culture_war_podcast_with_tim_pool"]
JUNK = re.compile(r"promo|code|slash|com slash|download|bleacher|staying connected|"
                  r"know mean|mean know|miss moment|sponsor|discount|today miss", re.I)

df = pd.read_parquet(CO + "/data/corpus_with_topics.parquet", columns=["show", "topic"])
df = df[(df.topic != -1) & (df["show"].isin(FEEDS) | True)]   # keep all shows for IDF
ti = pd.read_csv(CO + "/data/topic_model/topic_info.csv")
namecol = "Name" if "Name" in ti.columns else ti.columns[-1]
nm = dict(zip(ti.iloc[:, 0], ti[namecol].astype(str)))
junk_topics = {t for t, n in nm.items() if JUNK.search(str(n))}
print("dropping", len(junk_topics), "sponsor/filler topics")
df = df[~df.topic.isin(junk_topics)]

ST = df.groupby(["show", "topic"]).size().unstack(fill_value=0)   # shows x topics (all shows = doc set)
TF = ST.div(ST.sum(1), axis=0)
IDF = np.log(len(ST) / (1.0 + (ST > 0).sum(0)))
TFIDF = TF * IDF

recs = []
for s in FEEDS:
    if s not in TFIDF.index:
        continue
    top = TFIDF.loc[s].sort_values(ascending=False).head(5)
    for rank, (tp, v) in enumerate(top.items(), 1):
        recs.append((s, rank, int(tp), round(float(v), 5), nm.get(tp, "")))
pd.DataFrame(recs, columns=["show", "rank", "topic", "tfidf", "name"]).to_csv(SC + "/h4_tfidf_clean.csv", index=False)
print("CLEANDONE", len(recs))
