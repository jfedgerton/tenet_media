import logging
from pathlib import Path
import numpy as np, pandas as pd
import pyarrow.parquet as pq
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("s3v2"); SEED=123; N_PER=500; TOPIC=9
WD=Path("/storage/group/LiberalArts/default/jfe4_collab/podcast/data/windows/three_sentence")
OUT=Path("/storage/group/LiberalArts/default/jfe4_collab/podcast/data/label_sheets_fixed/three_sentence"); OUT.mkdir(parents=True,exist_ok=True)
tf=pq.ParquetFile(WD/"topics.parquet"); Nt=tf.metadata.num_rows
log.info("topics N=%d", Nt)
is_t=np.zeros(Nt,dtype=bool)
for b in tf.iter_batches(batch_size=8000000,columns=["corpus_index","topic"]):
    ci=b.column("corpus_index").to_numpy(); tp=b.column("topic").to_numpy(); m=tp==TOPIC
    if m.any(): is_t[ci[m]]=True
log.info("topic-9 rows: %d", int(is_t.sum()))
cols=["show","date","episode_number","filename","sentence_id","sentence"]
recs=[]; cf=pq.ParquetFile(WD/"corpus.parquet"); fcount=0; total=0
for b in cf.iter_batches(batch_size=1000000,columns=cols):
    n=b.num_rows; total+=n
    fn=b.column("filename").to_pylist(); sent=b.column("sentence").to_pylist()
    ss=pd.Series(sent).fillna("").astype(str); L=ss.str.strip().str.len().values
    keep=(L==0)|(L>=5); nkeep=int(keep.sum())
    fidx=np.full(n,-1,np.int64); fidx[keep]=np.arange(fcount,fcount+nkeep); fcount+=nkeep
    hit=np.zeros(n,dtype=bool); kr=np.where(keep)[0]; hit[kr]=is_t[fidx[kr]]
    kp=np.where(hit)[0]
    if len(kp):
        show=b.column("show").to_pylist(); date=b.column("date").to_pylist()
        epn=b.column("episode_number").to_pylist(); sid=b.column("sentence_id").to_pylist()
        for p in kp:
            prev=sent[p-1] if (p>0 and fn[p-1]==fn[p]) else ""
            nxt=sent[p+1] if (p<n-1 and fn[p+1]==fn[p]) else ""
            recs.append({"show":show[p],"date":date[p],"episode_number":epn[p],"filename":fn[p],"sentence_id":sid[p],"prev_sentence":prev,"sentence":sent[p],"next_sentence":nxt})
    del ss
log.info("scanned=%d kept=%d topicsN=%d ALIGN_MATCH=%s", total, fcount, Nt, fcount==Nt)
pool=pd.DataFrame(recs).drop_duplicates(["filename","sentence_id"]); log.info("pool=%d", len(pool))
samp=pool.sample(n=min(N_PER,len(pool)),random_state=SEED).sample(frac=1,random_state=SEED).reset_index(drop=True)
samp["target"]="russia_ukraine"; samp["strata"]="random"
samp["row_id"]=[f"russia_ukraine_{i:04d}" for i in range(len(samp))]
for c in ["stance_russia","stance_ukraine","uncodable","confidence","notes"]: samp[c]=""
oc=["row_id","target","strata","show","date","episode_number","filename","sentence_id","prev_sentence","sentence","next_sentence","stance_russia","stance_ukraine","uncodable","confidence","notes"]
samp[oc].to_csv(OUT/"label_russia_ukraine.csv",index=False)
for s in samp["sentence"].head(5).tolist(): log.info("   e.g: %s", str(s)[:110])
log.info("DONE sampled=%d", len(samp))

