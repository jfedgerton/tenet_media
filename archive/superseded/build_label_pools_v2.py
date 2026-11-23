import argparse, re, logging
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sample2")
SEED = 123
N_PER = 500

# one-sentence verified topics
TOPIC_CODE = {37:0, 58:1, 17:2, 46:3}          # corpus topic -> code
CODE_NAME  = {0:"russia",1:"ukraine",2:"supreme_court",3:"china"}
BT_TOPICS  = {66, 270}                          # big-tech candidate topics (technology, censorship)
RANDOM_CODES = {0,1}                             # russia, ukraine -> simple random
BIG_TECH_PAT = re.compile(r"big tech|silicon valley|section 230|zuckerberg|content moderation|deplatform|shadow ?ban|tech giant|social media compan", re.I)

POS_WORDS = set("good great right strong defend defends defended support supports supported praise praised win wins winning brave hero heroic freedom protect protects protected wise smart honest fair success best love respect admire admirable justified".split())
NEG_WORDS = set("bad wrong corrupt evil weak attack attacks attacked condemn condemns condemned lie lies liar lying fail fails failed failure dangerous threat criminal destroy destroys hate hates illegitimate disaster worst stupid tyranny tyrannical censor censors censorship banned crazy insane".split())
WORDRE = re.compile(r"[a-z']+")
def polarity(s):
    toks = WORDRE.findall(str(s).lower())
    p = sum(t in POS_WORDS for t in toks); n = sum(t in NEG_WORDS for t in toks)
    return "pos" if p>n else ("neg" if n>p else "neu")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    WD = Path(a.window_dir); OUT = Path(a.out_dir); OUT.mkdir(parents=True, exist_ok=True)

    tf = pq.ParquetFile(WD/"topics.parquet")
    N = tf.metadata.num_rows
    log.info("N=%d  building lookup arrays", N)
    target_of = np.full(N, -1, dtype=np.int8)
    is_bt = np.zeros(N, dtype=bool)
    for b in tf.iter_batches(batch_size=8000000, columns=["corpus_index","topic"]):
        ci = b.column("corpus_index").to_numpy()
        tp = b.column("topic").to_numpy()
        for topic, code in TOPIC_CODE.items():
            m = tp==topic
            if m.any(): target_of[ci[m]] = code
        for topic in BT_TOPICS:
            m = tp==topic
            if m.any(): is_bt[ci[m]] = True
    log.info("topic rows: %d ; bt-topic rows: %d", int((target_of>=0).sum()), int(is_bt.sum()))

    cols = ["show","date","episode_number","filename","sentence_id","sentence"]
    pools = {c: [] for c in CODE_NAME.values()}; pools["big_tech"] = []
    cf = pq.ParquetFile(WD/"corpus.parquet")
    pos = 0
    for b in cf.iter_batches(batch_size=1000000, columns=cols):
        n = b.num_rows
        codes = target_of[pos:pos+n]
        btm = is_bt[pos:pos+n]
        fn = b.column("filename").to_pylist()
        sent = b.column("sentence").to_pylist()
        keep = codes>=0
        # big-tech: regex only within bt candidate topics
        bt_hit = np.zeros(n, dtype=bool)
        if btm.any():
            idxs = np.where(btm)[0]
            for i in idxs:
                if BIG_TECH_PAT.search(sent[i] or ""):
                    bt_hit[i] = True
        keep_any = keep | bt_hit
        kp = np.where(keep_any)[0]
        if len(kp):
            show = b.column("show").to_pylist()
            date = b.column("date").to_pylist()
            epn = b.column("episode_number").to_pylist()
            sid = b.column("sentence_id").to_pylist()
            for p in kp:
                prev = sent[p-1] if (p>0 and fn[p-1]==fn[p]) else ""
                nxt  = sent[p+1] if (p<n-1 and fn[p+1]==fn[p]) else ""
                rec = {"show":show[p],"date":date[p],"episode_number":epn[p],"filename":fn[p],
                       "sentence_id":sid[p],"prev_sentence":prev,"sentence":sent[p],"next_sentence":nxt}
                if keep[p]:
                    tname = CODE_NAME[int(codes[p])]; rec["target"]=tname; pools[tname].append(rec)
                if bt_hit[p]:
                    r2 = dict(rec); r2["target"]="big_tech"; pools["big_tech"].append(r2)
        pos += n
    log.info("scanned %d rows", pos)

    summary=[]
    for t, recs in pools.items():
        pool = pd.DataFrame(recs)
        pool = pool.drop_duplicates(["filename","sentence_id"]) if len(pool) else pool
        npool=len(pool)
        if npool==0:
            log.warning("EMPTY pool %s", t); continue
        code = {v:k for k,v in CODE_NAME.items()}.get(t, None)
        if code in RANDOM_CODES:
            samp = pool.sample(n=min(N_PER,npool), random_state=SEED); samp["strata"]="random"
        else:
            pool = pool.copy(); pool["strata"]=pool["sentence"].map(polarity)
            quota={"pos":175,"neg":175,"neu":150}; picks=[]
            for s,q in quota.items():
                g=pool[pool.strata==s]; picks.append(g.sample(n=min(q,len(g)),random_state=SEED))
            samp=pd.concat(picks)
            if len(samp)<N_PER:
                rem=pool.drop(samp.index); samp=pd.concat([samp,rem.sample(n=min(N_PER-len(samp),len(rem)),random_state=SEED)])
        samp=samp.sample(frac=1,random_state=SEED).reset_index(drop=True)
        samp["row_id"]=[f"{t}_{i:04d}" for i in range(len(samp))]
        for c in ["stance","uncodable","confidence","notes"]: samp[c]=""
        outcols=["row_id","target","strata","show","date","episode_number","filename","sentence_id","prev_sentence","sentence","next_sentence","stance","uncodable","confidence","notes"]
        samp[outcols].to_csv(OUT/f"label_{t}.csv", index=False)
        pos_ct = int(pool["strata"].eq("pos").sum()) if "strata" in pool and code not in RANDOM_CODES else -1
        summary.append((t,npool,len(samp),pos_ct)); log.info("target %-14s pool=%d sampled=%d", t, npool, len(samp))
    pd.DataFrame(summary,columns=["target","pool_size","sampled","pool_pos_cue"]).to_csv(OUT/"SUMMARY.csv",index=False)
    log.info("DONE")

if __name__=="__main__":
    main()

