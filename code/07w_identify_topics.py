import argparse, logging
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("identify")
RUSSIA_PAT = "russia|russian|ukrain|putin|kyiv|kiev|donbas|crimea|zelensky|moscow|kremlin|soviet"
PLACEBO_PAT = {
    "immigration": "immigr|border|migrant|asylum",
    "abortion": "abortion|pro-life|pro life|roe",
    "covid_vaccine": "covid|vaccine|vaccinat|pandemic|lockdown",
    "cancel_culture": "cancel|woke|censor",
    "gender_trans": "transgender|gender|pronoun|nonbinary",
    "supreme_court": "supreme court|scotus|court ruling",
    "china": "china|chinese|ccp|beijing",
    "syria": "syria|assad|damascus|aleppo",
}
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-dir", required=True)
    a = ap.parse_args()
    WD = Path(a.window_dir)
    ti = pd.read_csv(WD / "topic_info.csv")
    namecol = next(c for c in ["Name", "Representation", "CustomName"] if c in ti.columns)
    ti = ti[ti["Topic"] >= 0].copy()
    names = ti[namecol].astype(str)
    russia_topics = set(ti.loc[names.str.contains(RUSSIA_PAT, case=False, regex=True), "Topic"])
    log.info("RUSSIA/UKRAINE topics: %s", sorted(russia_topics))
    rows = [(t, "russia") for t in russia_topics]
    for label, pat in PLACEBO_PAT.items():
        hits = set(ti.loc[names.str.contains(pat, case=False, regex=True), "Topic"])
        rows += [(t, label) for t in hits]
        log.info("placebo %-14s: %s", label, sorted(hits))
    pd.DataFrame(rows, columns=["topic", "label"]).to_csv(WD / "topic_labels.csv", index=False)
    topics = pd.read_parquet(WD / "topics.parquet")
    topic_idx = set(topics.loc[topics.topic.isin(russia_topics), "corpus_index"])
    log.info("russia-topic docs: %d", len(topic_idx))
    pf = pq.ParquetFile(WD / "corpus.parquet")
    chunks, pos = [], 0
    for i, b in enumerate(pf.iter_batches(batch_size=500000)):
        df = b.to_pandas().reset_index(drop=True)
        df["corpus_index"] = range(pos, pos + len(df))
        pos += len(df)
        in_kw = df.sentence.astype(str).str.contains(RUSSIA_PAT, case=False, regex=True, na=False)
        in_topic = df.corpus_index.isin(topic_idx)
        keep = in_kw | in_topic
        if keep.any():
            sub = df.loc[keep].copy()
            sub["from_topic"] = in_topic[keep].values
            sub["from_keyword"] = in_kw[keep].values
            chunks.append(sub)
    res = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
    res.to_parquet(WD / "russia_corpus.parquet", index=False)
    log.info("RUSSIA CLASS: %d docs", len(res))
if __name__ == "__main__":
    main()
