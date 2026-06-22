#!/usr/bin/env python3
"""One array task = one (coder,condition) cell. Fine-tune RoBERTa per target on
that cell's labels, validate vs human gold, infer over all topic-78/79 sentences.
Outputs: bert_out/<cell>/preds.parquet (sample-level label+probs+ordinal),
         bert_out/<cell>/val.csv (kappa vs gold per target).
Pure torch (no datasets/accelerate). CPU or GPU (auto)."""
import os, sys, json, glob
import numpy as np, pandas as pd
import torch, torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sklearn.metrics import cohen_kappa_score

C = os.environ["COLLAB"]
BD = os.path.join(C, "data/sc_results/bert_data")
OUTROOT = os.path.join(C, "data/sc_results/bert_out"); os.makedirs(OUTROOT, exist_ok=True)
MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"  # cached, offline
LABELS = ["positive","negative","neutral","unmentioned"]
L2I = {l:i for i,l in enumerate(LABELS)}
ORD = {"positive":1.0,"neutral":0.0,"negative":-1.0,"unmentioned":np.nan}  # signed stance; unmentioned dropped from mean
TARGETS = ["russia","ukraine"]
SEED=123; EPOCHS=4; BS=16; LR=2e-5; MAXLEN=128
torch.manual_seed(SEED); np.random.seed(SEED)
DEV = "cuda" if torch.cuda.is_available() else "cpu"

manifest = pd.read_csv(os.path.join(BD,"grid_manifest.csv"))
idx = int(os.environ.get("SLURM_ARRAY_TASK_ID", sys.argv[1] if len(sys.argv)>1 else 0))
row = manifest.iloc[idx]
coder, cond = row["coder"], row["condition"]
cell = f"{coder}_{cond}"
OUT = os.path.join(OUTROOT, cell); os.makedirs(OUT, exist_ok=True)
if os.path.exists(os.path.join(OUT,"DONE")):
    print(cell,"already done"); sys.exit(0)
print(f"CELL {idx}: {cell} on {DEV}", flush=True)

tok = AutoTokenizer.from_pretrained(MODEL)
train = pd.read_csv(os.path.join(BD, f"{cell}_train.csv"))
gold  = pd.read_csv(os.path.join(BD, "human_gold_test.csv"))

# add prev/next? keep it simple: train on sentence only (matches LLM "code the sentence")
class DS(Dataset):
    def __init__(s, texts, labels=None):
        s.t=list(texts); s.y=labels
    def __len__(s): return len(s.t)
    def __getitem__(s,i):
        e=tok(s.t[i],truncation=True,max_length=MAXLEN,padding="max_length",return_tensors="pt")
        item={k:v.squeeze(0) for k,v in e.items()}
        if s.y is not None: item["labels"]=torch.tensor(s.y[i])
        return item

val_rows=[]; pred_frames=[]
for tgt in TARGETS:
    tr=train[train.target==tgt].dropna(subset=["label","sentence"])
    tr=tr[tr.label.isin(LABELS)]
    y=[L2I[l] for l in tr.label]
    model=AutoModelForSequenceClassification.from_pretrained(
        MODEL,num_labels=4,ignore_mismatched_sizes=True).to(DEV)
    opt=torch.optim.AdamW(model.parameters(),lr=LR)
    dl=DataLoader(DS(tr.sentence.tolist(),y),batch_size=BS,shuffle=True)
    model.train()
    for ep in range(EPOCHS):
        tot=0
        for b in dl:
            opt.zero_grad()
            lb=b.pop("labels").to(DEV)
            out=model(**{k:v.to(DEV) for k,v in b.items()},labels=lb)
            out.loss.backward(); opt.step(); tot+=out.loss.item()
        print(f"  {tgt} ep{ep+1} loss={tot/len(dl):.3f}",flush=True)
    # validate vs human gold
    model.eval()
    g=gold[gold.target==tgt]
    def predict(texts):
        probs=[]
        dl2=DataLoader(DS(list(texts)),batch_size=64)
        with torch.no_grad():
            for b in dl2:
                lo=model(**{k:v.to(DEV) for k,v in b.items()}).logits
                probs.append(torch.softmax(lo,-1).cpu().numpy())
        return np.vstack(probs)
    gp=predict(g.sentence.tolist()); gpred=[LABELS[i] for i in gp.argmax(1)]
    gh=g.human_label.tolist()
    k=cohen_kappa_score(gh,gpred,labels=LABELS); acc=np.mean([a==b for a,b in zip(gh,gpred)])
    val_rows.append({"cell":cell,"coder":coder,"condition":cond,"target":tgt,
                     "n_gold":len(g),"accuracy":acc,"kappa":k})
    print(f"  {tgt} GOLD kappa={k:.3f} acc={acc:.3f}",flush=True)
    torch.save({"target":tgt}, os.path.join(OUT,f"trained_{tgt}.flag"))
    # stash model for inference stage by keeping in memory dict
    globals()[f"model_{tgt}"]=model

pd.DataFrame(val_rows).to_csv(os.path.join(OUT,"val.csv"),index=False)

# ---- inference over all topic-78/79 sentences ----
SRC=os.path.join(C,"data/corpus_with_topics.parquet")
import pyarrow.parquet as pq
pf=pq.ParquetFile(SRC); KEYS={78,79}
shard=int(os.environ.get("INFER_SHARD","0")); nsh=int(os.environ.get("INFER_NSHARDS","1"))
def predict_batch(model, texts):
    out=[]; dl2=DataLoader(DS(list(texts)),batch_size=128)
    with torch.no_grad():
        for b in dl2:
            lo=model(**{k:v.to(DEV) for k,v in b.items()}).logits
            out.append(torch.softmax(lo,-1).cpu().numpy())
    return np.vstack(out) if out else np.zeros((0,4))
allrows=[]
rg_list=[i for i in range(pf.metadata.num_row_groups) if i%nsh==shard]
for ri,rg in enumerate(rg_list):
    df=pf.read_row_group(rg,columns=["show","date","episode_number","sentence_id","sentence","topic"]).to_pandas()
    df=df[df.topic.isin(KEYS)]
    if len(df)==0: continue
    texts=df.sentence.fillna("").astype(str).tolist()
    rec=df[["show","date","episode_number","sentence_id","topic"]].copy()
    for tgt in TARGETS:
        p=predict_batch(globals()[f"model_{tgt}"],texts)
        rec[f"{tgt}_label"]=[LABELS[i] for i in p.argmax(1)]
        rec[f"{tgt}_p_pos"]=p[:,0]; rec[f"{tgt}_p_neg"]=p[:,1]
        # signed expected stance among mentioned mass: (p_pos - p_neg)/(p_pos+p_neg+p_neu)
        denom=p[:,0]+p[:,1]+p[:,2]
        rec[f"{tgt}_score"]=np.where(denom>0,(p[:,0]-p[:,1]),np.nan)
    allrows.append(rec)
    if (ri+1)%20==0: print(f"  infer rg {ri+1}/{len(rg_list)}",flush=True)
res=pd.concat(allrows,ignore_index=True) if allrows else pd.DataFrame()
import pyarrow as pa
pq.write_table(pa.Table.from_pandas(res,preserve_index=False),
               os.path.join(OUT,f"preds_shard{shard}.parquet"))
open(os.path.join(OUT,"DONE"),"w").write("ok")
print(f"CELL {cell} DONE: {len(res)} sentences scored",flush=True)
