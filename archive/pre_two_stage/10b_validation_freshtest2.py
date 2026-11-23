import os, numpy as np, pandas as pd
import pyarrow.parquet as pq
COLLAB=os.environ["COLLAB"]; OUT=COLLAB+"/data/sc_results"
np.random.seed(20260615+2)
SRC=COLLAB+"/data/corpus_with_topics.parquet"
KEYS={78,79}; N=60
# exclude original 1500 AND first fresh 60
excl=set()
prev=pd.read_csv(OUT+"/stance_train_1500_KEY.csv")
excl|=set(zip(prev["show"],prev["episode_number"],prev["sentence_id"]))
f1=pd.read_csv(OUT+"/stance_freshtest_60_KEY.csv")
excl|=set(zip(f1["show"],f1["episode_number"],f1["sentence_id"]))
print("excluding",len(excl),"prior rows",flush=True)
keep=[]
pf=pq.ParquetFile(SRC)
for b in pf.iter_batches(batch_size=3000000,columns=["show","date","episode_number","sentence_id","sentence","topic"]):
    df=b.to_pandas(); df=df[df["topic"].isin(KEYS)]
    if len(df)==0: continue
    df=df[df["date"].notna()].copy()
    df["wc"]=df["sentence"].fillna("").str.split().apply(len)
    df=df[df["wc"]>=6]
    k=list(zip(df["show"],df["episode_number"],df["sentence_id"]))
    df=df[[kk not in excl for kk in k]]
    if len(df): keep.append(df[["show","date","episode_number","sentence_id","sentence","topic"]])
cand=pd.concat(keep,ignore_index=True)
print("fresh2 candidate pool:",len(cand),flush=True)
s=cand.sample(N,random_state=20260617).reset_index(drop=True)
need=set(zip(s["show"],s["episode_number"]))
ctxrows=[]
for b in pf.iter_batches(batch_size=3000000,columns=["show","episode_number","sentence_id","sentence"]):
    bb=b.to_pandas(); bb=bb[[ (r.show,r.episode_number) in need for r in bb.itertuples()]]
    if len(bb): ctxrows.append(bb)
ctx=pd.concat(ctxrows,ignore_index=True).sort_values(["show","episode_number","sentence_id"])
ctx["prev_sentence"]=ctx.groupby(["show","episode_number"])["sentence"].shift(1).fillna("")
ctx["next_sentence"]=ctx.groupby(["show","episode_number"])["sentence"].shift(-1).fillna("")
s=s.merge(ctx[["show","episode_number","sentence_id","prev_sentence","next_sentence"]],on=["show","episode_number","sentence_id"],how="left")
s=s.sample(frac=1,random_state=20260617).reset_index(drop=True)
s.insert(0,"test_id",["U"+str(i+1).zfill(3) for i in range(len(s))])
s["russia_stance"]=""; s["ukraine_stance"]=""; s["notes"]=""
s[["test_id","prev_sentence","sentence","next_sentence","russia_stance","ukraine_stance","notes"]].to_csv(OUT+"/stance_freshtest2_60.csv",index=False)
s[["test_id","show","date","episode_number","sentence_id","topic"]].to_csv(OUT+"/stance_freshtest2_60_KEY.csv",index=False)
print("WROTE stance_freshtest2_60.csv (",len(s),"rows ); topic:",dict(s["topic"].value_counts()),flush=True)
print("DONE_FRESH2",flush=True)
