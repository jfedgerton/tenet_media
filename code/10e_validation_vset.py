import os, numpy as np, pandas as pd
import pyarrow.parquet as pq
COLLAB=os.environ["COLLAB"]; OUT=COLLAB+"/data/sc_results"
np.random.seed(123)
SRC=COLLAB+"/data/corpus_with_topics.parquet"
TEN=set(["tim_pool_daily_news","timcast_irl","the_culture_war_podcast_with_tim_pool","the_rubin_report","the_benny_show"])
TREAT=pd.Timestamp("2023-10-01")
TARGETMAP={79:"russia",78:"ukraine",353:"assad"}
KEYS=set(TARGETMAP)
PER_CELL=40  # 3 topics x 2 (tenet/ctrl) x 2 (pre/post) x 40 = 480

# collect candidate sentences (topic in keys, >=6 words) in batches, keep slim
pf=pq.ParquetFile(SRC); cols=["show","date","episode_number","sentence_id","sentence","topic"]
buckets={}  # (topic,is_tenet,period) -> list of rows (reservoir via random sampling at end)
keep=[]
for b in pf.iter_batches(batch_size=3000000,columns=cols):
    df=b.to_pandas(); df=df[df["topic"].isin(KEYS)]
    if len(df)==0: continue
    df=df[df["date"].notna()].copy()
    df["wc"]=df["sentence"].fillna("").str.split().apply(len)
    df=df[df["wc"]>=6]
    if len(df)==0: continue
    df["date"]=pd.to_datetime(df["date"]); df=df[df["date"]>="2018-01-01"]
    df["is_tenet"]=df["show"].isin(TEN).astype(int)
    df["period"]=np.where(df["date"]<TREAT,"pre","post")
    keep.append(df[["show","date","episode_number","sentence_id","sentence","topic","is_tenet","period"]])
cand=pd.concat(keep,ignore_index=True)
print("candidates",len(cand),"by topic",cand["topic"].value_counts().to_dict(),flush=True)

samp=[]
for (tp,it,per),g in cand.groupby(["topic","is_tenet","period"]):
    samp.append(g.sample(min(PER_CELL,len(g)),random_state=123))
s=pd.concat(samp).reset_index(drop=True)
s["target"]=s["topic"].map(TARGETMAP)

# neighbor context: build prev/next within episode from candidate-adjacent — need full episode order, so pull from corpus again per (show,episode)
# cheap approach: re-read just the needed episodes
need=s[["show","episode_number"]].drop_duplicates()
needset=set(map(tuple,need.values))
ctxrows=[]
for b in pf.iter_batches(batch_size=3000000,columns=["show","episode_number","sentence_id","sentence"]):
    df=b.to_pandas()
    df=df[[ (r.show,r.episode_number) in needset for r in df.itertuples()]]
    if len(df): ctxrows.append(df)
ctx=pd.concat(ctxrows,ignore_index=True).sort_values(["show","episode_number","sentence_id"])
ctx["prev_sentence"]=ctx.groupby(["show","episode_number"])["sentence"].shift(1).fillna("")
ctx["next_sentence"]=ctx.groupby(["show","episode_number"])["sentence"].shift(-1).fillna("")
s=s.merge(ctx[["show","episode_number","sentence_id","prev_sentence","next_sentence"]],on=["show","episode_number","sentence_id"],how="left")

s=s.sample(frac=1,random_state=123).reset_index(drop=True)
s.insert(0,"sample_id",["T"+str(i+1).zfill(4) for i in range(len(s))])
for c in ["stance","uncodable","confidence","notes"]: s[c]=""
# blind coding file: target + context + sentence, NO show/date/condition
s[["sample_id","target","prev_sentence","sentence","next_sentence","stance","uncodable","confidence","notes"]].to_csv(OUT+"/stance_validation_set_v2.csv",index=False)
# key kept separate
s[["sample_id","show","is_tenet","date","period","topic","target","episode_number","sentence_id"]].to_csv(OUT+"/stance_validation_KEY_v2.csv",index=False)
print("SAMPLE n",len(s),flush=True)
print(s.groupby(["target","is_tenet","period"]).size().to_dict(),flush=True)
print("DONE_VSET2",flush=True)
