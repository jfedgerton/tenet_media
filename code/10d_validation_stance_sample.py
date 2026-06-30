import os, numpy as np, pandas as pd
import pyarrow.parquet as pq
COLLAB=os.environ["COLLAB"]; OUT=COLLAB+"/data/sc_results"
np.random.seed(123)
SRC=COLLAB+"/data/russia_corpus.parquet"
TEN=set(["tim_pool_daily_news","timcast_irl","the_culture_war_podcast_with_tim_pool","the_rubin_report","the_benny_show","benny_johnson_arena"])
TREAT=pd.Timestamp("2023-10-01")
df=pq.read_table(SRC,columns=["show","date","episode_number","sentence_id","sentence"]).to_pandas()
df=df[df["date"].notna()].copy()
df["date"]=pd.to_datetime(df["date"])
df=df[df["date"]>="2018-01-01"]
df["is_tenet"]=df["show"].isin(TEN).astype(int)
df["period"]=np.where(df["date"]<TREAT,"pre","post")
df["wc"]=df["sentence"].fillna("").str.split().apply(len)
cand=df[df["wc"]>=6]
samp=[]
for (it,per),g in cand.groupby(["is_tenet","period"]):
    samp.append(g.sample(min(125,len(g)),random_state=123))
s=pd.concat(samp)
# neighbor context via vectorized merge (no giant dict): sort full df once, use positional shift within episode
df=df.sort_values(["show","episode_number","sentence_id"]).reset_index(drop=True)
df["prev_sentence"]=df.groupby(["show","episode_number"])["sentence"].shift(1).fillna("")
df["next_sentence"]=df.groupby(["show","episode_number"])["sentence"].shift(-1).fillna("")
ctx=df[["show","episode_number","sentence_id","prev_sentence","next_sentence"]]
s=s.merge(ctx,on=["show","episode_number","sentence_id"],how="left")
s=s.sample(frac=1,random_state=123).reset_index(drop=True)
s.insert(0,"sample_id",["S"+str(i+1).zfill(4) for i in range(len(s))])
for c in ["stance","narr_NATO_provoked","narr_ukraine_corrupt_nazi","narr_sanctions_backfire","narr_zelensky_illegitimate","narr_stop_aid","narr_russia_winning","narr_conspiracy","narr_peace_now_proRU","uncodable","confidence","notes"]:
    s[c]=""
s[["sample_id","show","is_tenet","date","period","episode_number","sentence_id"]].to_csv(OUT+"/stance_validation_KEY.csv",index=False)
s[["sample_id","prev_sentence","sentence","next_sentence","stance","narr_NATO_provoked","narr_ukraine_corrupt_nazi","narr_sanctions_backfire","narr_zelensky_illegitimate","narr_stop_aid","narr_russia_winning","narr_conspiracy","narr_peace_now_proRU","uncodable","confidence","notes"]].to_csv(OUT+"/stance_validation_set.csv",index=False)
print("SAMPLE n",len(s),flush=True)
print(s.groupby(["is_tenet","period"]).size().to_dict(),flush=True)
print("DONE_SAMPLE",flush=True)
