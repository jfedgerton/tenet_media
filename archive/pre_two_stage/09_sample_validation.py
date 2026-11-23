import os, numpy as np, pandas as pd
import pyarrow.parquet as pq
COLLAB=os.environ["COLLAB"]; OUT=COLLAB+"/data/sc_results"
np.random.seed(123)
SRC=COLLAB+"/data/corpus_with_topics.parquet"
KEYS={78,79}
N=1500
# pass 1: collect candidate sentences in topics 78/79 with >=6 words
keep=[]
pf=pq.ParquetFile(SRC)
for b in pf.iter_batches(batch_size=3000000,columns=["show","date","episode_number","sentence_id","sentence","topic"]):
    df=b.to_pandas(); df=df[df["topic"].isin(KEYS)]
    if len(df)==0: continue
    df=df[df["date"].notna()].copy()
    df["wc"]=df["sentence"].fillna("").str.split().apply(len)
    df=df[df["wc"]>=6]
    if len(df): keep.append(df[["show","date","episode_number","sentence_id","sentence","topic"]])
cand=pd.concat(keep,ignore_index=True)
print("candidates",len(cand),"by topic",cand["topic"].value_counts().to_dict(),flush=True)
# random 1500
s=cand.sample(min(N,len(cand)),random_state=123).reset_index(drop=True)
# neighbor context (pass 2, only needed episodes)
need=set(zip(s["show"],s["episode_number"]))
ctxrows=[]
for b in pf.iter_batches(batch_size=3000000,columns=["show","episode_number","sentence_id","sentence"]):
    bb=b.to_pandas(); bb=bb[[ (r.show,r.episode_number) in need for r in bb.itertuples()]]
    if len(bb): ctxrows.append(bb)
ctx=pd.concat(ctxrows,ignore_index=True).sort_values(["show","episode_number","sentence_id"])
ctx["prev_sentence"]=ctx.groupby(["show","episode_number"])["sentence"].shift(1).fillna("")
ctx["next_sentence"]=ctx.groupby(["show","episode_number"])["sentence"].shift(-1).fillna("")
s=s.merge(ctx[["show","episode_number","sentence_id","prev_sentence","next_sentence"]],on=["show","episode_number","sentence_id"],how="left")
s=s.sample(frac=1,random_state=123).reset_index(drop=True)
s.insert(0,"sample_id",["C"+str(i+1).zfill(4) for i in range(len(s))])
# coding columns: BOTH axes, blank
s["russia_stance"]=""; s["ukraine_stance"]=""; s["notes"]=""
# coding file: context + sentence + both axes (no show/date/condition)
s[["sample_id","prev_sentence","sentence","next_sentence","russia_stance","ukraine_stance","notes"]].to_csv(OUT+"/stance_train_1500.csv",index=False)
# key kept separate
s[["sample_id","show","date","episode_number","sentence_id","topic"]].to_csv(OUT+"/stance_train_1500_KEY.csv",index=False)
print("WROTE n",len(s),flush=True)
print("DONE_1500",flush=True)
