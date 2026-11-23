#!/usr/bin/env python3
"""Assemble per-(coder,condition) training tables + shared human-gold test set.
Sentence text comes from stance_train_1500.csv; labels come from each coder's
condition. Output: bert_data/<coder>_<cond>_train.csv (sample_id,target,sentence,label)
and bert_data/human_gold_test.csv (test_id,target,sentence,human_label)."""
import os, json, glob
import pandas as pd

C = os.environ.get("COLLAB", ".")
OUT = os.path.join(C, "data/sc_results/bert_data"); os.makedirs(OUT, exist_ok=True)

# --- sentence text for the 1500 training rows ---
tr = pd.read_csv(os.path.join(C, "stance_train_1500.csv"))
text = tr.set_index("sample_id")["sentence"].astype(str).to_dict()
TARGETS = ["russia", "ukraine"]

# --- coder label sources ---
def opus_labels():
    """all c0-c9 from full_opus checkpoint; c0 ALSO from patched (headline)."""
    rows = {}
    for f, tag in [("stance_bias_checkpoint_full_opus.jsonl", "full"),
                   ("stance_bias_checkpoint_full_opus_patched.jsonl", "patched")]:
        p = os.path.join(C, f)
        if not os.path.exists(p): continue
        for line in open(p):
            d = json.loads(line)
            cond = d["condition"]
            # patched only has c0 -> use it as the canonical c0 (headline)
            if tag == "patched" and cond != "c0_faithful": continue
            if tag == "full" and cond == "c0_faithful" and \
               os.path.exists(os.path.join(C, "stance_bias_checkpoint_full_opus_patched.jsonl")):
                continue   # prefer patched c0
            rows[(d["sample_id"], d["target"], cond)] = d["label"]
    return rows

def codex_labels():
    d = pd.read_csv(os.path.join(C, "stance_codex_outputs_gpt5mini_minimal/stance_codex_labels_long.csv"))
    return {(r.sample_id, r.target, r.condition): r.label for r in d.itertuples(index=False)}

SOURCES = {"opus": opus_labels(), "codex": codex_labels()}
CONDS = ["c0_faithful","c1_modRU","c2_strongRU","c3_modUA","c4_strongUA",
         "c6_central","c7_extreme","c8_mention_lax","c9_mention_strict"]  # c5_placebo excluded

manifest = []
for coder, lab in SOURCES.items():
    conds_present = sorted({c for (_,_,c) in lab})
    for cond in CONDS:
        if cond not in conds_present:
            print(f"SKIP {coder} {cond}: not in source"); continue
        recs = []
        for (sid, tgt, c), l in lab.items():
            if c != cond: continue
            if sid not in text: continue
            recs.append({"sample_id": sid, "target": tgt, "sentence": text[sid], "label": l})
        df = pd.DataFrame(recs)
        fn = os.path.join(OUT, f"{coder}_{cond}_train.csv")
        df.to_csv(fn, index=False)
        manifest.append({"coder": coder, "condition": cond, "n": len(df),
                         "primary": (coder=="opus" and cond=="c0_faithful")})
        print(f"WROTE {coder}_{cond}_train.csv n={len(df)}")

# --- shared human gold test set (180 rows x 2 targets) ---
gold = []
for f in ["stance_freshtest_60.csv","stance_freshtest2_60.csv","stance_freshtest3_60.csv"]:
    g = pd.read_csv(os.path.join(C, f))
    for r in g.itertuples(index=False):
        for tgt in TARGETS:
            gold.append({"test_id": r.test_id, "target": tgt, "sentence": str(r.sentence),
                         "human_label": str(getattr(r, f"{tgt}_stance")).strip()})
pd.DataFrame(gold).to_csv(os.path.join(OUT, "human_gold_test.csv"), index=False)
print(f"WROTE human_gold_test.csv n={len(gold)} ({len(gold)//2} sentences x 2 targets)")

pd.DataFrame(manifest).to_csv(os.path.join(OUT, "grid_manifest.csv"), index=False)
print(f"GRID CELLS: {len(manifest)}  (DONE_BUILD)")
