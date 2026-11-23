import argparse, re, logging
from pathlib import Path
import numpy as np, pandas as pd
import pyarrow.parquet as pq
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("v3")
SEED=123; N_PER=500
TOPIC_CODE={37:0,58:1,17:2,46:3}
CODE_NAME={0:"russia",1:"ukraine",2:"supreme_court",3:"china"}
RANDOM_CODES={0,1}
BIG_TECH_PAT=re.compile(r"big tech|silicon valley|section 230|zuckerberg|content moderation|deplatform|shadow ?ban|tech giant|social media compan", re.I)
POS_WORDS=set("good great right strong defend defends defended support supports supported praise praised win wins winning brave hero heroic freedom protect protects protected wise smart honest fair success best love respect admire admirable justified".split())
NEG_WORDS=set("bad wrong corrupt evil weak attack attacks attacked condemn condemns condemned lie lies liar lying fail fails failed failure dangerous threat criminal destroy destroys hate hates illegitimate disaster worst stupid tyranny tyrannical censor censors censorship banned crazy insane".split())
WORDRE=re.compile(r"[a-z']+")
def polarity(s):
    toks=WORDRE.findall(str(s).lower()); p=sum(t in POS_WORDS for t in toks); n=sum(t in NEG_WORDS for t in toks)
    return "pos" if p>n else ("neg" if n>p else "neu")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--window-dir",required=True); ap.add_argument("--out-dir",required=True)
    a=ap.parse_args(); WD=Path(a.window_dir); OUT=Path(a.out_dir); OUT.mkdir(parents=True,exist_ok=True)
    tf=pq.ParquetFile(WD/"topics.parquet"); Nt=tf.metadata.num_rows
    log.info("topics N=%d ; building target_of", Nt)
    target_of=np.full(Nt,-1,np.int8)
    for b in tf.iter_batches(batch_size=8000000, columns=["corpus_index","topic"]):
        ci=b.column("corpus_index").to_numpy(); tp=b.column("topic").to_numpy()
        for topic,code in TOPIC_CODE.items():
            m=tp==topic
            if m.any(): target_of[ci[m]]=code
    log.info("topic-target rows: %d", int((target_of>=0).sum()))
    cols=["show","date","episode_number","filename","sentence_id","sentence"]
    pools={c:[] for c in CODE_NAME.values()}; pools["big_tech"]=[]
    cf=pq.ParquetFile(WD/"corpus.parquet"); fcount=0; total=0
    for b in cf.iter_batches(batch_size=1000000, columns=cols):
        n=b.num_rows; total+=n
        fn=b.column("filename").to_pylist(); sent=b.column("sentence").to_pylist()
        ss=pd.Series(sent).fillna("").astype(str)
        L=ss.str.strip().str.len().values
        keep=(L==0)|(L>=5)                      # EXACT 06_topic_model filter
        nkeep=int(keep.sum())
        fidx=np.full(n,-1,np.int64); fidx[keep]=np.arange(fcount,fcount+nkeep); fcount+=nkeep
        codes=np.full(n,-1,np.int8); kr=np.where(keep)[0]; codes[kr]=target_of[fidx[kr]]
        bt=ss.str.contains(BIG_TECH_PAT, regex=True, na=False).values
        kp=np.where((codes>=0)|bt)[0]
        if len(kp):
            show=b.column("show").to_pylist(); date=b.column("date").to_pylist()
            epn=b.column("episode_number").to_pylist(); sid=b.column("sentence_id").to_pylist()
            for p in kp:
                prev=sent[p-1] if (p>0 and fn[p-1]==fn[p]) else ""
                nxt=sent[p+1] if (p<n-1 and fn[p+1]==fn[p]) else ""
                rec={"show":show[p],"date":date[p],"episode_number":epn[p],"filename":fn[p],"sentence_id":sid[p],"prev_sentence":prev,"sentence":sent[p],"next_sentence":nxt}
                if codes[p]>=0:
                    t=CODE_NAME[int(codes[p])]; r=dict(rec); r["target"]=t; pools[t].append(r)
                if bt[p]:
                    r=dict(rec); r["target"]="big_tech"; pools["big_tech"].append(r)
    log.info("scanned=%d  kept(filtered)=%d  topicsN=%d  ALIGN_MATCH=%s", total, fcount, Nt, fcount==Nt)
    for t, recs in pools.items():
        pool=pd.DataFrame(recs).drop_duplicates(["filename","sentence_id"]); npool=len(pool)
        if npool==0: log.warning("EMPTY %s", t); continue
        code={v:k for k,v in CODE_NAME.items()}.get(t,None)
        if code in RANDOM_CODES:
            samp=pool.sample(n=min(N_PER,npool),random_state=SEED); samp["strata"]="random"
        else:
            pool=pool.copy(); pool["strata"]=pool["sentence"].map(polarity)
            picks=[]
            for s,q in {"pos":175,"neg":175,"neu":150}.items():
                g=pool[pool["strata"]==s]; picks.append(g.sample(n=min(q,len(g)),random_state=SEED))
            samp=pd.concat(picks)
            if len(samp)<N_PER:
                rem=pool.drop(samp.index); samp=pd.concat([samp,rem.sample(n=min(N_PER-len(samp),len(rem)),random_state=SEED)])
        samp=samp.sample(frac=1,random_state=SEED).reset_index(drop=True)
        samp["row_id"]=[f"{t}_{i:04d}" for i in range(len(samp))]
        for c in ["stance","uncodable","confidence","notes"]: samp[c]=""
        oc=["row_id","target","strata","show","date","episode_number","filename","sentence_id","prev_sentence","sentence","next_sentence","stance","uncodable","confidence","notes"]
        samp[oc].to_csv(OUT/f"label_{t}.csv", index=False)
        log.info("TARGET %-14s pool=%d sampled=%d", t, npool, len(samp))
        for s in samp["sentence"].head(4).tolist(): log.info("    e.g: %s", str(s)[:110])
    log.info("DONE")

if __name__=="__main__": main()

