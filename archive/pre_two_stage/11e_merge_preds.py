"""
merge_predsfp.py  --  merge the 4-class softmax inference shards into ONE
sentence-level CSV that the probability-shift grid (R) consumes.

Input : data/sc_results/bert_out/opus_c0_faithful/predsfp_shard*.parquet
        (written by bert_train_infer_fp.py; full 4-class softmax per target)
Output: data/sc_results/probs_4class.csv
        columns: show, date, episode_number, sentence_id, topic,
                 russia_label, russia_p_pos, russia_p_neg, russia_p_neu, russia_p_unment,
                 ukraine_label, ukraine_p_pos, ukraine_p_neg, ukraine_p_neu, ukraine_p_unment

R lacks `arrow` on Roar, so the bridge is a CSV. ~444K rows is small for fread.
PI: Jared Edgerton (PSU).
"""
import glob, os, sys
import pandas as pd

COLLAB = "/storage/group/LiberalArts/default/jfe4_collab/podcast"
SC = COLLAB + "/data/sc_results"
IND = SC + "/bert_out/opus_c0_faithful"

shards = sorted(glob.glob(IND + "/predsfp_shard*.parquet"))
print("FOUND", len(shards), "shards")
if len(shards) == 0:
    sys.exit("no predsfp shards yet")

keep = ["show", "date", "episode_number", "sentence_id", "topic",
        "russia_label", "russia_p_pos", "russia_p_neg", "russia_p_neu", "russia_p_unment",
        "ukraine_label", "ukraine_p_pos", "ukraine_p_neg", "ukraine_p_neu", "ukraine_p_unment"]

parts = []
for f in shards:
    d = pd.read_parquet(f)
    have = [c for c in keep if c in d.columns]
    parts.append(d[have])
df = pd.concat(parts, ignore_index=True)
print("ROWS", len(df), "COLS", list(df.columns))

# sanity: 4 probs should sum to ~1 per target
for tgt in ("russia", "ukraine"):
    cols = [f"{tgt}_p_pos", f"{tgt}_p_neg", f"{tgt}_p_neu", f"{tgt}_p_unment"]
    if all(c in df.columns for c in cols):
        s = df[cols].sum(axis=1)
        print(f"{tgt} prob-sum mean={s.mean():.4f} min={s.min():.4f} max={s.max():.4f}")

out = SC + "/probs_4class.csv"
df.to_csv(out, index=False)
print("WROTE", out, os.path.getsize(out) // (1024*1024), "MB")

# also write the labeled PARQUET that the panel builders read (12_build_panels, 19_loso_panel):
# same rows, with the discrete labels + per-class probs the panels consume.
labeled = SC + "/opus_c0_corpus_labeled.parquet"
df.to_parquet(labeled, index=False)
print("WROTE", labeled)
print("MERGE_DONE")
