import logging
from pathlib import Path
import numpy as np, pandas as pd
import pyarrow.parquet as pq
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("s3")
SEED=123; N_PER=500
WD=Path("/storage/group/LiberalArts/default/jfe4_collab/podcast/data/windows/three_sentence")
OUT=Path("/storage/group/LiberalArts/default/jfe4_collab/podcast/data/label_sheets/three_sentence"); OUT.mkdir(parents=True,exist_ok=True)
TOPIC=9  # combined russia/ukraine at 3-sentence
tf=pq.ParquetFile(WD/"topics.parquet"); N=tf.metadata.num_rows
log.info("N=%d",N)
keeparr=np.zeros(N,dtype=bool)
for b in tf.iter_batches(batch_size=8000000,columns=["corpus_index","topic"]):
    ci=b.column("corpus_index").to_numpy(); tp=b.column("topic").to_numpy()
    m=tp==TOPIC
    if m.any(): keeparr[ci[m]]=True
log.info("topic-9 rows: %d", int(keeparr.sum()))
cols=["show","date","episode_number","filename","sentence_id","sentence"]
recs=[]; cf=pq.ParquetFile(WD/"corpus.parquet"); pos=0
for b in cf.iter_batches(batch_size=1000000,columns=cols):
    n=b.num_rows; km=keeparr[pos:pos+n]; kp=np.where(km)[0]
    if len(kp):
        fn=b.column("filename").to_pylist(); sent=b.column("sentence").to_pylist()
        show=b.column("show").to_pylist(); date=b.column("date").to_pylist()
        epn=b.column("episode_number").to_pylist(); sid=b.column("sentence_id").to_pylist()
        for p in kp:
            prev=sent[p-1] if (p>0 and fn[p-1]==fn[p]) else ""
            nxt=sent[p+1] if (p<n-1 and fn[p+1]==fn[p]) else ""
            recs.append({"show":show[p],"date":date[p],"episode_number":epn[p],"filename":fn[p],"sentence_id":sid[p],"prev_sentence":prev,"sentence":sent[p],"next_sentence":nxt})
    pos+=n
pool=pd.DataFrame(recs).drop_duplicates(["filename","sentence_id"])
log.info("pool=%d",len(pool))
samp=pool.sample(n=min(N_PER,len(pool)),random_state=SEED).sample(frac=1,random_state=SEED).reset_index(drop=True)
samp["target"]="russia_ukraine"; samp["strata"]="random"
samp["row_id"]=[f"russia_ukraine_{i:04d}" for i in range(len(samp))]
for c in ["stance_russia","stance_ukraine","uncodable","confidence","notes"]: samp[c]=""
outcols=["row_id","target","strata","show","date","episode_number","filename","sentence_id","prev_sentence","sentence","next_sentence","stance_russia","stance_ukraine","uncodable","confidence","notes"]
samp[outcols].to_csv(OUT/"label_russia_ukraine.csv",index=False)
pd.DataFrame([("russia_ukraine",len(pool),len(samp))],columns=["target","pool_size","sampled"]).to_csv(OUT/"SUMMARY.csv",index=False)
log.info("DONE pool=%d sampled=%d",len(pool),len(samp))

