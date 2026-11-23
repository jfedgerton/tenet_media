import argparse, re, logging
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sample")
SEED = 123
N_PER = 500

# HARDCODED verified one-sentence target topics
TOPIC_TARGETS = {37: "russia", 58: "ukraine", 17: "supreme_court", 46: "china"}
RANDOM_TARGETS = {"russia", "ukraine"}
STRAT_TARGETS = {"supreme_court", "china", "big_tech"}
BIG_TECH_PAT = re.compile(r"big tech|silicon valley|section 230|zuckerberg|content moderation|deplatform|shadow ?ban|tech giant|social media compan", re.I)

POS_WORDS = set("good great right strong defend defends defended support supports supported praise praised win wins winning brave hero heroic freedom protect protects protected wise smart honest fair success best love respect admire admirable justified".split())
NEG_WORDS = set("bad wrong corrupt evil weak attack attacks attacked condemn condemns condemned lie lies liar lying fail fails failed failure dangerous threat criminal destroy destroys hate hates illegitimate disaster worst stupid tyranny tyrannical censor censors censorship banned crazy insane".split())
WORDRE = re.compile(r"[a-z']+")

def polarity(s):
    toks = WORDRE.findall(str(s).lower())
    p = sum(t in POS_WORDS for t in toks)
    n = sum(t in NEG_WORDS for t in toks)
    return "pos" if p > n else ("neg" if n > p else "neu")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    WD = Path(a.window_dir); OUT = Path(a.out_dir); OUT.mkdir(parents=True, exist_ok=True)

    log.info("Pass A: topic map from topics.parquet")
    idx2t = {}
    tf = pq.ParquetFile(WD / "topics.parquet")
    for b in tf.iter_batches(batch_size=4000000, columns=["corpus_index", "topic"]):
        ci = b.column("corpus_index").to_numpy()
        tp = b.column("topic").to_numpy()
        for topic, tgt in TOPIC_TARGETS.items():
            m = tp == topic
            if m.any():
                idx2t.update(zip(ci[m].tolist(), [tgt] * int(m.sum())))
    log.info("topic-target rows: %d", len(idx2t))

    log.info("Pass B: corpus scan + intra-batch context")
    KEEP = ["target","corpus_index","show","date","filename","sentence_id","sentence","prev_sentence","next_sentence"]
    pools = {t: [] for t in list(TOPIC_TARGETS.values()) + ["big_tech"]}
    cf = pq.ParquetFile(WD / "corpus.parquet")
    pos = 0
    for b in cf.iter_batches(batch_size=500000):
        df = b.to_pandas().reset_index(drop=True)
        n = len(df)
        df["corpus_index"] = range(pos, pos + n)
        fn = df["filename"].values
        sent = df["sentence"].astype(str).values
        prevs = np.array([""] * n, dtype=object)
        nexts = np.array([""] * n, dtype=object)
        if n > 1:
            sp = fn[1:] == fn[:-1]
            prevs[1:][sp] = sent[:-1][sp]
            sn = fn[:-1] == fn[1:]
            nexts[:-1][sn] = sent[1:][sn]
        df["prev_sentence"] = prevs
        df["next_sentence"] = nexts
        df["target"] = df["corpus_index"].map(idx2t)
        for t in TOPIC_TARGETS.values():
            sub = df[df["target"] == t]
            if len(sub):
                pools[t].append(sub[KEEP])
        bt = df["sentence"].astype(str).str.contains(BIG_TECH_PAT, na=False)
        if bt.any():
            sub = df[bt].copy(); sub["target"] = "big_tech"
            pools["big_tech"].append(sub[KEEP])
        pos += n
    log.info("scanned %d rows", pos)

    summary = []
    for t, parts in pools.items():
        pool = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=KEEP)
        pool = pool.drop_duplicates("corpus_index")
        npool = len(pool)
        if t in RANDOM_TARGETS:
            samp = pool.sample(n=min(N_PER, npool), random_state=SEED)
            samp["strata"] = "random"
        else:
            pool = pool.copy()
            pool["strata"] = pool["sentence"].map(polarity)
            quota = {"pos": 175, "neg": 175, "neu": 150}
            picks = []
            for s, q in quota.items():
                g = pool[pool["strata"] == s]
                picks.append(g.sample(n=min(q, len(g)), random_state=SEED))
            samp = pd.concat(picks)
            if len(samp) < N_PER:
                rem = pool.drop(samp.index)
                samp = pd.concat([samp, rem.sample(n=min(N_PER - len(samp), len(rem)), random_state=SEED)])
        samp = samp.sample(frac=1, random_state=SEED).reset_index(drop=True)
        samp["row_id"] = [f"{t}_{i:04d}" for i in range(len(samp))]
        for c in ["stance", "uncodable", "confidence", "notes"]:
            samp[c] = ""
        cols = ["row_id","target","strata","show","date","filename","sentence_id","prev_sentence","sentence","next_sentence","stance","uncodable","confidence","notes"]
        samp[cols].to_csv(OUT / f"label_{t}.csv", index=False)
        pos_ct = int((pool["strata"].eq("pos").sum())) if t in STRAT_TARGETS else -1
        summary.append((t, npool, len(samp), pos_ct))
        log.info("target %-14s pool=%d sampled=%d", t, npool, len(samp))
    pd.DataFrame(summary, columns=["target","pool_size","sampled","pool_pos_cue"]).to_csv(OUT / "SUMMARY.csv", index=False)
    log.info("DONE")

if __name__ == "__main__":
    main()

