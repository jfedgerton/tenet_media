"""11w_build_disney_pool.py -- build the Disney placebo label pool (missing from the
July build_label_pools_v3 run). Mirrors the big_tech regex path exactly: stream the
one_sentence corpus, collect regex matches with prev/next context, polarity-balance
175 pos / 175 neg / 150 neu (fill remainder at random), N=500, seed 123.
Writes label_sheets_fixed/one_sentence/label_disney.csv with the v3 schema.
"""
import re, logging
from pathlib import Path
import numpy as np, pandas as pd
import pyarrow.parquet as pq
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("disney")
SEED = 123; N_PER = 500
P = '/storage/group/LiberalArts/default/jfe4_collab/podcast'
WD = Path(P + '/data/windows/one_sentence')
OUT = Path(P + '/data/label_sheets_fixed/one_sentence')
DISNEY_PAT = re.compile(r"disney|pixar|\biger\b", re.I)
POS_WORDS = set("good great right strong defend defends defended support supports supported praise praised win wins winning brave hero heroic freedom protect protects protected wise smart honest fair success best love respect admire admirable justified".split())
NEG_WORDS = set("bad wrong corrupt evil weak attack attacks attacked condemn condemns condemned lie lies liar lying fail fails failed failure dangerous threat criminal destroy destroys hate hates illegitimate disaster worst stupid tyranny tyrannical censor censors censorship banned crazy insane".split())
WORDRE = re.compile(r"[a-z']+")
def polarity(s):
    toks = WORDRE.findall(str(s).lower()); p = sum(t in POS_WORDS for t in toks); n = sum(t in NEG_WORDS for t in toks)
    return "pos" if p > n else ("neg" if n > p else "neu")

cols = ["show", "date", "episode_number", "filename", "sentence_id", "sentence"]
pf = pq.ParquetFile(WD / "corpus.parquet")
recs, total = [], 0
for bi, b in enumerate(pf.iter_batches(batch_size=1000000, columns=cols)):
    n = b.num_rows; total += n
    fn = b.column("filename").to_pylist(); sent = b.column("sentence").to_pylist()
    ss = pd.Series(sent).fillna("").astype(str)
    hit = ss.str.contains(DISNEY_PAT, regex=True, na=False).values
    kp = np.where(hit)[0]
    if len(kp):
        show = b.column("show").to_pylist(); date = b.column("date").to_pylist()
        epn = b.column("episode_number").to_pylist(); sid = b.column("sentence_id").to_pylist()
        for p in kp:
            prev = sent[p-1] if (p > 0 and fn[p-1] == fn[p]) else ""
            nxt = sent[p+1] if (p < n-1 and fn[p+1] == fn[p]) else ""
            recs.append({"show": show[p], "date": date[p], "episode_number": epn[p], "filename": fn[p], "sentence_id": sid[p], "prev_sentence": prev, "sentence": sent[p], "next_sentence": nxt})
    if bi % 20 == 0: log.info("batch %d total %d hits %d", bi, total, len(recs))

pool = pd.DataFrame(recs).drop_duplicates(["filename", "sentence_id"])
pool["target"] = "disney"
log.info("pool %d", len(pool))
pool["strata"] = pool["sentence"].map(polarity)
picks = []
for s, q in {"pos": 175, "neg": 175, "neu": 150}.items():
    g = pool[pool["strata"] == s]; picks.append(g.sample(n=min(q, len(g)), random_state=SEED))
samp = pd.concat(picks)
if len(samp) < N_PER:
    rem = pool.drop(samp.index); samp = pd.concat([samp, rem.sample(n=min(N_PER - len(samp), len(rem)), random_state=SEED)])
samp = samp.sample(frac=1, random_state=SEED).reset_index(drop=True)
samp["row_id"] = ["disney_%04d" % i for i in range(len(samp))]
for c in ["stance", "uncodable", "confidence", "notes"]: samp[c] = ""
oc = ["row_id", "target", "strata", "show", "date", "episode_number", "filename", "sentence_id", "prev_sentence", "sentence", "next_sentence", "stance", "uncodable", "confidence", "notes"]
samp[oc].to_csv(OUT / "label_disney.csv", index=False)
log.info("TARGET disney pool=%d sampled=%d DONE_11W", len(pool), len(samp))
